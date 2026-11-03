package br.com.majeirkn.majeirknai

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import java.io.File

/**
 * Servico em primeiro plano que executa o llama-server no proprio aparelho.
 *
 * Nao ha JNI: os binarios do llama.cpp sao empacotados em assets/arm64-v8a,
 * copiados para os arquivos do app no primeiro uso e executados como processo
 * filho. A interface web fica em http://127.0.0.1:8081 e a Activity carrega
 * esse endereco. O caminho e o mesmo usado pelo launcher em Python/Termux.
 */
class LlamaService : Service() {

    companion object {
        const val PORT = 8081
        const val ACTION_START = "br.com.majeirkn.action.START"
        const val ACTION_STOP = "br.com.majeirkn.action.STOP"
        const val EXTRA_MODEL_PATH = "model_path"
        private const val NOTIFICATION_ID = 1001
        private const val ABI = "arm64-v8a"

        /** alias do SONAME -> arquivo real, criado no diretorio privado do app. */
        private val LIBRARY_ALIASES = mapOf(
            "libggml-base.so.0" to "libggml-base.so.0.28.0",
            "libggml-cpu.so.0" to "libggml-cpu.so.0.28.0",
            "libggml.so.0" to "libggml.so.0.28.0",
            "libllama-common.so.0" to "libllama-common.so.0.8.0",
            "libllama.so.0" to "libllama.so.0.8.0",
            "libmtmd.so.0" to "libmtmd.so.0.8.0",
        )

        fun start(context: Context, modelPath: String) {
            context.startForegroundService(
                Intent(context, LlamaService::class.java)
                    .setAction(ACTION_START)
                    .putExtra(EXTRA_MODEL_PATH, modelPath)
            )
        }

        fun stop(context: Context) {
            context.startService(
                Intent(context, LlamaService::class.java).setAction(ACTION_STOP)
            )
        }

        fun baseUrl(): String = "http://127.0.0.1:$PORT/"
    }

    private var process: Process? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopServer()
            return START_NOT_STICKY
        }
        startServer(intent)
        return START_STICKY
    }

    // ---------------------------------------------------------------- inicio

    private fun startServer(intent: Intent?) {
        startForeground(NOTIFICATION_ID, buildNotification())

        if (process != null) {
            return // o servidor ja esta rodando
        }

        val modelPath = intent?.getStringExtra(EXTRA_MODEL_PATH)
        if (modelPath.isNullOrBlank() || !File(modelPath).canRead()) {
            ServerLog.write(this, "modelo indisponivel: $modelPath")
            stopServer()
            return
        }

        // A tela pode apagar durante uma resposta longa.
        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MajeirknAI::server")
            .apply { acquire(4 * 60 * 60 * 1000L) }

        val nativeDir = prepareNativeBinaries()
        val webDir = prepareWebAssets()
        val command = buildCommand(nativeDir, webDir, modelPath)

        try {
            process = ProcessBuilder(command)
                .directory(nativeDir)
                .redirectErrorStream(true)
                .apply { environment()["LD_LIBRARY_PATH"] = nativeDir.absolutePath + ":" + applicationInfo.nativeLibraryDir }
                .start()
            ServerLog.write(this, "iniciado: ${command.joinToString(" ")}")
        } catch (error: Exception) {
            ServerLog.write(this, "falha ao iniciar: ${error.message}")
            stopServer()
        }
    }

    /**
     * Copia os arquivos de assets/$ABI (executavel e bibliotecas) para os
     * arquivos do app, cria os aliases de versao e os torna executaveis.
     *
     * Os aliases (libX.so.0 -> libX.so.0.28.0) existem porque o carregador do
     * Android pede o SONAME versionado; sem eles o binario nao acharia as libs.
     * O APK carrega so os arquivos reais para nao duplicar o tamanho, e os
     * links sao criados aqui, onde o sistema de arquivos privado os aceita.
     */
    private fun prepareNativeBinaries(): File {
        val target = File(filesDir, "bin").apply { mkdirs() }
        val names = assets.list(ABI) ?: return target
        for (name in names) {
            val destination = File(target, name)
            try {
                assets.open("$ABI/$name").use { input ->
                    destination.outputStream().use { output -> input.copyTo(output) }
                }
                destination.setExecutable(true)
            } catch (error: Exception) {
                ServerLog.write(this, "falha ao copiar $name: ${error.message}")
            }
        }
        createLibraryAliases(target)
        return target
    }

    private fun createLibraryAliases(target: File) {
        LIBRARY_ALIASES.forEach { (alias, realFile) ->
            val link = File(target, alias)
            if (link.exists()) return@forEach
            try {
                android.system.Os.symlink(realFile, link.absolutePath)
            } catch (error: Exception) {
                ServerLog.write(this, "falha ao criar alias $alias: ${error.message}")
            }
        }
    }

    /** Copia a interface web dos assets, onde o llama-server a serve com --path. */
    private fun prepareWebAssets(): File {
        val target = File(filesDir, "webui").apply { mkdirs() }
        copyAssetTree("webui", target)
        return target
    }

    private fun copyAssetTree(assetPath: String, target: File) {
        assets.list(assetPath)?.forEach { name ->
            val source = "$assetPath/$name"
            val destination = File(target, name)
            val children = assets.list(source)
            if (!children.isNullOrEmpty()) {
                destination.mkdirs()
                copyAssetTree(source, destination)
            } else {
                assets.open(source).use { input ->
                    destination.outputStream().use { output -> input.copyTo(output) }
                }
            }
        }
    }

    private fun buildCommand(nativeDir: File, webDir: File, modelPath: String): List<String> {
        val threads = (Runtime.getRuntime().availableProcessors() - 1).coerceAtLeast(2)
        return listOf(
            File(applicationInfo.nativeLibraryDir, "libllama-server.so").absolutePath,
            "--model", modelPath,
            "--ctx-size", "2048",
            "--threads", threads.toString(),
            "--host", "127.0.0.1",
            "--port", PORT.toString(),
            "--parallel", "1",
            "--no-warmup",
            "--reasoning-budget", "0",
            "--path", webDir.absolutePath,
        )
    }

    // --------------------------------------------------------------- parada

    private fun stopServer() {
        process?.destroy()
        process = null
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        stopServer()
        super.onDestroy()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // O servidor continua: fechar a tela nao deve encerrar a conversa.
    }

    // --------------------------------------------------------- notificacao

    private fun buildNotification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(
                    getString(R.string.service_channel_name),
                    getString(R.string.service_channel_description),
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }

        val openIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, getString(R.string.service_channel_name))
            .setContentTitle(getString(R.string.service_notification_title))
            .setContentText(getString(R.string.service_notification_text))
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentIntent(openIntent)
            .setOngoing(true)
            .build()
    }
}
