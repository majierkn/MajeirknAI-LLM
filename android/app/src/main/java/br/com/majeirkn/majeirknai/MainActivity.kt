package br.com.majeirkn.majeirknai

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
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

/**
 * Tela principal: espera o servidor local ficar pronto e carrega a interface
 * web em http://127.0.0.1:8081 (a mesma pagina usada no Termux).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progress: ProgressBar
    private lateinit var status: TextView
    private lateinit var pickModelButton: Button

    private val prefs by lazy { getSharedPreferences("majeirkn", MODE_PRIVATE) }

    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        uri ?: return@registerForActivityResult
        // Precisa sobreviver a reinicios: pede permissao persistente na arvore.
        try {
            contentResolver.takePersistableUriPermission(
                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
        } catch (_: Exception) {
            // Uri nao persistivel: usamos so nesta sessao.
        }
        prefs.edit().putString("model_uri", uri.toString()).apply()
        startWithModel(resolveUriPath(uri))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        progress = findViewById(R.id.progress)
        status = findViewById(R.id.status)
        pickModelButton = findViewById(R.id.pick_model)

        configureWebView()

        val savedModel = prefs.getString("model_path", null)
        val modelPath = savedModel ?: findModel()
        if (modelPath != null && File(modelPath).canRead()) {
            prefs.edit().putString("model_path", modelPath).apply()
            startServer(modelPath)
        } else {
            showModelPicker()
        }

        pickModelButton.setOnClickListener { pickModel.launch(arrayOf("*/*")) }
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
            override fun shouldInterceptRequest(
                view: WebView, request: WebResourceRequest
            ): WebResourceResponse? {
                if (request.method != "GET") {
                    return null
                }
                return when (request.url.host) {
                    "127.0.0.1", "localhost" -> null // a API local passa direto
                    else -> WebResourceResponse(null, null, null) // sem internet
                }
            }
        }
    }

    private fun startServer(modelPath: String) {
        pickModelButton.visibility = View.GONE
        status.setText(R.string.loading_model)
        WebView.setWebContentsDebuggingEnabled(false)
        LlamaService.start(this, modelPath)
        waitForServer(modelPath)
    }

    /** Polling em /health ate o modelo carregar (leva de 5 a 30 s no celular). */
    private fun waitForServer(modelPath: String) {
        val handler = android.os.Handler(mainLooper)
        val deadline = System.currentTimeMillis() + 5 * 60 * 1000L
        val check = object : Runnable {
            override fun run() {
                if (LlamaService.baseUrl().let { probeHealth(it) }) {
                    progress.visibility = View.GONE
                    status.visibility = View.GONE
                    webView.loadUrl(LlamaService.baseUrl())
                    return
                }
                if (System.currentTimeMillis() > deadline) {
                    status.text = getString(R.string.server_failed) + "\n\n" +
                        ServerLog.read(this@MainActivity).takeLast(400)
                    progress.visibility = View.GONE
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
            .setTitle("Modelo nao encontrado")
            .setMessage(
                "Coloque o arquivo Qwen3.5-2B-Q4_K_M.gguf em uma pasta do aparelho " +
                    "(ex.: Download) e escolha o arquivo. Ele tem cerca de 1,3 GB."
            )
            .setPositiveButton("Escolher arquivo") { _, _ ->
                pickModel.launch(arrayOf("*/*"))
            }
            .setNegativeButton("Cancelar", null)
            .show()
        pickModelButton.visibility = View.VISIBLE
    }

    /** Procura o modelo nos lugares usuais. */
    private fun findModel(): String? {
        val candidates = listOf(
            File(Environment.getExternalStorageDirectory(), "Download/models"),
            File(Environment.getExternalStorageDirectory(), "Download"),
            File(Environment.getExternalStorageDirectory(), "MajeirknAI/models"),
            File(filesDir, "models"),
        )
        for (directory in candidates) {
            if (!directory.isDirectory) continue
            directory.listFiles()?.firstOrNull { file ->
                file.isFile && file.name.endsWith(".gguf", ignoreCase = true)
            }?.let { return it.absolutePath }
        }
        return null
    }

    /**
     * Converte um Uri do SAF em caminho de arquivo quando possivel; senao devolve
     * null e quem chamou trata o erro (llama-server precisa de caminho real).
     */
    private fun resolveUriPath(uri: Uri): String? {
        val documentId = android.provider.DocumentsContract.getDocumentId(uri)
        val parts = documentId.split(":")
        if (parts.size != 2) return null
        val volume = parts[0]
        val relative = parts[1]
        val base = if (volume == "primary") {
            Environment.getExternalStorageDirectory().absolutePath
        } else {
            "/storage/$volume"
        }
        return "$base/$relative"
    }

    private fun startWithModel(path: String?) {
        if (path == null || !File(path).canRead()) {
            status.text = getString(R.string.server_failed) + "\n\nCaminho invalido: $path"
            return
        }
        prefs.edit().putString("model_path", path).apply()
        startServer(path)
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        LlamaService.stop(this)
        super.onDestroy()
    }
}
