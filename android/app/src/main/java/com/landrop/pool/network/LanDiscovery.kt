package com.landrop.pool.network

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Build
import com.landrop.pool.model.RemoteFileInfo
import com.landrop.pool.model.RemotePeer
import com.landrop.pool.model.SharedFile
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.ConcurrentHashMap

class LanDiscovery(
    private val context: Context,
    val deviceId: String,
    val deviceName: String,
    private val httpPort: Int
) {
    companion object {
        const val BROADCAST_PORT = 45454
    }

    private val _peers = MutableStateFlow<Map<String, RemotePeer>>(emptyMap())
    val peers: StateFlow<Map<String, RemotePeer>> = _peers

    private val peerMap = ConcurrentHashMap<String, RemotePeer>()
    private var multicastLock: WifiManager.MulticastLock? = null
    private var isRunning = false
    private var currentFiles: List<SharedFile> = emptyList()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    fun updateSharedFiles(files: List<SharedFile>) {
        currentFiles = files
        // Natychmiastowe rozgłoszenie nowej puli
        scope.launch { sendBeacon("beacon") }
    }

    fun addManualPeer(ip: String, port: Int = 50505) {
        scope.launch(Dispatchers.IO) {
            try {
                val url = java.net.URL("http://$ip:$port/api/pool")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.connectTimeout = 3000
                conn.readTimeout = 3000
                val stream = conn.inputStream
                val text = stream.bufferedReader().use { it.readText() }
                val root = JSONObject(text)
                val senderId = root.optString("deviceId", ip)
                val senderName = root.optString("deviceName", "Urządzenie ($ip)")
                val filesArray = root.optJSONArray("files") ?: JSONArray()
                val fileList = mutableListOf<RemoteFileInfo>()
                for (i in 0 until filesArray.length()) {
                    val f = filesArray.getJSONObject(i)
                    fileList.add(
                        RemoteFileInfo(
                            id = f.optString("id"),
                            name = f.optString("name"),
                            size = f.optLong("size")
                        )
                    )
                }
                peerMap[senderId] = RemotePeer(
                    deviceId = senderId,
                    deviceName = senderName,
                    ip = ip,
                    port = port,
                    files = fileList,
                    lastSeen = System.currentTimeMillis() + 3600000L
                )
                _peers.value = HashMap(peerMap)
            } catch (e: Exception) {}
        }
    }

    fun start() {
        if (isRunning) return
        isRunning = true

        // Wlaczenie odbioru pakietow multicast/broadcast w Androidzie
        try {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("LanDropMulticastLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) {}

        // Watek nasluchujacy
        scope.launch { listenLoop() }

        // Watek rozglaszajacy i czyszczacy
        scope.launch {
            while (isRunning) {
                sendBeacon("beacon")
                prunePeers()
                delay(2000)
            }
        }
    }

    private fun listenLoop() {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket(BROADCAST_PORT)
            socket.broadcast = true
            val buffer = ByteArray(65535)

            while (isRunning) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)

                val senderIp = packet.address.hostAddress ?: continue
                val jsonStr = String(packet.data, 0, packet.length, Charsets.UTF_8)

                try {
                    val root = JSONObject(jsonStr)
                    val senderId = root.optString("deviceId")
                    if (senderId.isEmpty() || senderId == deviceId) continue

                    val type = root.optString("type", "beacon")
                    if (type == "farewell") {
                        peerMap.remove(senderId)
                        _peers.value = HashMap(peerMap)
                    } else {
                        val senderName = root.optString("deviceName", "Urzadzenie ($senderIp)")
                        val port = root.optInt("port", 50505)
                        val filesArray = root.optJSONArray("files") ?: JSONArray()
                        val fileList = mutableListOf<RemoteFileInfo>()

                        for (i in 0 until filesArray.length()) {
                            val f = filesArray.getJSONObject(i)
                            fileList.add(
                                RemoteFileInfo(
                                    id = f.optString("id"),
                                    name = f.optString("name"),
                                    size = f.optLong("size")
                                )
                            )
                        }

                        peerMap[senderId] = RemotePeer(
                            deviceId = senderId,
                            deviceName = senderName,
                            ip = senderIp,
                            port = port,
                            files = fileList,
                            lastSeen = System.currentTimeMillis()
                        )
                        _peers.value = HashMap(peerMap)
                    }
                } catch (e: Exception) {}
            }
        } catch (e: Exception) {
            // Ignoruj bledy zamykania socketu
        } finally {
            socket?.close()
        }
    }

    private suspend fun sendBeacon(type: String) = withContext(Dispatchers.IO) {
        try {
            val root = JSONObject()
            root.put("type", type)
            root.put("deviceId", deviceId)
            root.put("deviceName", deviceName)
            root.put("platform", "android")
            root.put("port", httpPort)

            val arr = JSONArray()
            for (f in currentFiles) {
                val item = JSONObject()
                item.put("id", f.id)
                item.put("name", f.name)
                item.put("size", f.size)
                arr.put(item)
            }
            root.put("files", arr)

            val bytes = root.toString().toByteArray(Charsets.UTF_8)
            val socket = DatagramSocket()
            socket.broadcast = true

            val target = InetAddress.getByName("255.255.255.255")
            val packet = DatagramPacket(bytes, bytes.size, target, BROADCAST_PORT)
            socket.send(packet)
            socket.close()
        } catch (e: Exception) {}
    }

    private fun prunePeers() {
        val now = System.currentTimeMillis()
        var changed = false
        val iterator = peerMap.entries.iterator()
        while (iterator.hasNext()) {
            val entry = iterator.next()
            if (now - entry.value.lastSeen > 6000) {
                iterator.remove()
                changed = true
            }
        }
        if (changed) {
            _peers.value = HashMap(peerMap)
        }
    }

    fun stop() {
        isRunning = false
        scope.launch {
            sendBeacon("farewell")
            delay(100)
            scope.cancel()
        }
        try {
            if (multicastLock?.isHeld == true) {
                multicastLock?.release()
            }
        } catch (e: Exception) {}
    }
}
