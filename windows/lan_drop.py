#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN Drop Pool - Aplikacja do szybkiej wymiany plików w sieci lokalnej (LAN / Wi-Fi).
Stylistyka: Pure Black (OLED / Stealth Dark), zero zbędnych funkcji, maksymalna wydajność.
"""

import sys
import os
import time
import uuid
import json
import socket
import mimetypes
import threading
import subprocess
import io
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

import qrcode
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QDragEnterEvent, QDropEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFileDialog, QMessageBox, QSplitter, QFrame,
    QScrollArea, QSizePolicy, QInputDialog, QDialog
)

BROADCAST_PORT = 45454
DEFAULT_HTTP_PORT = 50505
APP_NAME = "LAN DROP"

def format_size(bytes_num):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != 'B' else f"{bytes_num} B"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('1.1.1.1', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_download_folder():
    dl_path = Path.home() / "Downloads" / "LanDrop"
    dl_path.mkdir(parents=True, exist_ok=True)
    return dl_path


# =====================================================================
# MOBILNA STRONA WWW (TRYB 1: SZYBKI ZRZUT DLA DOWOLNEGO TELEFONU)
# =====================================================================

MOBILE_WEB_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>LAN Drop Pool</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #000000;
    color: #ffffff;
    margin: 0;
    padding: 20px 16px;
    line-height: 1.4;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 1px solid #1c1c1f;
  }
  .logo { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
  .badge {
    background: #18181b;
    border: 1px solid #27272a;
    color: #10b981;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
  }
  .card {
    background: #09090b;
    border: 1px solid #27272a;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .card-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #a1a1aa;
    margin-bottom: 14px;
  }
  .btn-upload-wrap {
    position: relative;
    overflow: hidden;
    display: block;
    width: 100%;
  }
  .btn-upload {
    background: #ffffff;
    color: #000000;
    font-weight: 700;
    font-size: 15px;
    padding: 16px;
    border-radius: 12px;
    border: none;
    width: 100%;
    text-align: center;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .btn-upload-wrap input[type=file] {
    position: absolute;
    left: 0;
    top: 0;
    opacity: 0;
    width: 100%;
    height: 100%;
    cursor: pointer;
  }
  .progress-wrap {
    background: #18181b;
    border-radius: 8px;
    height: 8px;
    margin-top: 14px;
    overflow: hidden;
    display: none;
  }
  .progress-fill {
    background: #10b981;
    height: 100%;
    width: 0%;
    transition: width 0.2s ease;
  }
  .status-msg {
    font-size: 12px;
    color: #a1a1aa;
    margin-top: 8px;
    font-weight: 500;
  }
  .file-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #121214;
    border: 1px solid #27272a;
    padding: 14px 16px;
    border-radius: 12px;
    margin-bottom: 10px;
  }
  .file-name {
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
    word-break: break-all;
  }
  .file-size {
    font-size: 12px;
    color: #71717a;
    margin-top: 2px;
  }
  .btn-dl {
    background: #27272a;
    color: #ffffff;
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #3f3f46;
    white-space: nowrap;
    margin-left: 12px;
  }
  .empty-note {
    text-align: center;
    padding: 30px 10px;
    color: #52525b;
    font-size: 13px;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="logo">⚡ LAN DROP</div>
    <div class="badge">POŁĄCZONO</div>
  </div>

  <div class="card">
    <div class="card-title">Wyślij pliki do komputera</div>
    <div class="btn-upload-wrap">
      <button class="btn-upload">Wybierz z Galerii / Plików</button>
      <input type="file" id="fileIn" multiple onchange="upload(this.files)">
    </div>
    <div class="progress-wrap" id="pWrap">
      <div class="progress-fill" id="pFill"></div>
    </div>
    <div class="status-msg" id="statusMsg"></div>
  </div>

  <div class="card">
    <div class="card-title">Pliki wystawione na komputerze</div>
    <div id="fileContainer">
      <div class="empty-note">Ładowanie puli...</div>
    </div>
  </div>

  <script>
    function fmt(b) {
      if (b === 0) return '0 B';
      const k = 1024, s = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(b) / Math.log(k));
      return (b / Math.pow(k, i)).toFixed(1) + ' ' + s[i];
    }

    async function fetchPool() {
      try {
        const res = await fetch('/api/pool');
        const data = await res.json();
        const box = document.getElementById('fileContainer');
        if (!data.files || data.files.length === 0) {
          box.innerHTML = '<div class="empty-note">Pula komputera jest pusta.<br>Przeciągnij pliki do programu na komputerze.</div>';
          return;
        }
        let html = '';
        for (let f of data.files) {
          html += '<div class="file-item"><div><div class="file-name">' + f.name + '</div><div class="file-size">' + fmt(f.size) + '</div></div><a class="btn-dl" href="/api/download/' + f.id + '" download="' + f.name + '">Pobierz</a></div>';
        }
        box.innerHTML = html;
      } catch (e) {
        document.getElementById('fileContainer').innerHTML = '<div class="empty-note">Brak połączenia z komputerem.</div>';
      }
    }

    async function upload(files) {
      if (!files || files.length === 0) return;
      const pWrap = document.getElementById('pWrap');
      const pFill = document.getElementById('pFill');
      const msg = document.getElementById('statusMsg');
      pWrap.style.display = 'block';

      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        msg.innerText = 'Wysyłanie (' + (i+1) + '/' + files.length + '): ' + f.name + '...';
        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', '/api/upload?filename=' + encodeURIComponent(f.name));
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const pct = (e.loaded / e.total) * 100;
              pFill.style.width = pct + '%';
            }
          };
          xhr.onload = () => xhr.status === 200 ? resolve() : reject();
          xhr.onerror = () => reject();
          xhr.send(f);
        });
      }
      pFill.style.width = '100%';
      msg.innerText = 'Przesłano ' + files.length + ' plik(ów) do folderu Pobrane na komputerze!';
      setTimeout(() => { pWrap.style.display = 'none'; }, 3500);
      document.getElementById('fileIn').value = '';
    }

    fetchPool();
    setInterval(fetchPool, 2500);
  </script>
</body>
</html>
"""


# =====================================================================
# PULA PLIKÓW I SERWER HTTP
# =====================================================================

class SharedItem:
    def __init__(self, file_path: str):
        self.path = os.path.abspath(file_path)
        self.name = os.path.basename(self.path)
        self.size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        self.id = str(uuid.uuid4())
        mime, _ = mimetypes.guess_type(self.path)
        self.mime = mime or "application/octet-stream"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "mime": self.mime
        }

class PoolManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.files = {}
        self.version = 1

    def add_files(self, paths):
        added = []
        with self.lock:
            for p in paths:
                if os.path.isfile(p):
                    if not any(item.path == os.path.abspath(p) for item in self.files.values()):
                        item = SharedItem(p)
                        self.files[item.id] = item
                        added.append(item)
            if added:
                self.version += 1
        return added

    def remove_file(self, file_id):
        with self.lock:
            if file_id in self.files:
                del self.files[file_id]
                self.version += 1
                return True
        return False

    def clear(self):
        with self.lock:
            if self.files:
                self.files.clear()
                self.version += 1

    def get_list(self):
        with self.lock:
            return [item.to_dict() for item in self.files.values()]

    def get_item(self, file_id):
        with self.lock:
            return self.files.get(file_id)

    def count(self):
        with self.lock:
            return len(self.files)

    def total_size(self):
        with self.lock:
            return sum(item.size for item in self.files.values())


class HttpFileHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        pool = self.server.pool_manager
        path = unquote(self.path)

        if path == "/" or path == "/index.html":
            body = MOBILE_WEB_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/pool" or path == "/api/pool/":
            data = {
                "deviceId": self.server.device_id,
                "deviceName": self.server.device_name,
                "version": pool.version,
                "files": pool.get_list()
            }
            body = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/api/download/"):
            file_id = path[len("/api/download/"):].split("?")[0].strip("/")
            item = pool.get_item(file_id)
            if not item or not os.path.exists(item.path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Plik nie istnieje lub zostal usuniety z puli.")
                return

            try:
                file_size = os.path.getsize(item.path)
                self.send_response(200)
                self.send_header("Content-Type", item.mime)
                self.send_header("Content-Length", str(file_size))
                safe_name = item.name.replace('"', '\\"')
                self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                with open(item.path, "rb") as f:
                    while chunk := f.read(512 * 1024):
                        self.wfile.write(chunk)
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                print(f"[HTTP] Blad strumieniowania: {e}")
            return

        if path == "/api/ping":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            qs = parse_qs(parsed.query)
            filename = qs.get("filename", ["plik_" + str(int(time.time()))])[0]
            filename = os.path.basename(filename)
            dest_dir = get_download_folder()
            save_path = dest_dir / filename
            counter = 1
            stem = save_path.stem
            suf = save_path.suffix
            while save_path.exists():
                save_path = dest_dir / f"{stem}_{counter}{suf}"
                counter += 1

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                remaining = content_length
                with open(save_path, "wb") as f:
                    while remaining > 0:
                        chunk = self.rfile.read(min(remaining, 512 * 1024))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)

                if hasattr(self.server, "on_file_received") and self.server.on_file_received:
                    self.server.on_file_received(str(save_path))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()


class LocalServer:
    def __init__(self, pool_manager, device_id, device_name, port=DEFAULT_HTTP_PORT):
        self.pool = pool_manager
        self.device_id = device_id
        self.device_name = device_name
        self.port = port
        self.server = None
        self.thread = None
        self.on_file_received = None

    def start(self):
        for p in range(self.port, self.port + 50):
            try:
                self.server = ThreadingHTTPServer(('0.0.0.0', p), HttpFileHandler)
                self.server.pool_manager = self.pool
                self.server.device_id = self.device_id
                self.server.device_name = self.device_name
                self.server.on_file_received = self.on_file_received
                self.port = p
                break
            except OSError:
                continue

        if not self.server:
            raise RuntimeError("Nie udalo sie powiazac serwera HTTP!")

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# =====================================================================
# SYSTEM ODKRYWANIA URZĄDZEŃ W SIECI (UDP BROADCAST)
# =====================================================================

class LanDiscovery(QThread):
    peers_updated = pyqtSignal(dict)

    def __init__(self, device_id, device_name, http_port, pool_manager):
        super().__init__()
        self.device_id = device_id
        self.device_name = device_name
        self.http_port = http_port
        self.pool = pool_manager
        self.running = True
        self.peers = {}
        self.lock = threading.Lock()

    def run(self):
        rx_thread = threading.Thread(target=self._listen_loop, daemon=True)
        rx_thread.start()

        while self.running:
            self._send_beacon("beacon")
            self._prune_peers()
            time.sleep(2)

    def _get_broadcast_addresses(self):
        addresses = ['255.255.255.255']
        local_ip = get_local_ip()
        parts = local_ip.split('.')
        if len(parts) == 4 and parts[0] != '127':
            addresses.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        return list(set(addresses))

    def _send_beacon(self, msg_type="beacon"):
        payload = {
            "type": msg_type,
            "deviceId": self.device_id,
            "deviceName": self.device_name,
            "platform": "windows",
            "port": self.http_port,
            "version": self.pool.version,
            "files": self.pool.get_list()
        }
        data = json.dumps(payload).encode('utf-8')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)

        for bcast_ip in self._get_broadcast_addresses():
            try:
                sock.sendto(data, (bcast_ip, BROADCAST_PORT))
            except Exception:
                pass
        sock.close()

    def send_farewell(self):
        payload = {"type": "farewell", "deviceId": self.device_id}
        data = json.dumps(payload).encode('utf-8')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for bcast_ip in self._get_broadcast_addresses():
            try:
                sock.sendto(data, (bcast_ip, BROADCAST_PORT))
            except Exception:
                pass
        sock.close()

    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', BROADCAST_PORT))
        except Exception:
            return

        sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = sock.recvfrom(65535)
                sender_ip = addr[0]
                msg = json.loads(data.decode('utf-8'))
                peer_id = msg.get("deviceId")
                if not peer_id or peer_id == self.device_id:
                    continue

                msg_type = msg.get("type", "beacon")
                with self.lock:
                    if msg_type == "farewell":
                        if peer_id in self.peers:
                            del self.peers[peer_id]
                            self.peers_updated.emit(dict(self.peers))
                    else:
                        self.peers[peer_id] = {
                            "last_seen": time.time(),
                            "ip": sender_ip,
                            "deviceName": msg.get("deviceName", f"Urządzenie ({sender_ip})"),
                            "platform": msg.get("platform", "unknown"),
                            "port": msg.get("port", DEFAULT_HTTP_PORT),
                            "version": msg.get("version", 1),
                            "files": msg.get("files", [])
                        }
                        self.peers_updated.emit(dict(self.peers))
            except socket.timeout:
                continue
            except Exception:
                continue
        sock.close()

    def add_manual_peer(self, ip, port=DEFAULT_HTTP_PORT):
        def _fetch():
            try:
                req = urllib.request.Request(f"http://{ip}:{port}/api/pool")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    pid = data.get("deviceId", ip)
                    with self.lock:
                        self.peers[pid] = {
                            "last_seen": time.time(),
                            "ip": ip,
                            "deviceName": data.get("deviceName", f"Urządzenie ({ip})"),
                            "platform": "manual",
                            "port": port,
                            "version": data.get("version", 1),
                            "files": data.get("files", []),
                            "is_manual": True
                        }
                        self.peers_updated.emit(dict(self.peers))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _prune_peers(self):
        now = time.time()
        changed = False
        with self.lock:
            to_delete = []
            for pid, peer in self.peers.items():
                if peer.get("is_manual"):
                    if now - peer["last_seen"] > 3.0:
                        peer["last_seen"] = now
                        self.add_manual_peer(peer["ip"], peer.get("port", DEFAULT_HTTP_PORT))
                    continue
                if now - peer["last_seen"] > 6.0:
                    to_delete.append(pid)
            for pid in to_delete:
                del self.peers[pid]
                changed = True

        if changed:
            with self.lock:
                self.peers_updated.emit(dict(self.peers))

    def stop(self):
        self.running = False
        self.send_farewell()
        self.wait(1000)


# =====================================================================
# WĄTEK POBIERANIA PLIKÓW
# =====================================================================

class DownloadWorker(QThread):
    progress = pyqtSignal(str, int, int, float)
    finished = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(self, file_id, file_name, file_size, host_ip, host_port):
        super().__init__()
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.host_ip = host_ip
        self.host_port = host_port
        self.dest_dir = get_download_folder()

    def run(self):
        url = f"http://{self.host_ip}:{self.host_port}/api/download/{self.file_id}"
        save_path = self.dest_dir / self.file_name
        counter = 1
        base_stem = save_path.stem
        suffix = save_path.suffix
        while save_path.exists():
            save_path = self.dest_dir / f"{base_stem}_{counter}{suffix}"
            counter += 1

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp, open(save_path, "wb") as out_file:
                total_bytes = int(resp.headers.get("Content-Length", self.file_size))
                downloaded = 0
                chunk_size = 512 * 1024
                start_time = time.time()
                last_time = start_time
                last_bytes = 0

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed = now - last_time
                    if elapsed >= 0.2:
                        speed_mbps = ((downloaded - last_bytes) / (1024 * 1024)) / elapsed
                        last_time = now
                        last_bytes = downloaded
                        self.progress.emit(self.file_id, downloaded, total_bytes, speed_mbps)

                total_elapsed = max(0.001, time.time() - start_time)
                avg_speed = (downloaded / (1024 * 1024)) / total_elapsed
                self.progress.emit(self.file_id, downloaded, total_bytes, avg_speed)
                self.finished.emit(self.file_id, str(save_path))
        except Exception as e:
            if save_path.exists() and save_path.stat().st_size == 0:
                try:
                    save_path.unlink()
                except Exception:
                    pass
            self.failed.emit(self.file_id, str(e))


# =====================================================================
# OBSŁUGA HOTSPOTU WINDOWS
# =====================================================================

class HotspotWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, action="info"):
        super().__init__()
        self.action = action

    def run(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotspot_helper.ps1")
        if not os.path.exists(script_path):
            self.finished.emit({"status": "error", "error": "Brak skryptu hotspot_helper.ps1"})
            return

        try:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Action", self.action]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            lines = res.stdout.strip().splitlines()
            data = {"status": "ok", "action": self.action}
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip().upper()] = v.strip()
            self.finished.emit(data)
        except Exception as e:
            self.finished.emit({"status": "error", "error": str(e), "action": self.action})


class HotspotDialog(QDialog):
    def __init__(self, ssid, password, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hotspot Wi-Fi")
        self.setFixedSize(400, 520)
        self.setStyleSheet("background-color: #000000; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("HOTSPOT WI-FI")
        title.setStyleSheet("font-size: 16px; font-weight: 800; letter-spacing: 0.5px; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel("Skieruj aparat telefonu na kod QR, aby połączyć:")
        info.setStyleSheet("font-size: 12px; color: #a1a1aa;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(f"WIFI:S:{ssid};T:WPA;P:{password};;")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            qr_label.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            qr_label.setText(f"[Błąd QR: {e}]")
        layout.addWidget(qr_label)

        box = QFrame()
        box.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 10px; padding: 12px;")
        b_lay = QVBoxLayout(box)
        b_lay.setSpacing(4)

        s_lbl = QLabel(f"Sieć: <b>{ssid}</b>")
        s_lbl.setStyleSheet("font-size: 13px; color: #ffffff;")
        p_lbl = QLabel(f"Hasło: <b style='color:#10b981; font-family: monospace;'>{password}</b>")
        p_lbl.setStyleSheet("font-size: 13px;")

        b_lay.addWidget(s_lbl)
        b_lay.addWidget(p_lbl)
        layout.addWidget(box)

        btn_box = QHBoxLayout()
        copy_btn = QPushButton("Kopiuj hasło")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #27272a;
                padding: 10px 16px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #27272a; }
        """)
        copy_btn.clicked.connect(lambda: self.copy_password(password))

        close_btn = QPushButton("Zamknij")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 700;
                border: none;
            }
            QPushButton:hover { background-color: #e4e4e7; }
        """)
        close_btn.clicked.connect(self.accept)

        btn_box.addWidget(copy_btn)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def copy_password(self, password):
        QApplication.clipboard().setText(password)
        QMessageBox.information(self, "Hasło", "Hasło zostało skopiowane do schowka.")


# =====================================================================
# WIDŻET WRZUTNI DRAG & DROP
# =====================================================================

class DropZoneWidget(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 36, 20, 36)
        layout.setSpacing(8)

        self.icon_label = QLabel("📥")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 38px; background: transparent;")

        self.text_label = QLabel("PRZECIĄGNIJ I UPUSZĆ PLIKI")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 800; letter-spacing: 0.5px; color: #ffffff; background: transparent;")

        self.sub_label = QLabel("Pliki zawisną w sieci i będą widoczne dla innych komputerów i telefonu")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("font-size: 12px; color: #71717a; background: transparent;")

        self.browse_btn = QPushButton("Wybierz pliki...")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                font-weight: 700;
                font-size: 13px;
                padding: 10px 22px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover { background-color: #e4e4e7; }
        """)
        self.browse_btn.clicked.connect(self.choose_files)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.sub_label)
        layout.addSpacing(6)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.set_idle_style()

    def set_idle_style(self):
        self.setStyleSheet("""
            #DropZone {
                background-color: #09090b;
                border: 2px dashed #27272a;
                border-radius: 14px;
            }
        """)

    def set_hover_style(self):
        self.setStyleSheet("""
            #DropZone {
                background-color: #121214;
                border: 2px dashed #10b981;
                border-radius: 14px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_hover_style()

    def dragLeaveEvent(self, event):
        self.set_idle_style()

    def dropEvent(self, event: QDropEvent):
        self.set_idle_style()
        urls = event.mimeData().urls()
        paths = []
        for u in urls:
            lp = u.toLocalFile()
            if os.path.isfile(lp):
                paths.append(lp)
            elif os.path.isdir(lp):
                for root, _, files in os.walk(lp):
                    for f in files:
                        paths.append(os.path.join(root, f))
        if paths:
            self.files_dropped.emit(paths)

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Wybierz pliki do udostępnienia")
        if files:
            self.files_dropped.emit(files)


# =====================================================================
# GŁÓWNE OKNO APLIKACJI (PURE BLACK STEALTH DESIGN)
# =====================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1120, 740)
        self.setMinimumSize(920, 600)

        self.device_id = str(uuid.uuid4())[:8]
        self.hostname = socket.gethostname()
        self.device_name = f"{self.hostname} (PC)"
        self.local_ip = get_local_ip()

        self.hotspot_active = False
        self.hotspot_started_by_us = False
        self.hotspot_worker = None
        self.active_downloads = {}

        self.pool = PoolManager()
        self.server = LocalServer(self.pool, self.device_id, self.device_name)
        self.server.on_file_received = self.on_web_file_received
        self.server.start()

        self.discovery = LanDiscovery(self.device_id, self.device_name, self.server.port, self.pool)
        self.discovery.peers_updated.connect(self.on_peers_updated)
        self.discovery.start()

        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 1. Pasek górny (Dashboard Header)
        header = QFrame()
        header.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 12px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)
        h_layout.setSpacing(14)

        # Logo i status
        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet("color: #10b981; font-size: 16px;")
        app_title = QLabel("LAN DROP")
        app_title.setStyleSheet("font-size: 17px; font-weight: 900; letter-spacing: -0.5px; color: #ffffff;")
        title_box.addWidget(dot)
        title_box.addWidget(app_title)

        self.ip_badge = QLabel(f"{self.local_ip}:{self.server.port}")
        self.ip_badge.setStyleSheet("background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 12px;")
        title_box.addWidget(self.ip_badge)

        self.peers_badge = QLabel("Urządzenia: 0")
        self.peers_badge.setStyleSheet("background-color: #18181b; color: #71717a; border: 1px solid #27272a; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;")
        title_box.addWidget(self.peers_badge)

        h_layout.addLayout(title_box)
        h_layout.addStretch()

        # Przyciski akcji (proste, czytelne, nieucięte)
        actions = QHBoxLayout()
        actions.setSpacing(8)

        # Przycisk: Szybki zrzut WWW (QR dla każdego telefonu)
        self.web_btn = QPushButton("📱 Szybki zrzut (QR)")
        self.web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.web_btn.setToolTip("Otwórz wrzutnię na telefonie przez przeglądarkę bez instalowania aplikacji")
        self.web_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #3f3f46;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272a; border-color: #52525b; }
        """)
        self.web_btn.clicked.connect(self.show_web_dialog)
        actions.addWidget(self.web_btn)

        # Przycisk: Włącz Hotspot
        self.hotspot_btn = QPushButton("📶 Hotspot Wi-Fi")
        self.hotspot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_hotspot_btn_idle()
        self.hotspot_btn.clicked.connect(self.toggle_hotspot)
        actions.addWidget(self.hotspot_btn)

        # Przycisk: Otwórz pobrane
        dl_btn = QPushButton("📂 Pobrane")
        dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dl_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #27272a;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272a; }
        """)
        dl_btn.clicked.connect(self.open_downloads_folder)
        actions.addWidget(dl_btn)

        h_layout.addLayout(actions)
        main_layout.addWidget(header)

        # 2. Główny podział (Splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)

        # PANEL LEWY: TWOJA PULA
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #000000; border: 1px solid #1f1f23; border-radius: 14px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_head = QHBoxLayout()
        l_title = QLabel("TWOJA PULA")
        l_title.setStyleSheet("font-size: 12px; font-weight: 800; letter-spacing: 1px; color: #ffffff;")
        left_head.addWidget(l_title)
        left_head.addStretch()
        left_layout.addLayout(left_head)

        # Strefa DropZone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self.add_files_to_pool)
        left_layout.addWidget(self.drop_zone)

        # Tabela plików
        self.my_table = QTableWidget(0, 3)
        self.my_table.setHorizontalHeaderLabels(["Nazwa pliku", "Rozmiar", ""])
        self.my_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.my_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.my_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.my_table.verticalHeader().setVisible(False)
        self.my_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        left_layout.addWidget(self.my_table)

        # Pasek podsumowania lewego panelu
        left_foot = QHBoxLayout()
        self.my_summary_lbl = QLabel("W puli: 0 plików")
        self.my_summary_lbl.setStyleSheet("color: #71717a; font-size: 12px; font-weight: 500;")

        self.clear_my_pool_btn = QPushButton("Wyczyść pulę")
        self.clear_my_pool_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_my_pool_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ef4444;
                border: 1px solid #27272a;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #27272a; border-color: #ef4444; }
        """)
        self.clear_my_pool_btn.clicked.connect(self.clear_my_pool)

        left_foot.addWidget(self.my_summary_lbl)
        left_foot.addStretch()
        left_foot.addWidget(self.clear_my_pool_btn)
        left_layout.addLayout(left_foot)

        # PANEL PRAWY: PLIKI W SIECI
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #000000; border: 1px solid #1f1f23; border-radius: 14px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        right_head = QHBoxLayout()
        r_title = QLabel("PLIKI W SIECI (Z TELEFONU / INNYCH PC)")
        r_title.setStyleSheet("font-size: 12px; font-weight: 800; letter-spacing: 1px; color: #ffffff;")
        right_head.addWidget(r_title)
        right_head.addStretch()
        right_layout.addLayout(right_head)

        # Tabela sieciowa
        self.net_table = QTableWidget(0, 4)
        self.net_table.setHorizontalHeaderLabels(["Urządzenie", "Nazwa pliku", "Rozmiar", "Akcja"])
        self.net_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.net_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.net_table)

        # Kontener na postęp pobierania
        self.transfers_box = QVBoxLayout()
        self.transfers_box.setSpacing(6)
        right_layout.addLayout(self.transfers_box)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([520, 600])
        main_layout.addWidget(splitter, 1)

        # 3. Pasek statusu
        status_bar = QHBoxLayout()
        self.status_lbl = QLabel("Gotowy. Przeciągnij pliki do lewego panelu.")
        self.status_lbl.setStyleSheet("color: #71717a; font-size: 12px;")
        status_bar.addWidget(self.status_lbl)
        status_bar.addStretch()

        tip_lbl = QLabel("Pliki znikną z sieci po zamknięciu programu")
        tip_lbl.setStyleSheet("color: #52525b; font-size: 11px;")
        status_bar.addWidget(tip_lbl)

        main_layout.addLayout(status_bar)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
            }
            QTableWidget {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 8px;
                color: #ffffff;
                gridline-color: #1f1f23;
                selection-background-color: #18181b;
            }
            QHeaderView::section {
                background-color: #121214;
                color: #71717a;
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 8px 10px;
                border: none;
                border-bottom: 1px solid #27272a;
            }
            QScrollBar:vertical {
                border: none;
                background: #000000;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #27272a;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QSplitter::handle {
                background-color: #000000;
            }
        """)

    # =================================================================
    # HOTSPOT WI-FI
    # =================================================================

    def set_hotspot_btn_idle(self):
        self.hotspot_btn.setText("📶 Hotspot Wi-Fi")
        self.hotspot_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #27272a;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272a; }
        """)

    def set_hotspot_btn_active(self):
        self.hotspot_btn.setText("⏹️ Wyłącz Hotspot")
        self.hotspot_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)

    def toggle_hotspot(self):
        if not self.hotspot_active:
            self.hotspot_btn.setEnabled(False)
            self.hotspot_btn.setText("Włączanie...")
            self.status_lbl.setText("Uruchamianie punktu dostępu Wi-Fi w laptopie...")
            self.hotspot_worker = HotspotWorker("start")
            self.hotspot_worker.finished.connect(self.on_hotspot_started)
            self.hotspot_worker.start()
        else:
            self.hotspot_btn.setEnabled(False)
            self.hotspot_btn.setText("Wyłączanie...")
            self.status_lbl.setText("Wyłączanie punktu dostępu...")
            self.hotspot_worker = HotspotWorker("stop")
            self.hotspot_worker.finished.connect(self.on_hotspot_stopped)
            self.hotspot_worker.start()

    def on_hotspot_started(self, data):
        self.hotspot_btn.setEnabled(True)
        if data.get("status") == "ok" and (data.get("RESULT") == "SUCCESS" or "SSID" in data):
            self.hotspot_active = True
            self.hotspot_started_by_us = True
            self.set_hotspot_btn_active()
            ssid = data.get("SSID", "LAN-Drop-Laptop")
            password = data.get("PASSWORD", "")
            self.status_lbl.setText(f"Hotspot aktywny: {ssid}. Wi-Fi uczelni nadal działa na laptopie.")
            dlg = HotspotDialog(ssid, password, self)
            dlg.exec()
        else:
            self.set_hotspot_btn_idle()
            err = data.get("error") or data.get("RESULT", "Nieznany błąd")
            QMessageBox.warning(self, "Hotspot", f"Nie udało się uruchomić hotspotu.\nSzczegóły: {err}")
            self.status_lbl.setText("Błąd uruchamiania hotspotu.")

    def on_hotspot_stopped(self, data):
        self.hotspot_btn.setEnabled(True)
        self.hotspot_active = False
        self.hotspot_started_by_us = False
        self.set_hotspot_btn_idle()
        self.status_lbl.setText("Hotspot laptopa został wyłączony.")

    # =================================================================
    # SZYBKI ZRZUT (QR KOD DLA PRZEGLĄDARKI TELEFONU)
    # =================================================================

    def show_web_dialog(self):
        url = f"http://{self.local_ip}:{self.server.port}"
        dlg = QDialog(self)
        dlg.setWindowTitle("Szybki zrzut - Telefon")
        dlg.setFixedSize(380, 480)
        dlg.setStyleSheet("background-color: #000000; color: #ffffff;")

        layout = QVBoxLayout(dlg)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("SZYBKI ZRZUT")
        title.setStyleSheet("font-size: 16px; font-weight: 800; letter-spacing: 0.5px; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Skieruj aparat telefonu na kod QR, aby otworzyć wrzutnię w przeglądarce:")
        desc.setStyleSheet("font-size: 12px; color: #a1a1aa; text-align: center;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        qr_lbl = QLabel()
        qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            qr_lbl.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            qr_lbl.setText(f"[Błąd QR: {e}]")
        layout.addWidget(qr_lbl)

        url_card = QFrame()
        url_card.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 10px;")
        uc_layout = QVBoxLayout(url_card)
        url_lbl = QLabel(f"Adres: <b style='color:#10b981; font-family:monospace;'>{url}</b>")
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        uc_layout.addWidget(url_lbl)
        layout.addWidget(url_card)

        btn = QPushButton("Gotowe")
        btn.setStyleSheet("background-color: #ffffff; color: #000000; padding: 10px 24px; border-radius: 8px; font-weight: 700; border: none;")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dlg.exec()

    def on_web_file_received(self, save_path):
        fname = os.path.basename(save_path)
        QTimer.singleShot(0, lambda: self.status_lbl.setText(f"Otrzymano plik z telefonu: {fname} (zapisano w Downloads/LanDrop)"))

    # =================================================================
    # OBSŁUGA TWOJEJ PULI
    # =================================================================

    def add_files_to_pool(self, paths):
        added = self.pool.add_files(paths)
        if added:
            self.refresh_my_pool_ui()
            self.status_lbl.setText(f"Dodano {len(added)} plik(ów) do Twojej puli.")
            self.discovery._send_beacon("beacon")

    def remove_from_my_pool(self, file_id):
        if self.pool.remove_file(file_id):
            self.refresh_my_pool_ui()
            self.status_lbl.setText("Usunięto plik z Twojej puli.")
            self.discovery._send_beacon("beacon")

    def clear_my_pool(self):
        if self.pool.count() == 0:
            return
        self.pool.clear()
        self.refresh_my_pool_ui()
        self.status_lbl.setText("Twoja pula została wyczyszczona.")
        self.discovery._send_beacon("beacon")

    def refresh_my_pool_ui(self):
        files = self.pool.get_list()
        self.my_table.setRowCount(len(files))

        for row, f in enumerate(files):
            name_item = QTableWidgetItem(f["name"])
            name_item.setToolTip(f["name"])
            self.my_table.setItem(row, 0, name_item)

            size_item = QTableWidgetItem(format_size(f["size"]))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.my_table.setItem(row, 1, size_item)

            del_btn = QPushButton("✕")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("Usuń z puli")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #71717a;
                    padding: 4px 8px;
                    border: none;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover { color: #ef4444; }
            """)
            del_btn.clicked.connect(lambda _, fid=f["id"]: self.remove_from_my_pool(fid))
            self.my_table.setCellWidget(row, 2, del_btn)

        self.my_summary_lbl.setText(f"W puli: {self.pool.count()} plików ({format_size(self.pool.total_size())})")

    # =================================================================
    # PLIKI W SIECI (Z APLIKACJI ANDROID LUB INNYCH KOMPUTERÓW)
    # =================================================================

    def on_peers_updated(self, peers):
        self.peers_badge.setText(f"Urządzenia: {len(peers)}")

        all_remote_files = []
        for pid, peer in peers.items():
            device_name = peer.get("deviceName", "Nieznane")
            ip = peer.get("ip")
            port = peer.get("port")
            for f in peer.get("files", []):
                all_remote_files.append({
                    "deviceId": pid,
                    "deviceName": device_name,
                    "ip": ip,
                    "port": port,
                    "file": f
                })

        self.net_table.setRowCount(len(all_remote_files))

        for row, item in enumerate(all_remote_files):
            f = item["file"]
            fid = f["id"]

            dev_item = QTableWidgetItem(item["deviceName"])
            self.net_table.setItem(row, 0, dev_item)

            name_item = QTableWidgetItem(f["name"])
            name_item.setToolTip(f["name"])
            self.net_table.setItem(row, 1, name_item)

            size_item = QTableWidgetItem(format_size(f["size"]))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.net_table.setItem(row, 2, size_item)

            if fid in self.active_downloads:
                status_lbl = QLabel("Pobieranie...")
                status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
                self.net_table.setCellWidget(row, 3, status_lbl)
            else:
                dl_btn = QPushButton("Pobierz")
                dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                dl_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #000000;
                        font-weight: 700;
                        padding: 6px 14px;
                        border-radius: 6px;
                        border: none;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #e4e4e7; }
                """)
                dl_btn.clicked.connect(lambda _, item=item: self.start_download(item))
                self.net_table.setCellWidget(row, 3, dl_btn)

    def start_download(self, item):
        f = item["file"]
        fid = f["id"]
        fname = f["name"]
        fsize = f["size"]
        ip = item["ip"]
        port = item["port"]

        if fid in self.active_downloads:
            return

        worker = DownloadWorker(fid, fname, fsize, ip, port)
        self.active_downloads[fid] = worker

        card = QFrame()
        card.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 10px;")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(8, 6, 8, 6)

        info_lbl = QLabel(f"{fname} (z {item['deviceName']})")
        info_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff;")

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #27272a;
                border-radius: 4px;
                text-align: center;
                background-color: #121214;
                color: white;
                height: 16px;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
        """)

        speed_lbl = QLabel("Pobieranie...")
        speed_lbl.setStyleSheet("font-size: 11px; color: #71717a;")

        c_lay.addWidget(info_lbl)
        c_lay.addWidget(pbar)
        c_lay.addWidget(speed_lbl)
        self.transfers_box.addWidget(card)

        def on_prog(file_id, done, total, speed_mbps):
            pct = int((done / total) * 100) if total > 0 else 0
            pbar.setValue(pct)
            speed_lbl.setText(f"{format_size(done)} / {format_size(total)} | {speed_mbps:.1f} MB/s ({pct}%)")

        def on_finish(file_id, save_path):
            pbar.setValue(100)
            speed_lbl.setText(f"Ukończono: {save_path}")
            speed_lbl.setStyleSheet("font-size: 11px; color: #10b981; font-weight: 700;")
            if file_id in self.active_downloads:
                del self.active_downloads[file_id]
            self.status_lbl.setText(f"Pobrano {fname}!")

        def on_fail(file_id, err):
            speed_lbl.setText(f"Błąd: {err}")
            speed_lbl.setStyleSheet("font-size: 11px; color: #ef4444;")
            if file_id in self.active_downloads:
                del self.active_downloads[file_id]

        worker.progress.connect(on_prog)
        worker.finished.connect(on_finish)
        worker.failed.connect(on_fail)
        worker.start()
        self.status_lbl.setText(f"Pobieranie pliku {fname}...")

    def open_downloads_folder(self):
        dl_dir = get_download_folder()
        try:
            if sys.platform == "win32":
                os.startfile(str(dl_dir))
            else:
                subprocess.Popen(["xdg-open", str(dl_dir)])
        except Exception:
            QMessageBox.information(self, "Pobrane", f"Folder pobranych:\n{dl_dir}")

    def closeEvent(self, event):
        self.status_lbl.setText("Zamykanie...")
        if self.hotspot_started_by_us:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotspot_helper.ps1")
            try:
                subprocess.Popen([
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", script_path, "-Action", "stop"
                ], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            except Exception:
                pass

        self.discovery.stop()
        self.server.stop()
        event.accept()


# =====================================================================
# START
# =====================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
