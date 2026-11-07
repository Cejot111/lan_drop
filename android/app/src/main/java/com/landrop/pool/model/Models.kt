package com.landrop.pool.model

import android.net.Uri

data class SharedFile(
    val id: String,
    val uri: Uri,
    val name: String,
    val size: Long,
    val mime: String
)

data class RemotePeer(
    val deviceId: String,
    val deviceName: String,
    val ip: String,
    val port: Int,
    val files: List<RemoteFileInfo>,
    val lastSeen: Long = System.currentTimeMillis()
)

data class RemoteFileInfo(
    val id: String,
    val name: String,
    val size: Long
)

data class RemoteFileItem(
    val id: String,
    val name: String,
    val size: Long,
    val peerDeviceId: String,
    val peerName: String,
    val peerIp: String,
    val peerPort: Int
)

data class TransferState(
    val fileId: String,
    val fileName: String,
    val bytesDone: Long = 0,
    val totalBytes: Long = 0,
    val speedMbps: Double = 0.0,
    val isCompleted: Boolean = false,
    val error: String? = null
)
