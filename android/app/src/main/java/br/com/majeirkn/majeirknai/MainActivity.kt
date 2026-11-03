package br.com.majeirkn.majeirknai

import android.annotation.SuppressLint
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.StatFs
import android.provider.OpenableColumns
import android.view.View
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.io.File
import java.io.FileOutputStream
import java.util.Locale
import java.util.concurrent.Executors

/**
 * O seletor do Android retorna URIs content://, nao caminhos /storage confiaveis.
 * O modelo e copiado para filesDir/models, privado do aplicativo, antes de iniciar
 * o llama-server. Isso funciona com Scoped Storage no Android 10 ou superior.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progress: ProgressBar
    private lateinit var status: TextView
    private lateinit var pickModelButton: Button

    private val prefs by lazy { getSharedPreferences("majeirkn", MODE_PRIVATE) }
    private val copyExecutor = Executors.newSingleThreadExecutor()
    @Volatile private var copyingModel = false

    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) copySelectedModel(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        progress = findViewById(R.id.progress)
        status = findViewById(R.id.status)
        pickModelButton = findViewById(R.id.pick_model)
        pickModelButton.setOnClickListener { launchModelPicker() }
        configureWebView()

        val savedPath = prefs.getString("model_path", null)
        val savedModel = savedPath?.let { File(it) }
        if (savedModel != null && savedModel.isFile && savedModel.canRead() && savedModel.length() > 0L) {
            startServer(savedModel.absolutePath)
        } else {
            prefs.edit().remove("model_path").apply()
            showModelPicker()
        }
    }

    private fun launchModelPicker() {
        if (!copyingModel) pickModel.launch(arrayOf("*/*"))
    }

    /** Copia o URI autorizado pelo SAF em background; nunca converte content:// em path. */
    private fun copySelectedModel(uri: Uri) {
        if (copyingModel) return
        val displayName = queryDisplayName(uri)
        if (!displayName.endsWith(".gguf", ignoreCase = true)) {
            showPickerError("Selecione um arquivo com extensao .gguf.")
            return
        }

        copyingModel = true
        pickModelButton.visibility = View.GONE
        progress.visibility = View.VISIBLE
        progress.isIndeterminate = true
        status.visibility = View.VISIBLE
        status.text = "Preparando o modelo...\n" + displayName

        copyExecutor.execute {
            val modelsDir = File(filesDir, "models")
            val destination = File(modelsDir, "model.gguf")
            val temporary = File(modelsDir, "model.gguf.part")
            try {
                if (!modelsDir.exists() && !modelsDir.mkdirs()) {
                    throw IllegalStateException("Nao foi possivel criar a pasta privada dos modelos.")
                }

                val expectedSize = querySize(uri)
                val available = StatFs(filesDir.absolutePath).availableBytes
                if (expectedSize > 0L && available < expectedSize + 64L * 1024L * 1024L) {
                    throw IllegalStateException(
                        "Espaco insuficiente. Modelo: " + formatBytes(expectedSize) +
                            "; livre: " + formatBytes(available) + "."
                    )
                }

                var copied = 0L
                val buffer = ByteArray(1024 * 1024)
                val input = contentResolver.openInputStream(uri)
                    ?: throw IllegalStateException("O Android nao conseguiu abrir o arquivo selecionado.")

                input.use { source ->
                    FileOutputStream(temporary).use { output ->
                        while (true) {
                            val count = source.read(buffer)
                            if (count < 0) break
                            if (count == 0) continue
                            output.write(buffer, 0, count)
                            copied += count
                            if (copied % (16L * 1024L * 1024L) < buffer.size) {
                                val current = copied
                                runOnUiThread {
                                    if (!isFinishing && !isDestroyed) {
                                        progress.isIndeterminate = false
                                        progress.max = 100
                                        val percent = if (expectedSize > 0L) {
                                            ((current * 100L) / expectedSize).toInt().coerceIn(0, 100)
                                        } else 0
                                        progress.progress = percent
                                        val totalText = if (expectedSize > 0L) formatBytes(expectedSize) else "desconhecido"
                                        status.text = "Copiando modelo... " + percent + "%\n" +
                                            formatBytes(current) + " de " + totalText
                                    }
                                }
                            }
                        }
                        output.fd.sync()
                    }
                }

                if (copied < 1024L * 1024L) {
                    throw IllegalStateException("O arquivo selecionado esta vazio ou incompleto.")
                }
                if (expectedSize > 0L && copied != expectedSize) {
                    throw IllegalStateException(
                        "Copia incompleta: " + formatBytes(copied) + " de " + formatBytes(expectedSize) + "."
                    )
                }

                if (destination.exists() && !destination.delete()) {
                    throw IllegalStateException("Nao foi possivel substituir o modelo anterior.")
                }
                if (!temporary.renameTo(destination)) {
                    throw IllegalStateException("Nao foi possivel finalizar a copia do modelo.")
                }

                prefs.edit()
                    .putString("model_uri", uri.toString())
                    .putString("model_path", destination.absolutePath)
                    .putString("model_name", displayName)
                    .apply()

                runOnUiThread {
                    copyingModel = false
                    if (!isFinishing && !isDestroyed) {
                        status.text = "Modelo copiado. Iniciando servidor local..."
                        progress.isIndeterminate = true
                        startServer(destination.absolutePath)
                    }
                }
            } catch (error: Exception) {
                temporary.delete()
                runOnUiThread {
                    copyingModel = false
                    if (!isFinishing && !isDestroyed) {
                        progress.visibility = View.GONE
                        status.text = getString(R.string.server_failed) + "\n\n" +
                            (error.message ?: "Falha desconhecida ao copiar o modelo.")
                        pickModelButton.visibility = View.VISIBLE
                    }
                }
            }
        }
    }

    private fun queryDisplayName(uri: Uri): String {
        var cursor: Cursor? = null
        try {
            cursor = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            if (cursor != null && cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return cursor.getString(index) ?: "modelo.gguf"
            }
        } catch (_: Exception) {
        } finally {
            cursor?.close()
        }
        return (uri.lastPathSegment ?: "modelo.gguf").substringAfterLast('/')
    }

    private fun querySize(uri: Uri): Long {
        var cursor: Cursor? = null
        try {
            cursor = contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)
            if (cursor != null && cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (index >= 0 && !cursor.isNull(index)) return cursor.getLong(index)
            }
        } catch (_: Exception) {
        } finally {
            cursor?.close()
        }
        return -1L
    }

    private fun formatBytes(bytes: Long): String {
        val gb = bytes / (1024.0 * 1024.0 * 1024.0)
        return if (gb >= 1.0) String.format(Locale.US, "%.2f GB", gb)
        else String.format(Locale.US, "%.0f MB", bytes / (1024.0 * 1024.0))
    }

    private fun showPickerError(message: String) {
        AlertDialog.Builder(this)
            .setTitle("Arquivo GGUF invalido")
            .setMessage(message)
            .setPositiveButton("OK", null)
            .show()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            textZoom = 100
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (request.method != "GET") return null
                return when (request.url.host) {
                    "127.0.0.1", "localhost" -> null
                    else -> WebResourceResponse(null, null, null)
                }
            }
        }
    }

    private fun startServer(modelPath: String) {
        val model = File(modelPath)
        if (!model.isFile || !model.canRead() || model.length() == 0L) {
            status.text = getString(R.string.server_failed) + "\n\nO modelo salvo nao esta acessivel."
            progress.visibility = View.GONE
            pickModelButton.visibility = View.VISIBLE
            return
        }
        pickModelButton.visibility = View.GONE
        progress.visibility = View.VISIBLE
        progress.isIndeterminate = true
        status.visibility = View.VISIBLE
        status.text = getString(R.string.loading_model)
        LlamaService.start(this, model.absolutePath)
        waitForServer()
    }

    private fun waitForServer() {
        val handler = Handler(Looper.getMainLooper())
        val deadline = System.currentTimeMillis() + 5 * 60 * 1000L
        val check = object : Runnable {
            override fun run() {
                if (probeHealth(LlamaService.baseUrl())) {
                    progress.visibility = View.GONE
                    status.visibility = View.GONE
                    webView.visibility = View.VISIBLE
                    webView.loadUrl(LlamaService.baseUrl())
                    return
                }
                if (System.currentTimeMillis() > deadline) {
                    status.text = getString(R.string.server_failed) + "\n\n" +
                        ServerLog.read(this@MainActivity).takeLast(700)
                    progress.visibility = View.GONE
                    pickModelButton.visibility = View.VISIBLE
                    return
                }
                handler.postDelayed(this, 1000)
            }
        }
        handler.post(check)
    }

    private fun probeHealth(base: String): Boolean {
        return try {
            val connection = java.net.URL(base + "health").openConnection() as java.net.HttpURLConnection
            connection.connectTimeout = 3000
            connection.readTimeout = 3000
            connection.requestMethod = "GET"
            val ok = connection.responseCode == 200
            connection.disconnect()
            ok
        } catch (_: Exception) {
            false
        }
    }

    private fun showModelPicker() {
        AlertDialog.Builder(this)
            .setTitle("Modelo GGUF necessario")
            .setMessage(
                "Escolha o arquivo .gguf pelo seletor do Android. O MajeirknAI vai copia-lo " +
                    "para o armazenamento privado do aplicativo. O modelo pode ocupar cerca de 1,3 GB."
            )
            .setPositiveButton("Escolher arquivo") { _, _ -> launchModelPicker() }
            .setNegativeButton("Cancelar", null)
            .show()
        pickModelButton.visibility = View.VISIBLE
    }

    override fun onBackPressed() {
        if (webView.visibility == View.VISIBLE && webView.canGoBack()) webView.goBack()
        else super.onBackPressed()
    }

    override fun onDestroy() {
        copyExecutor.shutdownNow()
        LlamaService.stop(this)
        super.onDestroy()
    }
}
