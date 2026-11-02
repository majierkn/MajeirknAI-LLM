package br.com.majeirkn.majeirknai

import android.content.Context
import java.io.File

/** Registro simples da saida do llama-server nos arquivos do app. */
object ServerLog {
    private const val NAME = "server.log"

    fun write(context: Context, message: String) {
        try {
            val file = File(context.filesDir, NAME)
            file.appendText("[${System.currentTimeMillis()}] $message\n")
        } catch (_: Exception) {
            // Log nao e critico: nunca deve derrubar o servico.
        }
    }

    fun read(context: Context): String {
        val file = File(context.filesDir, NAME)
        return if (file.exists()) file.readText() else ""
    }
}
