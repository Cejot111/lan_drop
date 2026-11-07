package com.landrop.pool.network

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import com.landrop.pool.model.RemoteFileItem
import com.landrop.pool.model.TransferState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL

class FileDownloader(private val context: Context) {

    suspend fun download(
        item: RemoteFileItem,
        progressFlow: MutableStateFlow<Map<String, TransferState>>
    ): Boolean = withContext(Dispatchers.IO) {
        val urlStr = "http://${item.peerIp}:${item.peerPort}/api/download/${item.id}"
        var connection: HttpURLConnection? = null
        var inputStream: InputStream? = null
        var outputStream: OutputStream? = null

        try {
            updateProgress(progressFlow, item.id, item.name, 0, item.size, 0.0, false, null)

            val url = URL(urlStr)
            connection = url.openConnection() as HttpURLConnection
            connection.connectTimeout = 10000
            connection.readTimeout = 30000
            connection.requestMethod = "GET"
            connection.connect()

            if (connection.responseCode != 200) {
                updateProgress(progressFlow, item.id, item.name, 0, item.size, 0.0, false, "HTTP ${connection.responseCode}")
                return@withContext false
            }

            val totalBytes = connection.contentLength.toLong().let { if (it > 0) it else item.size }
            inputStream = connection.inputStream

            // Otwórz strumień wyjściowy do katalogu Downloads
            val pair = createDownloadOutputStream(context, item.name)
            outputStream = pair.second

            val buffer = ByteArray(256 * 1024) // 256 KB
            var downloaded = 0L
            var lastTime = System.currentTimeMillis()
            var lastBytes = 0L
            var read: Int

            while (inputStream.read(buffer).also { read = it } != -1) {
                outputStream.write(buffer, 0, read)
                downloaded += read

                val now = System.currentTimeMillis()
                val elapsed = now - lastTime
                if (elapsed >= 300) {
                    val speedMbps = ((downloaded - lastBytes) / (1024.0 * 1024.0)) / (elapsed / 1000.0)
                    lastTime = now
                    lastBytes = downloaded
                    updateProgress(progressFlow, item.id, item.name, downloaded, totalBytes, speedMbps, false, null)
                }
            }
            outputStream.flush()

            // Oznacz jako zakończone
            updateProgress(progressFlow, item.id, item.name, totalBytes, totalBytes, 0.0, true, null)
            true
        } catch (e: Exception) {
            updateProgress(progressFlow, item.id, item.name, 0, item.size, 0.0, false, e.localizedMessage ?: "Błąd pobierania")
            false
        } finally {
            try { inputStream?.close() } catch (e: Exception) {}
            try { outputStream?.close() } catch (e: Exception) {}
            connection?.disconnect()
        }
    }

    private fun createDownloadOutputStream(context: Context, fileName: String): Pair<Uri?, OutputStream> {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val contentValues = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/LanDrop")
            }
            val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                ?: throw IllegalStateException("Nie można utworzyć wpisu w MediaStore.Downloads")
            val stream = context.contentResolver.openOutputStream(uri)
                ?: throw IllegalStateException("Nie można otworzyć strumienia do zapisu")
            return Pair(uri, stream)
        } else {
            val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "LanDrop")
            if (!dir.exists()) dir.mkdirs()
            var file = File(dir, fileName)
            var counter = 1
            val baseName = fileName.substringBeforeLast(".")
            val ext = if (fileName.contains(".")) "." + fileName.substringAfterLast(".") else ""
            while (file.exists()) {
                file = File(dir, "${baseName}_$counter$ext")
                counter++
            }
            return Pair(null, FileOutputStream(file))
        }
    }

    private fun updateProgress(
        flow: MutableStateFlow<Map<String, TransferState>>,
        id: String,
        name: String,
        done: Long,
        total: Long,
        speed: Double,
        completed: Boolean,
        error: String?
    ) {
        val map = HashMap(flow.value)
        map[id] = TransferState(
            fileId = id,
            fileName = name,
            bytesDone = done,
            totalBytes = total,
            speedMbps = speed,
            isCompleted = completed,
            error = error
        )
        flow.value = map
    }
}
