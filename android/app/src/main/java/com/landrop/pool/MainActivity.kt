package com.landrop.pool

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
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
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.ExperimentalFoundationApi
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

        // Start rozgłaszania LAN (UDP Broadcast + Unicast + TCP polling)
        discovery = LanDiscovery(this, deviceId, deviceName, port)
        discovery.start()

        // Obsługa intencji udostępniania z menu systemowego Androida
        handleIncomingIntent(intent)

        setContent {
            LanDropTheme {
                MainAppScreen()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingIntent(intent)
    }

    private fun handleIncomingIntent(intent: Intent?) {
        if (intent == null) return
        val action = intent.action
        val type = intent.type

        if (Intent.ACTION_SEND == action && type != null) {
            val extraText = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (extraText != null && extraText.isNotBlank()) {
                addLinkOrTextToPool(extraText)
            } else {
                val uri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
                }
                if (uri != null) {
                    addUrisToPool(listOf(uri))
                }
            }
        } else if (Intent.ACTION_SEND_MULTIPLE == action && type != null) {
            val uris = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)
            }
            if (!uris.isNullOrEmpty()) {
                addUrisToPool(uris)
            }
        }
    }

    private fun addLinkOrTextToPool(rawText: String) {
        val trimmed = rawText.trim()
        val urlRegex = "(https?://[^\\s]+)".toRegex()
        val match = urlRegex.find(trimmed)
        val finalUrl = match?.value ?: trimmed

        val item = SharedFile(
            id = UUID.randomUUID().toString(),
            uri = null,
            name = finalUrl,
            size = finalUrl.toByteArray(Charsets.UTF_8).size.toLong(),
            mime = "text/x-uri",
            type = "link",
            content = finalUrl
        )
        mySharedFiles.add(item)
        val currentList = mySharedFiles.toList()
        httpServer.updateFiles(currentList)
        discovery.updateSharedFiles(currentList)

        Toast.makeText(this, "Dodano link do puli LAN!", Toast.LENGTH_SHORT).show()
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
                mime = mime,
                type = "file",
                content = null
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

    private fun openLinkInBrowser(rawUrl: String) {
        val target = if (!rawUrl.startsWith("http://") && !rawUrl.startsWith("https://")) {
            "https://$rawUrl"
        } else {
            rawUrl
        }
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target))
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Nie można otworzyć linku: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun copyToClipboard(text: String, label: String = "Link") {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText(label, text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(this, "Skopiowano do schowka: $text", Toast.LENGTH_SHORT).show()
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun MainAppScreen() {
        val peersState by discovery.peers.collectAsState()
        val transfersState by transfers.collectAsState()
        val scope = rememberCoroutineScope()
        var selectedTab by remember { mutableStateOf(0) }
        var showAddLinkDialog by remember { mutableStateOf(false) }

        if (showAddLinkDialog) {
            var urlInput by remember { mutableStateOf("") }
            AlertDialog(
                onDismissRequest = { showAddLinkDialog = false },
                containerColor = DarkCard,
                title = {
                    Text("Udostępnij link WWW", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                },
                text = {
                    Column {
                        Text(
                            "Wpisz lub wklej adres strony. Pojawi się w puli komputerów z przyciskiem do natychmiastowego otwarcia.",
                            color = TextMuted,
                            fontSize = 12.sp,
                            lineHeight = 16.sp
                        )
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = urlInput,
                            onValueChange = { urlInput = it },
                            placeholder = { Text("https://...", color = TextMuted) },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White,
                                focusedBorderColor = Color.White,
                                unfocusedBorderColor = DarkBorder,
                                cursorColor = Color.White
                            ),
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            if (urlInput.isNotBlank()) {
                                addLinkOrTextToPool(urlInput)
                                showAddLinkDialog = false
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color.White)
                    ) {
                        Text("Dodaj", color = Color.Black, fontWeight = FontWeight.Bold)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showAddLinkDialog = false }) {
                        Text("Anuluj", color = TextMuted)
                    }
                }
            )
        }

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
                        onAddLink = { showAddLinkDialog = true },
                        onClearPool = { clearMyPool() },
                        onRemoveFile = { id -> removeFileFromPool(id) }
                    )
                } else {
                    NetworkPoolTabContent(
                        peers = peersState.values.toList(),
                        transfers = transfersState,
                        onOpenLink = { url -> openLinkInBrowser(url) },
                        onCopyLink = { url -> copyToClipboard(url) },
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
        onAddLink: () -> Unit,
        onClearPool: () -> Unit,
        onRemoveFile: (String) -> Unit
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            // Przyciski dodawania (Galeria, Pliki, Link)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(
                    onClick = onPickGallery,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White),
                    shape = RoundedCornerShape(10.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp)
                ) {
                    Icon(Icons.Default.PhotoLibrary, contentDescription = null, tint = Color.Black, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Galeria", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }

                Button(
                    onClick = onPickFiles,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = DarkCard),
                    border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder),
                    shape = RoundedCornerShape(10.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp)
                ) {
                    Icon(Icons.Default.Folder, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Pliki", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }

                Button(
                    onClick = onAddLink,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = DarkCard),
                    border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder),
                    shape = RoundedCornerShape(10.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp)
                ) {
                    Icon(Icons.Default.Link, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Link", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            }

            Spacer(Modifier.height(16.dp))

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
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Wybierz pliki/link powyżej lub udostępnij bezpośrednio z innej aplikacji (menu Udostępnij -> LAN Drop).",
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
                                Row(
                                    modifier = Modifier.weight(1f),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = if (f.type == "link") Icons.Default.Link else Icons.Default.InsertDriveFile,
                                        contentDescription = null,
                                        tint = if (f.type == "link") AccentGreen else TextMuted,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.width(12.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(f.name, fontWeight = FontWeight.SemiBold, maxLines = 1, color = Color.White, fontSize = 14.sp)
                                        Text(
                                            if (f.type == "link") "Link WWW" else formatSize(f.size),
                                            fontSize = 12.sp,
                                            color = TextMuted
                                        )
                                    }
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
                "💡 Pliki i linki wiszą w sieci dopóki nie zamkniesz aplikacji.",
                fontSize = 11.sp,
                color = Color.DarkGray
            )
        }
    }

    @OptIn(ExperimentalFoundationApi::class)
    @Composable
    fun NetworkPoolTabContent(
        peers: List<com.landrop.pool.model.RemotePeer>,
        transfers: Map<String, TransferState>,
        onOpenLink: (String) -> Unit,
        onCopyLink: (String) -> Unit,
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
                            peerPort = p.port,
                            type = f.type,
                            content = f.content
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
                "ELEMENTY WYSTAWIONE PRZEZ KOMPUTERY",
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
                            "Uruchom LAN Drop na komputerze i wrzuć pliki lub linki do wrzutni.",
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
                        val isLink = item.type == "link"
                        val linkUrl = item.content ?: item.name

                        Card(
                            colors = CardDefaults.cardColors(containerColor = DarkCard),
                            shape = RoundedCornerShape(12.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder),
                            modifier = Modifier.combinedClickable(
                                onClick = {
                                    if (isLink) onOpenLink(linkUrl) else onDownloadFile(item)
                                },
                                onLongClick = {
                                    if (isLink) onCopyLink(linkUrl)
                                }
                            )
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(
                                    modifier = Modifier.weight(1f),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = if (isLink) Icons.Default.Link else Icons.Default.InsertDriveFile,
                                        contentDescription = null,
                                        tint = if (isLink) AccentGreen else TextMuted,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.width(12.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(item.name, fontWeight = FontWeight.Bold, maxLines = 1, color = Color.White, fontSize = 14.sp)
                                        Text(
                                            if (isLink) "Link WWW • Z: ${item.peerName}" else "${formatSize(item.size)} • Z: ${item.peerName}",
                                            fontSize = 12.sp,
                                            color = TextMuted
                                        )
                                    }
                                }

                                if (isLink) {
                                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        IconButton(
                                            onClick = { onCopyLink(linkUrl) },
                                            modifier = Modifier.size(36.dp)
                                        ) {
                                            Icon(Icons.Default.ContentCopy, contentDescription = "Kopiuj", tint = TextMuted, modifier = Modifier.size(18.dp))
                                        }
                                        Button(
                                            onClick = { onOpenLink(linkUrl) },
                                            colors = ButtonDefaults.buttonColors(containerColor = Color.White),
                                            shape = RoundedCornerShape(8.dp),
                                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                                        ) {
                                            Text("Otwórz", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                        }
                                    }
                                } else {
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
