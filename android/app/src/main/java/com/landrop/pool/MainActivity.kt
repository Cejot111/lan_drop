package com.landrop.pool

import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.landrop.pool.model.RemoteFileItem
import com.landrop.pool.model.SharedFile
import com.landrop.pool.model.TransferState
import com.landrop.pool.network.FileDownloader
import com.landrop.pool.network.LanDiscovery
import com.landrop.pool.network.LocalHttpServer
import com.landrop.pool.ui.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.UUID

class MainActivity : ComponentActivity() {

    private val deviceId = UUID.randomUUID().toString().substring(0, 8)
    private val deviceName = "Telefon (${Build.MODEL})"

    private lateinit var httpServer: LocalHttpServer
    private lateinit var discovery: LanDiscovery
    private lateinit var downloader: FileDownloader

    private val mySharedFiles = mutableStateListOf<SharedFile>()
    private val transfers = MutableStateFlow<Map<String, TransferState>>(emptyMap())

    // Wybór zdjęć i filmów z Galerii
    private val pickVisualMediaLauncher = registerForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia()
    ) { uris ->
        if (uris.isNotEmpty()) {
            addUrisToPool(uris)
        }
    }

    // Wybór dowolnych plików z Menedżera Plików
    private val openDocumentsLauncher = registerForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isNotEmpty()) {
            addUrisToPool(uris)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        downloader = FileDownloader(this)

        // Start lokalnego serwera HTTP (udostępnianie puli telefonu)
        httpServer = LocalHttpServer(this, deviceId, deviceName)
        val port = httpServer.start()

        // Start rozgłaszania LAN (UDP Broadcast)
        discovery = LanDiscovery(this, deviceId, deviceName, port)
        discovery.start()

        setContent {
            LanDropTheme {
                MainAppScreen()
            }
        }
    }

    private fun addUrisToPool(uris: List<Uri>) {
        var addedCount = 0
        for (uri in uris) {
            val (name, size) = getFileInfo(uri)
            val mime = contentResolver.getType(uri) ?: "application/octet-stream"
            val item = SharedFile(
                id = UUID.randomUUID().toString(),
                uri = uri,
                name = name,
                size = size,
                mime = mime
            )
            mySharedFiles.add(item)
            addedCount++
        }

        val currentList = mySharedFiles.toList()
        httpServer.updateFiles(currentList)
        discovery.updateSharedFiles(currentList)

        Toast.makeText(this, "Dodano $addedCount plik(ów) do puli LAN!", Toast.LENGTH_SHORT).show()
    }

    private fun removeFileFromPool(id: String) {
        mySharedFiles.removeAll { it.id == id }
        val currentList = mySharedFiles.toList()
        httpServer.updateFiles(currentList)
        discovery.updateSharedFiles(currentList)
    }

    private fun clearMyPool() {
        mySharedFiles.clear()
        httpServer.updateFiles(emptyList())
        discovery.updateSharedFiles(emptyList())
        Toast.makeText(this, "Wyczyszczono Twoją pulę.", Toast.LENGTH_SHORT).show()
    }

    private fun getFileInfo(uri: Uri): Pair<String, Long> {
        var name = "plik_${System.currentTimeMillis()}"
        var size = 0L
        try {
            contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (cursor.moveToFirst()) {
                    if (nameIndex != -1) name = cursor.getString(nameIndex) ?: name
                    if (sizeIndex != -1) size = cursor.getLong(sizeIndex)
                }
            }
        } catch (e: Exception) {}
        return Pair(name, size)
    }

    private fun getLocalIp(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (!addr.isLoopbackAddress && addr is Inet4Address) {
                        return addr.hostAddress ?: "127.0.0.1"
                    }
                }
            }
        } catch (e: Exception) {}
        return "LAN"
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun MainAppScreen() {
        val peersState by discovery.peers.collectAsState()
        val transfersState by transfers.collectAsState()
        val scope = rememberCoroutineScope()
        var selectedTab by remember { mutableStateOf(0) }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(AccentGreen)
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "LAN DROP",
                                fontWeight = FontWeight.Black,
                                fontSize = 18.sp,
                                letterSpacing = (-0.5).sp,
                                color = Color.White
                            )
                            Spacer(Modifier.width(12.dp))
                            Text(
                                "${getLocalIp()}:${httpServer.actualPort}",
                                fontSize = 11.sp,
                                color = TextMuted,
                                modifier = Modifier
                                    .border(1.dp, DarkBorder, RoundedCornerShape(6.dp))
                                    .padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = PureBlack,
                        titleContentColor = Color.White
                    )
                )
            },
            bottomBar = {
                NavigationBar(
                    containerColor = PureBlack,
                    modifier = Modifier.border(width = 1.dp, color = DarkBorder)
                ) {
                    NavigationBarItem(
                        selected = selectedTab == 0,
                        onClick = { selectedTab = 0 },
                        icon = { Icon(Icons.Default.CloudUpload, contentDescription = null) },
                        label = { Text("Moja pula (${mySharedFiles.size})", fontWeight = FontWeight.Bold) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color.Black,
                            selectedTextColor = Color.White,
                            indicatorColor = Color.White,
                            unselectedIconColor = TextMuted,
                            unselectedTextColor = TextMuted
                        )
                    )
                    NavigationBarItem(
                        selected = selectedTab == 1,
                        onClick = { selectedTab = 1 },
                        icon = { Icon(Icons.Default.CloudDownload, contentDescription = null) },
                        label = { Text("W sieci (${peersState.values.sumOf { it.files.size }})", fontWeight = FontWeight.Bold) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color.Black,
                            selectedTextColor = Color.White,
                            indicatorColor = Color.White,
                            unselectedIconColor = TextMuted,
                            unselectedTextColor = TextMuted
                        )
                    )
                }
            },
            containerColor = PureBlack
        ) { paddingValues ->
            Box(modifier = Modifier.padding(paddingValues).fillMaxSize()) {
                if (selectedTab == 0) {
                    MyPoolTabContent(
                        onPickGallery = {
                            pickVisualMediaLauncher.launch(
                                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageAndVideo)
                            )
                        },
                        onPickFiles = {
                            openDocumentsLauncher.launch(arrayOf("*/*"))
                        },
                        onClearPool = { clearMyPool() },
                        onRemoveFile = { id -> removeFileFromPool(id) }
                    )
                } else {
                    NetworkPoolTabContent(
                        peers = peersState.values.toList(),
                        transfers = transfersState,
                        onDownloadFile = { item ->
                            scope.launch {
                                downloader.download(item, transfers)
                            }
                        }
                    )
                }
            }
        }
    }

    @Composable
    fun MyPoolTabContent(
        onPickGallery: () -> Unit,
        onPickFiles: () -> Unit,
        onClearPool: () -> Unit,
        onRemoveFile: (String) -> Unit
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            // Przyciski dodawania
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Button(
                    onClick = onPickGallery,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Default.PhotoLibrary, contentDescription = null, tint = Color.Black)
                    Spacer(Modifier.width(8.dp))
                    Text("Z Galerii", color = Color.Black, fontWeight = FontWeight.Bold)
                }

                Button(
                    onClick = onPickFiles,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = DarkCard),
                    border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Default.Folder, contentDescription = null, tint = Color.White)
                    Spacer(Modifier.width(8.dp))
                    Text("Z Plików", color = Color.White, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(Modifier.height(18.dp))

            // Nagłówek sekcji
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "TWOJA WISZĄCA PULA",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                    color = TextMuted
                )
                if (mySharedFiles.isNotEmpty()) {
                    TextButton(onClick = onClearPool) {
                        Text("Wyczyść pulę", color = AccentRed, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            if (mySharedFiles.isEmpty()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(DarkCard)
                        .border(1.dp, DarkBorder, RoundedCornerShape(14.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                        Icon(Icons.Default.UploadFile, contentDescription = null, tint = TextMuted, modifier = Modifier.size(40.dp))
                        Spacer(Modifier.height(10.dp))
                        Text("Pula jest pusta", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Wybierz zdjęcia lub pliki powyżej.\nZawisną w sieci i komputery będą mogły je pobrać.",
                            color = TextMuted,
                            fontSize = 12.sp,
                            lineHeight = 16.sp,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(mySharedFiles, key = { it.id }) { f ->
                        Card(
                            colors = CardDefaults.cardColors(containerColor = DarkCard),
                            shape = RoundedCornerShape(12.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(f.name, fontWeight = FontWeight.SemiBold, maxLines = 1, color = Color.White, fontSize = 14.sp)
                                    Text(formatSize(f.size), fontSize = 12.sp, color = TextMuted)
                                }
                                IconButton(onClick = { onRemoveFile(f.id) }) {
                                    Icon(Icons.Default.Close, contentDescription = "Usuń", tint = TextMuted)
                                }
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(10.dp))
            Text(
                "💡 Pliki znikną z sieci po zamknięciu aplikacji.",
                fontSize = 11.sp,
                color = Color.DarkGray
            )
        }
    }

    @Composable
    fun NetworkPoolTabContent(
        peers: List<com.landrop.pool.model.RemotePeer>,
        transfers: Map<String, TransferState>,
        onDownloadFile: (RemoteFileItem) -> Unit
    ) {
        val allRemoteFiles = remember(peers) {
            val list = mutableListOf<RemoteFileItem>()
            for (p in peers) {
                for (f in p.files) {
                    list.add(
                        RemoteFileItem(
                            id = f.id,
                            name = f.name,
                            size = f.size,
                            peerDeviceId = p.deviceId,
                            peerName = p.deviceName,
                            peerIp = p.ip,
                            peerPort = p.port
                        )
                    )
                }
            }
            list
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            Text(
                "PLIKI WYSTAWIONE PRZEZ KOMPUTERY",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp,
                color = TextMuted
            )

            Spacer(Modifier.height(10.dp))

            // Aktywne pobierania
            if (transfers.isNotEmpty()) {
                for ((_, tr) in transfers) {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DarkCard),
                        shape = RoundedCornerShape(10.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(tr.fileName, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            val pct = if (tr.totalBytes > 0) ((tr.bytesDone.toFloat() / tr.totalBytes) * 100).toInt() else 0
                            LinearProgressIndicator(
                                progress = { if (tr.totalBytes > 0) tr.bytesDone.toFloat() / tr.totalBytes else 0f },
                                modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                                color = AccentGreen,
                                trackColor = DarkCardItem
                            )
                            if (tr.isCompleted) {
                                Text("✅ Zapisano w Downloads/LanDrop", fontSize = 11.sp, color = AccentGreen, fontWeight = FontWeight.Bold)
                            } else if (tr.error != null) {
                                Text("❌ Błąd: ${tr.error}", fontSize = 11.sp, color = AccentRed)
                            } else {
                                Text("${formatSize(tr.bytesDone)} / ${formatSize(tr.totalBytes)} | ${String.format("%.1f", tr.speedMbps)} MB/s ($pct%)", fontSize = 11.sp, color = TextMuted)
                            }
                        }
                    }
                }
            }

            if (allRemoteFiles.isEmpty()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(DarkCard)
                        .border(1.dp, DarkBorder, RoundedCornerShape(14.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                        Icon(Icons.Default.Devices, contentDescription = null, tint = TextMuted, modifier = Modifier.size(40.dp))
                        Spacer(Modifier.height(10.dp))
                        Text("Brak aktywnych plików w sieci", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Uruchom LAN Drop na komputerze i wrzuć pliki do wrzutni.",
                            color = TextMuted,
                            fontSize = 12.sp
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(allRemoteFiles, key = { it.peerDeviceId + it.id }) { item ->
                        Card(
                            colors = CardDefaults.cardColors(containerColor = DarkCard),
                            shape = RoundedCornerShape(12.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(item.name, fontWeight = FontWeight.Bold, maxLines = 1, color = Color.White, fontSize = 14.sp)
                                    Text(
                                        "${formatSize(item.size)} • Z: ${item.peerName}",
                                        fontSize = 12.sp,
                                        color = TextMuted
                                    )
                                }
                                Button(
                                    onClick = { onDownloadFile(item) },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color.White),
                                    shape = RoundedCornerShape(8.dp),
                                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                                ) {
                                    Text("Pobierz", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private fun formatSize(bytes: Long): String {
        var b = bytes.toDouble()
        val units = arrayOf("B", "KB", "MB", "GB", "TB")
        for (u in units) {
            if (b < 1024.0) {
                return if (u == "B") "${bytes} B" else String.format("%.1f %s", b, u)
            }
            b /= 1024.0
        }
        return String.format("%.1f PB", b)
    }

    override fun onDestroy() {
        super.onDestroy()
        discovery.stop()
        httpServer.stop()
    }
}
