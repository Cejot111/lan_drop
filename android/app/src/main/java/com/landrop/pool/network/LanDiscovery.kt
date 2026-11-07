package com.landrop.pool.network

import android.content.Context
import android.net.wifi.WifiManager
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
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URL
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
    private val knownPeerIps = ConcurrentHashMap.newKeySet<String>()

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
        knownPeerIps.add(ip)
        scope.launch(Dispatchers.IO) {
            fetchPeerPool(ip, port)
        }
    }

    private fun fetchPeerPool(ip: String, port: Int) {
        try {
            val url = URL("http://$ip:$port/api/pool?t=${System.currentTimeMillis()}")
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 2500
            conn.readTimeout = 2500
            conn.useCaches = false
            conn.setRequestProperty("Cache-Control", "no-cache")

            if (conn.responseCode == 200) {
                val text = conn.inputStream.bufferedReader().use { it.readText() }
                val root = JSONObject(text)
                val senderId = root.optString("deviceId", ip)
                if (senderId != deviceId) {
                    val senderName = root.optString("deviceName", "Komputer ($ip)")
                    val filesArray = root.optJSONArray("files") ?: JSONArray()
                    val fileList = mutableListOf<RemoteFileInfo>()

                    for (i in 0 until filesArray.length()) {
                        val f = filesArray.getJSONObject(i)
                        fileList.add(
                            RemoteFileInfo(
                                id = f.optString("id"),
                                name = f.optString("name"),
                                size = f.optLong("size"),
                                type = f.optString("type", "file"),
                                content = if (f.has("content")) f.optString("content") else null
                            )
                        )
                    }

                    peerMap[senderId] = RemotePeer(
                        deviceId = senderId,
                        deviceName = senderName,
                        ip = ip,
                        port = port,
                        files = fileList,
                        lastSeen = System.currentTimeMillis()
                    )
                    _peers.value = HashMap(peerMap)
                }
            }
        } catch (e: Exception) {
            // Ignoruj błędy sieciowe przy odpytywaniu
        }
    }

    fun start() {
        if (isRunning) return
        isRunning = true

        // Włączenie odbioru pakietów multicast/broadcast w Androidzie
        try {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("LanDropMulticastLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) {}

        // Wątek nasłuchujący UDP
        scope.launch { listenLoop() }

        // Wątek rozgłaszający UDP
        scope.launch {
            while (isRunning) {
                sendBeacon("beacon")
                delay(2000)
            }
        }

        // Aktywny wątek odpytywania TCP/HTTP (gwarancja synchronizacji z PC nawet przy blokadzie UDP przez router)
        scope.launch {
            while (isRunning) {
                for (peer in peerMap.values) {
                    fetchPeerPool(peer.ip, peer.port)
                }
                for (ip in knownPeerIps) {
                    if (peerMap.values.none { it.ip == ip }) {
                        fetchPeerPool(ip, 50505)
                    }
                }
                prunePeers()
                delay(2500)
            }
        }
    }

    private fun listenLoop() {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket(BROADCAST_PORT)
            socket.broadcast = true
            socket.reuseAddress = true
            val buffer = ByteArray(65535)

            while (isRunning) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)

                val senderIp = packet.address.hostAddress ?: continue
                knownPeerIps.add(senderIp)

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
                        val senderName = root.optString("deviceName", "Komputer ($senderIp)")
                        val port = root.optInt("port", 50505)
                        val filesArray = root.optJSONArray("files") ?: JSONArray()
                        val fileList = mutableListOf<RemoteFileInfo>()

                        for (i in 0 until filesArray.length()) {
                            val f = filesArray.getJSONObject(i)
                            fileList.add(
                                RemoteFileInfo(
                                    id = f.optString("id"),
                                    name = f.optString("name"),
                                    size = f.optLong("size"),
                                    type = f.optString("type", "file"),
                                    content = if (f.has("content")) f.optString("content") else null
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
            // Ignoruj błędy zamykania socketu
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
                item.put("type", f.type)
                if (f.content != null) {
                    item.put("content", f.content)
                }
                arr.put(item)
            }
            root.put("files", arr)

            val bytes = root.toString().toByteArray(Charsets.UTF_8)
            val socket = DatagramSocket()
            socket.broadcast = true

            // 1. Rozgłoszenie broadcastem ogólnym
            try {
                val target = InetAddress.getByName("255.255.255.255")
                val packet = DatagramPacket(bytes, bytes.size, target, BROADCAST_PORT)
                socket.send(packet)
            } catch (e: Exception) {}

            // 2. Bezpośrednie pakiety Unicast do znanych adresów IP komputerów (omija filtry broadcastu w FunBox)
            for (peerIp in knownPeerIps) {
                try {
                    val unicastTarget = InetAddress.getByName(peerIp)
                    val unicastPacket = DatagramPacket(bytes, bytes.size, unicastTarget, BROADCAST_PORT)
                    socket.send(unicastPacket)
                } catch (e: Exception) {}
            }

            socket.close()
        } catch (e: Exception) {}
    }

    private fun prunePeers() {
        val now = System.currentTimeMillis()
        var changed = false
        val iterator = peerMap.entries.iterator()
        while (iterator.hasNext()) {
            val entry = iterator.next()
            if (now - entry.value.lastSeen > 8000) {
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
