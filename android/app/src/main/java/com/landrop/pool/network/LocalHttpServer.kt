package com.landrop.pool.network

import android.content.Context
import com.landrop.pool.model.SharedFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

class LocalHttpServer(
    private val context: Context,
    private val deviceId: String,
    private val deviceName: String,
    private val requestedPort: Int = 50505
) {
    private var serverSocket: ServerSocket? = null
    var actualPort: Int = requestedPort
        private set

    private val threadPool = Executors.newCachedThreadPool()
    private val sharedFiles = ConcurrentHashMap<String, SharedFile>()
    @Volatile
    private var isRunning = false

    fun updateFiles(files: List<SharedFile>) {
        sharedFiles.clear()
        for (f in files) {
            sharedFiles[f.id] = f
        }
    }

    fun start(): Int {
        for (p in requestedPort..(requestedPort + 50)) {
            try {
                serverSocket = ServerSocket(p)
                actualPort = p
                break
            } catch (e: Exception) {
                // Spróbuj kolejny port
            }
        }

        val s = serverSocket ?: throw IllegalStateException("Nie udało się powiązać serwera z wolnym portem!")
        isRunning = true

        threadPool.execute {
            while (isRunning && !s.isClosed) {
                try {
                    val client = s.accept()
                    threadPool.execute {
                        handleClient(client)
                    }
                } catch (e: Exception) {
                    if (!isRunning) break
                }
            }
        }
        return actualPort
    }

    private fun handleClient(socket: Socket) {
        try {
            socket.soTimeout = 15000
            val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
            val out = BufferedOutputStream(socket.getOutputStream())

            val requestLine = reader.readLine() ?: return
            val parts = requestLine.split(" ")
            if (parts.size < 2) return

            val method = parts[0]
            val rawPath = parts[1]
            val cleanPath = URLDecoder.decode(rawPath.substringBefore("?"), "UTF-8")

            if (method.equals("GET", ignoreCase = true)) {
                if (cleanPath == "/api/pool" || cleanPath == "/api/pool/") {
                    servePoolJson(out)
                } else if (cleanPath.startsWith("/api/download/")) {
                    val fileId = cleanPath.removePrefix("/api/download/").trim('/')
                    serveFileDownload(fileId, out)
                } else if (cleanPath == "/api/ping") {
                    val body = """{"status":"ok"}""".toByteArray(Charsets.UTF_8)
                    writeHttpResponse(out, 200, "OK", "application/json", body.size.toLong())
                    out.write(body)
                    out.flush()
                } else {
                    writeHttpResponse(out, 404, "Not Found", "text/plain", 0)
                    out.flush()
                }
            }
        } catch (e: Exception) {
            // Zamknięcie połączenia lub przerwany transfer
        } finally {
            try { socket.close() } catch (e: Exception) {}
        }
    }

    private fun servePoolJson(out: BufferedOutputStream) {
        val jsonArray = JSONArray()
        for (f in sharedFiles.values) {
            val obj = JSONObject()
            obj.put("id", f.id)
            obj.put("name", f.name)
            obj.put("size", f.size)
            obj.put("mime", f.mime)
            obj.put("type", f.type)
            if (f.content != null) {
                obj.put("content", f.content)
            }
            jsonArray.put(obj)
        }

        val root = JSONObject()
        root.put("deviceId", deviceId)
        root.put("deviceName", deviceName)
        root.put("files", jsonArray)

        val bytes = root.toString().toByteArray(Charsets.UTF_8)
        writeHttpResponse(out, 200, "OK", "application/json; charset=utf-8", bytes.size.toLong())
        out.write(bytes)
        out.flush()
    }

    private fun serveFileDownload(fileId: String, out: BufferedOutputStream) {
        val item = sharedFiles[fileId]
        if (item == null) {
            val msg = "Element nie istnieje lub został usunięty z puli.".toByteArray(Charsets.UTF_8)
            writeHttpResponse(out, 404, "Not Found", "text/plain; charset=utf-8", msg.size.toLong())
            out.write(msg)
            out.flush()
            return
        }

        if (item.type == "link") {
            val linkBytes = (item.content ?: item.name).toByteArray(Charsets.UTF_8)
            writeHttpResponse(out, 200, "OK", "text/plain; charset=utf-8", linkBytes.size.toLong())
            out.write(linkBytes)
            out.flush()
            return
        }

        val uri = item.uri
        if (uri == null) {
            writeHttpResponse(out, 404, "Not Found", "text/plain", 0)
            out.flush()
            return
        }

        try {
            val inputStream = context.contentResolver.openInputStream(uri)
            if (inputStream == null) {
                writeHttpResponse(out, 500, "Error", "text/plain", 0)
                out.flush()
                return
            }

            inputStream.use { inStream ->
                val safeName = item.name.replace("\"", "\\\"")
                val headers = StringBuilder()
                headers.append("HTTP/1.1 200 OK\r\n")
                headers.append("Content-Type: ${item.mime}\r\n")
                headers.append("Content-Length: ${item.size}\r\n")
                headers.append("Content-Disposition: attachment; filename=\"$safeName\"\r\n")
                headers.append("Cache-Control: no-cache, no-store, must-revalidate\r\n")
                headers.append("Access-Control-Allow-Origin: *\r\n")
                headers.append("Connection: close\r\n\r\n")

                out.write(headers.toString().toByteArray(Charsets.UTF_8))
                out.flush()

                // Wysyłanie w buforze 256KB
                val buffer = ByteArray(256 * 1024)
                var bytesRead: Int
                while (inStream.read(buffer).also { bytesRead = it } != -1) {
                    out.write(buffer, 0, bytesRead)
                }
                out.flush()
            }
        } catch (e: Exception) {
            // Przerwano połączenie przez odbiorcę
        }
    }

    private fun writeHttpResponse(out: BufferedOutputStream, code: Int, status: String, mime: String, length: Long) {
        val headers = "HTTP/1.1 $code $status\r\n" +
                "Content-Type: $mime\r\n" +
                "Content-Length: $length\r\n" +
                "Cache-Control: no-cache, no-store, must-revalidate\r\n" +
                "Access-Control-Allow-Origin: *\r\n" +
                "Connection: close\r\n\r\n"
        out.write(headers.toByteArray(Charsets.UTF_8))
    }

    fun stop() {
        isRunning = false
        try {
            serverSocket?.close()
        } catch (e: Exception) {}
        threadPool.shutdownNow()
    }
}
