#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN Drop Pool - Aplikacja do szybkiej wymiany plików i linków w sieci lokalnej (LAN / Wi-Fi).
Stylistyka: Pure Black (OLED / Stealth Dark), zero zbędnych funkcji, maksymalna wydajność.
Obsługa: Wrzutnia Drag & Drop, udostępnianie linków WWW, Hotspot Wi-Fi z kodem QR,
dwukierunkowa synchronizacja UDP Unicast + Broadcast + HTTP TCP sync.
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
import webbrowser
import zipfile
import tarfile
import tempfile
import shutil
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

import qrcode
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QDragEnterEvent, QDropEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFileDialog, QMessageBox, QSplitter, QFrame,
    QScrollArea, QSizePolicy, QInputDialog, QDialog, QLineEdit, QCheckBox
)

BROADCAST_PORT = 45454
DEFAULT_HTTP_PORT = 50505
APP_NAME = "LAN DROP"
APP_VERSION = "1.3.3"

def parse_version(v_str):
    try:
        parts = []
        for x in str(v_str).strip().lstrip("v").split("."):
            parts.append(int(x) if x.isdigit() else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)
    except Exception:
        return (0, 0, 0)

def format_size(bytes_num):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != 'B' else f"{bytes_num} B"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"

def is_valid_local_ip(ip):
    if not ip or not isinstance(ip, str):
        return False
    # Odrzucamy loopback, APIPA, oraz wirtualne adaptery VirtualBox (192.168.56.x)
    if ip.startswith('127.') or ip.startswith('169.254.') or ip.startswith('192.168.56.') or ip.startswith('0.'):
        return False
    return True

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('1.1.1.1', 80))
        cand = s.getsockname()[0]
        if is_valid_local_ip(cand):
            return cand
    except Exception:
        pass
    finally:
        s.close()

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if is_valid_local_ip(ip):
                return ip
    except Exception:
        pass
    return '127.0.0.1'

def get_all_local_ips():
    """Zwraca wszystkie aktywne adresy IPv4 z kart sieciowych (Wi-Fi, Hotspot, Ethernet), pomijając wirtualne (VirtualBox)."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('1.1.1.1', 80))
        cand = s.getsockname()[0]
        if is_valid_local_ip(cand):
            ips.add(cand)
        s.close()
    except Exception:
        pass

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if is_valid_local_ip(ip):
                ips.add(ip)
    except Exception:
        pass

    if not ips:
        ips.add('127.0.0.1')
    return list(ips)

def get_download_folder():
    dl_path = Path.home() / "Downloads" / "LanDrop"
    dl_path.mkdir(parents=True, exist_ok=True)
    return dl_path


# =====================================================================
# MOBILNA STRONA WWW (DLA DOWOLNEGO TELEFONU BEZ APLIKACJI)
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
  .input-text {
    width: 100%;
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 10px;
    color: #ffffff;
    padding: 12px 14px;
    font-size: 14px;
    outline: none;
    margin-bottom: 10px;
  }
  .input-text:focus { border-color: #ffffff; }
  .btn-link {
    background: #27272a;
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #3f3f46;
    width: 100%;
    cursor: pointer;
  }
  .btn-link:active { background: #3f3f46; }
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
    display: inline-block;
  }
  .btn-open {
    background: #ffffff;
    color: #000000;
    text-decoration: none;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 8px;
    border: none;
    white-space: nowrap;
    margin-left: 12px;
    display: inline-block;
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
    <div class="card-title">Wyślij link WWW do komputera</div>
    <input type="url" id="linkIn" class="input-text" placeholder="Wklej link https://...">
    <button class="btn-link" onclick="sendLink()">Wyślij link do komputera</button>
    <div class="status-msg" id="linkMsg"></div>
  </div>

  <div class="card">
    <div class="card-title">Pula wystawiona na komputerze</div>
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
        const res = await fetch('/api/pool?t=' + Date.now(), { cache: 'no-store' });
        const data = await res.json();
        const box = document.getElementById('fileContainer');
        if (!data.files || data.files.length === 0) {
          box.innerHTML = '<div class="empty-note">Pula komputera jest pusta.<br>Przeciągnij pliki lub dodaj link w programie na komputerze.</div>';
          return;
        }
        let html = '';
        for (let f of data.files) {
          if (f.type === 'link') {
            const url = f.content || f.name;
            html += '<div class="file-item"><div><div class="file-name">🔗 ' + escapeHtml(f.name) + '</div><div class="file-size">Link WWW</div></div><a class="btn-open" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Otwórz ↗</a></div>';
          } else if (f.type === 'folder') {
            html += '<div class="file-item"><div><div class="file-name">📁 ' + escapeHtml(f.name) + '</div><div class="file-size">Folder (' + (f.file_count || 0) + ' plików, ' + fmt(f.size) + ')</div></div><a class="btn-dl" href="/api/download/' + f.id + '" download="' + escapeHtml(f.name) + '.zip">Pobierz ZIP</a></div>';
          } else if (f.type === 'update') {
            html += '<div class="file-item"><div><div class="file-name">🚀 ' + escapeHtml(f.name) + '</div><div class="file-size">Aktualizacja LAN Drop (' + fmt(f.size) + ')</div></div><a class="btn-dl" href="/api/download/' + f.id + '" download="landrop_update.zip">Pobierz paczkę</a></div>';
          } else {
            html += '<div class="file-item"><div><div class="file-name">📄 ' + escapeHtml(f.name) + '</div><div class="file-size">' + fmt(f.size) + '</div></div><a class="btn-dl" href="/api/download/' + f.id + '" download="' + escapeHtml(f.name) + '">Pobierz</a></div>';
          }
        }
        box.innerHTML = html;
      } catch (e) {
        document.getElementById('fileContainer').innerHTML = '<div class="empty-note">Brak połączenia z komputerem.</div>';
      }
    }

    function escapeHtml(str) {
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    async function sendLink() {
      const input = document.getElementById('linkIn');
      const val = input.value.trim();
      const msg = document.getElementById('linkMsg');
      if (!val) return;
      try {
        msg.innerText = 'Wysyłanie linku...';
        const res = await fetch('/api/upload_link?url=' + encodeURIComponent(val), { method: 'POST' });
        if (res.ok) {
          msg.innerText = '✅ Link przesłany na komputer!';
          input.value = '';
          setTimeout(() => { msg.innerText = ''; }, 3000);
          fetchPool();
        } else {
          msg.innerText = '❌ Błąd wysyłania linku.';
        }
      } catch (e) {
        msg.innerText = '❌ Błąd połączenia.';
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
    setInterval(fetchPool, 2000);
  </script>
</body>
</html>
"""


# =====================================================================
# PULA ELEMENTÓW (PLIKI + LINKI) I SERWER HTTP
# =====================================================================

class SharedItem:
    def __init__(self, file_path: str = None, link_url: str = None, folder_path: str = None, is_update: bool = False, version: str = APP_VERSION):
        self.id = str(uuid.uuid4())
        self.version = version
        if is_update:
            self.type = "update"
            self.path = os.path.abspath(file_path) if file_path else None
            self.name = f"Aktualizacja LAN Drop (v{version})"
            self.content = None
            self.size = os.path.getsize(self.path) if self.path and os.path.exists(self.path) else 0
            self.mime = "application/zip"
            self.file_count = 1
        elif folder_path:
            self.type = "folder"
            self.path = os.path.abspath(folder_path)
            self.name = os.path.basename(self.path)
            self.content = None
            total_size = 0
            file_count = 0
            try:
                for root, _, files in os.walk(self.path):
                    for f in files:
                        fp = os.path.join(root, f)
                        if os.path.isfile(fp):
                            total_size += os.path.getsize(fp)
                            file_count += 1
            except Exception:
                pass
            self.size = total_size
            self.file_count = file_count
            self.mime = "application/x-directory"
        elif link_url:
            self.type = "link"
            self.path = None
            self.name = link_url.strip()
            self.content = link_url.strip()
            self.size = len(self.name.encode('utf-8'))
            self.mime = "text/x-uri"
            self.file_count = 0
        else:
            self.type = "file"
            self.path = os.path.abspath(file_path)
            self.name = os.path.basename(self.path)
            self.content = None
            self.size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
            mime, _ = mimetypes.guess_type(self.path)
            self.mime = mime or "application/octet-stream"
            self.file_count = 1

    def to_dict(self):
        d = {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "mime": self.mime,
            "type": self.type,
            "file_count": getattr(self, "file_count", 1)
        }
        if self.content:
            d["content"] = self.content
        if getattr(self, "version", None):
            d["version"] = self.version
        return d

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
                    if not any(item.path == os.path.abspath(p) for item in self.files.values() if item.type == "file"):
                        item = SharedItem(file_path=p)
                        self.files[item.id] = item
                        added.append(item)
            if added:
                self.version += 1
        return added

    def add_folder(self, folder_path):
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return None
        with self.lock:
            for item in self.files.values():
                if item.type == "folder" and item.path == folder_path:
                    return item
            item = SharedItem(folder_path=folder_path)
            self.files[item.id] = item
            self.version += 1
            return item

    def add_update(self, zip_path, version=APP_VERSION):
        with self.lock:
            to_del = [fid for fid, it in self.files.items() if it.type == "update"]
            for fid in to_del:
                del self.files[fid]
            item = SharedItem(file_path=zip_path, is_update=True, version=version)
            self.files[item.id] = item
            self.version += 1
            return item

    def add_link(self, url: str):
        url = url.strip()
        if not url:
            return None
        with self.lock:
            for item in self.files.values():
                if item.type == "link" and item.content == url:
                    return item
            item = SharedItem(link_url=url)
            self.files[item.id] = item
            self.version += 1
            return item

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
            if not file_id:
                return None
            if file_id in self.files:
                return self.files[file_id]
            uq_id = unquote(str(file_id)).strip()
            if uq_id in self.files:
                return self.files[uq_id]
            for it in self.files.values():
                if it.name == file_id or it.name == uq_id:
                    return it
            return None

    def count(self):
        with self.lock:
            return len(self.files)

    def total_size(self):
        with self.lock:
            return sum(item.size for item in self.files.values())


class SocketWriter:
    """Umożliwia bezpośrednie strumieniowanie archiwum zip do gniazda HTTP bez tworzenia plików tymczasowych na dysku."""
    def __init__(self, wfile):
        self.wfile = wfile
        self.pos = 0

    def write(self, b):
        self.wfile.write(b)
        self.pos += len(b)
        return len(b)

    def tell(self):
        return self.pos

    def flush(self):
        try:
            self.wfile.flush()
        except Exception:
            pass


class ProgressStream(io.RawIOBase):
    """Opakowuje strumień sieciowy odpowiedzi HTTP, raportując postęp i prędkość w czasie rzeczywistym bez blokowania."""
    def __init__(self, raw_resp, on_progress_callback=None):
        self.raw = raw_resp
        self.read_bytes = 0
        self.on_progress = on_progress_callback
        self.last_time = time.time()
        self.last_bytes = 0

    def read(self, n=-1):
        chunk = self.raw.read(n)
        if chunk:
            self.read_bytes += len(chunk)
            self._notify()
        return chunk

    def readinto(self, b):
        n = self.raw.readinto(b)
        if n:
            self.read_bytes += n
            self._notify()
        return n

    def _notify(self):
        if self.on_progress:
            now = time.time()
            elapsed = now - self.last_time
            if elapsed >= 0.25:
                speed_mbps = ((self.read_bytes - self.last_bytes) / (1024 * 1024)) / elapsed
                self.last_time = now
                self.last_bytes = self.read_bytes
                self.on_progress(self.read_bytes, speed_mbps)

    def readable(self):
        return True


class HttpFileHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        pool = self.server.pool_manager
        parsed = urlparse(self.path)
        req_path = unquote(parsed.path)

        if req_path in ("/", "/index.html"):
            body = MOBILE_WEB_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if req_path in ("/api/pool", "/api/pool/"):
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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if req_path.startswith("/api/stream_folder/"):
            file_id = req_path[len("/api/stream_folder/"):].strip("/")
            item = pool.get_item(file_id)
            if not item:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Element nie istnieje.")
                return

            if item.type != "folder" or not os.path.isdir(item.path):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Element nie jest folderem.")
                return

            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-tar")
                self.send_header("X-Item-Type", "folder")
                self.send_header("X-Total-Bytes", str(item.size))
                safe_name = f"{item.name}.tar".replace('"', '\\"')
                self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                base_dir = os.path.abspath(item.path)
                with tarfile.open(fileobj=self.wfile, mode="w|") as tw:
                    for root, dirs, files in os.walk(base_dir):
                        for file in files:
                            full_p = os.path.join(root, file)
                            rel_p = os.path.relpath(full_p, base_dir)
                            try:
                                tw.add(full_p, arcname=rel_p)
                            except Exception as add_err:
                                print(f"[HTTP] Blad dodawania pliku {rel_p}: {add_err}")
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                print(f"[HTTP] Blad strumieniowania folderu tar: {e}")
            return

        if req_path.startswith("/api/download/"):
            file_id = req_path[len("/api/download/"):].strip("/")
            item = pool.get_item(file_id)
            if not item:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Element nie istnieje lub zostal usuniety z puli.")
                return

            if item.type == "link":
                body = (item.content or item.name).encode('utf-8')
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            if item.type == "folder":
                if not os.path.isdir(item.path):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Folder nie istnieje na dysku.")
                    return

                # Sprawdzamy czy klient preferuje strumieniowanie TAR (np. aplikacja desktopowa) czy ZIP (przeglądarka WWW)
                accept_hdr = self.headers.get("Accept", "")
                is_tar_req = "format=tar" in parsed.query or "tar" in accept_hdr

                if is_tar_req:
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/x-tar")
                        self.send_header("X-Item-Type", "folder")
                        self.send_header("X-Total-Bytes", str(item.size))
                        safe_name = f"{item.name}.tar".replace('"', '\\"')
                        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()

                        base_dir = os.path.abspath(item.path)
                        with tarfile.open(fileobj=self.wfile, mode="w|") as tw:
                            for root, dirs, files in os.walk(base_dir):
                                for file in files:
                                    full_p = os.path.join(root, file)
                                    rel_p = os.path.relpath(full_p, base_dir)
                                    try:
                                        tw.add(full_p, arcname=rel_p)
                                    except Exception as add_err:
                                        print(f"[HTTP] Blad dodawania pliku {rel_p}: {add_err}")
                    except (ConnectionResetError, BrokenPipeError):
                        pass
                    except Exception as e:
                        print(f"[HTTP] Blad strumieniowania folderu tar: {e}")
                    return

                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("X-Item-Type", "folder")
                    safe_name = f"{item.name}.zip".replace('"', '\\"')
                    self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    base_dir = os.path.abspath(item.path)
                    sw = SocketWriter(self.wfile)
                    with zipfile.ZipFile(sw, 'w', compression=zipfile.ZIP_STORED) as zf:
                        for root, dirs, files in os.walk(base_dir):
                            for file in files:
                                full_p = os.path.join(root, file)
                                rel_p = os.path.relpath(full_p, base_dir)
                                try:
                                    zf.write(full_p, arcname=rel_p)
                                except Exception as ze:
                                    print(f"[HTTP] Blad pakowania {rel_p}: {ze}")
                except (ConnectionResetError, BrokenPipeError):
                    pass
                except Exception as e:
                    print(f"[HTTP] Blad strumieniowania folderu zip: {e}")
                return

            if not os.path.exists(item.path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Plik nie istnieje na dysku.")
                return

            try:
                file_size = os.path.getsize(item.path)
                self.send_response(200)
                self.send_header("Content-Type", item.mime)
                self.send_header("Content-Length", str(file_size))
                safe_name = item.name.replace('"', '\\"')
                self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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

        if req_path == "/api/ping":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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

        if parsed.path == "/api/upload_link":
            qs = parse_qs(parsed.query)
            link_url = qs.get("url", [""])[0]
            if not link_url:
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    raw_body = self.rfile.read(content_length).decode('utf-8')
                    body_json = json.loads(raw_body)
                    link_url = body_json.get("url", "")
                except Exception:
                    pass

            if link_url:
                if hasattr(self.server, "on_link_received") and self.server.on_link_received:
                    self.server.on_link_received(link_url)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Brak parametru url"}')
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
        self.on_link_received = None

    def start(self):
        ThreadingHTTPServer.allow_reuse_address = True

        # Zwalnianie ewentualnego zawieszonego procesu python na porcie 50505
        try:
            cur_pid = os.getpid()
            out = subprocess.check_output(f'netstat -ano | findstr :{self.port}', shell=True).decode('utf-8', errors='ignore')
            for line in out.splitlines():
                if "LISTENING" in line.upper():
                    parts = line.strip().split()
                    if parts:
                        owner_pid = int(parts[-1])
                        if owner_pid != cur_pid and owner_pid > 0:
                            subprocess.call(f'taskkill /f /pid {owner_pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            time.sleep(0.5)
        except Exception:
            pass

        for p in [self.port] + list(range(self.port + 1, self.port + 10)):
            try:
                self.server = ThreadingHTTPServer(('0.0.0.0', p), HttpFileHandler)
                self.server.pool_manager = self.pool
                self.server.device_id = self.device_id
                self.server.device_name = self.device_name
                self.server.on_file_received = self.on_file_received
                self.server.on_link_received = self.on_link_received
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
# SYSTEM ODKRYWANIA URZĄDZEŃ W SIECI (UDP BROADCAST + UNICAST + TCP SYNC)
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
        self.known_peer_ips = set()
        self.lock = threading.Lock()

    def run(self):
        rx_thread = threading.Thread(target=self._listen_loop, daemon=True)
        rx_thread.start()

        tcp_thread = threading.Thread(target=self._tcp_poll_loop, daemon=True)
        tcp_thread.start()

        while self.running:
            self._send_beacon("beacon")
            self._prune_peers()
            time.sleep(2)

    def _send_beacon(self, msg_type="beacon", target_ip=None):
        payload = {
            "type": msg_type,
            "deviceId": self.device_id,
            "deviceName": self.device_name,
            "platform": "windows",
            "port": self.http_port,
            "version": self.pool.version,
            "app_version": APP_VERSION,
            "files": self.pool.get_list()
        }
        data = json.dumps(payload).encode('utf-8')

        local_ips = get_all_local_ips()
        for lip in local_ips:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(0.3)
                sock.bind((lip, 0))

                if target_ip:
                    # Wysyłka unicast do konkretnego adresu
                    sock.sendto(data, (target_ip, BROADCAST_PORT))
                else:
                    # 1. Ogólny broadcast
                    try:
                        sock.sendto(data, ('255.255.255.255', BROADCAST_PORT))
                    except Exception:
                        pass

                    # 2. Subnet broadcast (np. 192.168.1.255)
                    parts = lip.split('.')
                    if len(parts) == 4 and parts[0] != '127':
                        try:
                            sock.sendto(data, (f"{parts[0]}.{parts[1]}.{parts[2]}.255", BROADCAST_PORT))
                        except Exception:
                            pass

                    # 3. Unicast do wszystkich znanych urządzeń (omija filtry routera FunBox)
                    with self.lock:
                        ips_to_unicast = list(self.known_peer_ips)
                    for pip in ips_to_unicast:
                        try:
                            sock.sendto(data, (pip, BROADCAST_PORT))
                        except Exception:
                            pass

                sock.close()
            except Exception:
                pass

    def send_farewell(self):
        payload = {"type": "farewell", "deviceId": self.device_id}
        data = json.dumps(payload).encode('utf-8')
        local_ips = get_all_local_ips()
        for lip in local_ips:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((lip, 0))
                sock.sendto(data, ('255.255.255.255', BROADCAST_PORT))
                with self.lock:
                    ips = list(self.known_peer_ips)
                for pip in ips:
                    try:
                        sock.sendto(data, (pip, BROADCAST_PORT))
                    except Exception:
                        pass
                sock.close()
            except Exception:
                pass

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

                with self.lock:
                    is_new = sender_ip not in self.known_peer_ips
                    self.known_peer_ips.add(sender_ip)

                # Jeśli to nowe urządzenie, natychmiast odpowiedz pakietem unicast
                if is_new:
                    self._send_beacon("beacon", target_ip=sender_ip)

                msg_type = msg.get("type", "beacon")
                with self.lock:
                    if msg_type == "farewell":
                        if peer_id in self.peers:
                            del self.peers[peer_id]
                            self.peers_updated.emit(dict(self.peers))
                    else:
                        parsed_files = []
                        for f in msg.get("files", []):
                            f_item = {
                                "id": f.get("id"),
                                "name": f.get("name"),
                                "size": f.get("size", 0),
                                "type": f.get("type", "file"),
                                "content": f.get("content"),
                                "file_count": f.get("file_count", 1)
                            }
                            if "version" in f:
                                f_item["version"] = f["version"]
                            parsed_files.append(f_item)

                        self.peers[peer_id] = {
                            "last_seen": time.time(),
                            "ip": sender_ip,
                            "deviceName": msg.get("deviceName", f"Telefon ({sender_ip})"),
                            "platform": msg.get("platform", "unknown"),
                            "port": msg.get("port", DEFAULT_HTTP_PORT),
                            "version": msg.get("version", 1),
                            "app_version": msg.get("app_version"),
                            "files": parsed_files
                        }
                        self.peers_updated.emit(dict(self.peers))
            except socket.timeout:
                continue
            except Exception:
                continue
        sock.close()

    def _tcp_poll_loop(self):
        """Aktywne odpytywanie TCP/HTTP co 2.5s gwarantuje 100% synchronizacji listy plików."""
        while self.running:
            time.sleep(2.5)
            with self.lock:
                peers_to_check = [(p["ip"], p.get("port", DEFAULT_HTTP_PORT), pid) for pid, p in self.peers.items()]
                known_ips = list(self.known_peer_ips)

            for ip, port, pid in peers_to_check:
                self._fetch_peer_http(ip, port, pid)

            for ip in known_ips:
                if not any(ip == p[0] for p in peers_to_check):
                    self._fetch_peer_http(ip, DEFAULT_HTTP_PORT, None)

    def _fetch_peer_http(self, ip, port, expected_pid):
        try:
            req = urllib.request.Request(f"http://{ip}:{port}/api/pool?t={int(time.time()*1000)}")
            req.add_header("Cache-Control", "no-cache")
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                pid = data.get("deviceId", ip)
                if pid == self.device_id:
                    return

                parsed_files = []
                for f in data.get("files", []):
                    f_item = {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "size": f.get("size", 0),
                        "type": f.get("type", "file"),
                        "content": f.get("content"),
                        "file_count": f.get("file_count", 1)
                    }
                    if "version" in f:
                        f_item["version"] = f["version"]
                    parsed_files.append(f_item)

                with self.lock:
                    self.peers[pid] = {
                        "last_seen": time.time(),
                        "ip": ip,
                        "deviceName": data.get("deviceName", f"Telefon ({ip})"),
                        "platform": "http_sync",
                        "port": port,
                        "version": data.get("version", 1),
                        "app_version": data.get("app_version"),
                        "files": parsed_files
                    }
                    self.peers_updated.emit(dict(self.peers))
        except Exception:
            pass

    def _prune_peers(self):
        now = time.time()
        changed = False
        with self.lock:
            to_delete = []
            for pid, peer in self.peers.items():
                if now - peer["last_seen"] > 8.0:
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

    def __init__(self, file_id, file_name, file_size, host_ip, host_port, item_type="file"):
        super().__init__()
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.host_ip = host_ip
        self.host_port = host_port
        self.item_type = item_type
        self.dest_dir = get_download_folder()

    def run(self):
        if self.item_type == "folder":
            target_folder = self.dest_dir / self.file_name
            counter = 1
            base_name = self.file_name
            while target_folder.exists():
                target_folder = self.dest_dir / f"{base_name}_{counter}"
                counter += 1
            target_folder.mkdir(parents=True, exist_ok=True)

            urls_to_try = [
                f"http://{self.host_ip}:{self.host_port}/api/download/{self.file_id}?format=tar",
                f"http://{self.host_ip}:{self.host_port}/api/stream_folder/{self.file_id}",
                f"http://{self.host_ip}:{self.host_port}/api/download/{self.file_id}"
            ]

            resp = None
            last_err = None
            for url in urls_to_try:
                try:
                    req = urllib.request.Request(url)
                    req.add_header("Cache-Control", "no-cache")
                    req.add_header("Accept", "application/x-tar, application/zip, */*")
                    r = urllib.request.urlopen(req, timeout=30)
                    if r.status == 200:
                        resp = r
                        break
                except urllib.error.HTTPError as he:
                    last_err = he
                    if he.code != 404:
                        break
                except Exception as ex:
                    last_err = ex
                    break

            if not resp:
                err_msg = f"Błąd pobierania folderu ({last_err}). Upewnij się, że na drugim komputerze folder jest wciąż w puli i zrestartowano program."
                self.failed.emit(self.file_id, err_msg)
                return

            try:
                if hasattr(resp, "fp") and hasattr(resp.fp, "raw") and hasattr(resp.fp.raw, "_sock"):
                    resp.fp.raw._sock.settimeout(180.0)
            except Exception:
                pass

            content_type = resp.headers.get("Content-Type", "")
            total_bytes = int(resp.headers.get("X-Total-Bytes", resp.headers.get("Content-Length", self.file_size)))
            if total_bytes <= 0:
                total_bytes = self.file_size

            start_time = time.time()

            def on_stream_prog(done, speed):
                self.progress.emit(self.file_id, min(done, total_bytes), total_bytes, speed)

            ps = ProgressStream(resp, on_progress_callback=on_stream_prog)

            try:
                if "tar" in content_type:
                    with tarfile.open(fileobj=ps, mode="r|*") as tr:
                        for member in tr:
                            clean_name = os.path.normpath(member.name).lstrip("/\\")
                            if ".." in clean_name.split(os.sep):
                                continue
                            member.name = clean_name
                            try:
                                tr.extract(member, path=str(target_folder))
                            except Exception as ex_err:
                                print(f"[TAR] Blad wypakowywania {member.name}: {ex_err}")
                else:
                    temp_zip = target_folder / f".download_{uuid.uuid4().hex[:6]}.zip"
                    with open(temp_zip, "wb") as zf_out:
                        while chunk := ps.read(1024 * 1024):
                            zf_out.write(chunk)
                    with zipfile.ZipFile(temp_zip, 'r') as zf:
                        zf.extractall(target_folder)
                    try:
                        temp_zip.unlink(missing_ok=True)
                    except Exception:
                        pass

                total_elapsed = max(0.001, time.time() - start_time)
                avg_speed = (ps.read_bytes / (1024 * 1024)) / total_elapsed
                self.progress.emit(self.file_id, total_bytes, total_bytes, avg_speed)
                self.finished.emit(self.file_id, str(target_folder))

            except Exception as e:
                self.failed.emit(self.file_id, str(e))
            return

        # Pobieranie pojedynczego pliku
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
            req.add_header("Cache-Control", "no-cache")
            resp = urllib.request.urlopen(req, timeout=30)
            try:
                if hasattr(resp, "fp") and hasattr(resp.fp, "raw") and hasattr(resp.fp.raw, "_sock"):
                    resp.fp.raw._sock.settimeout(180.0)
            except Exception:
                pass

            with resp, open(save_path, "wb") as out_file:
                total_bytes = int(resp.headers.get("Content-Length", self.file_size))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1 MB bufor dla maksymalnej przepustowości NVMe/SSD
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
                    if elapsed >= 0.25:
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


class UpdateWorker(QThread):
    progress = pyqtSignal(int, int, float)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, file_id, file_size, host_ip, host_port, target_dir=None, python_exe=None):
        super().__init__()
        self.file_id = file_id
        self.file_size = file_size
        self.host_ip = host_ip
        self.host_port = host_port

        if target_dir:
            self.target_dir = os.path.abspath(target_dir).rstrip("\\/")
        else:
            cur_script = os.path.abspath(__file__)
            win_dir = os.path.dirname(cur_script)
            if os.path.basename(win_dir).lower() == "windows":
                self.target_dir = os.path.abspath(os.path.dirname(win_dir)).rstrip("\\/")
            else:
                self.target_dir = os.path.abspath(win_dir).rstrip("\\/")

        if python_exe:
            self.python_exe = os.path.abspath(python_exe)
        else:
            py_dir = os.path.dirname(sys.executable)
            pw = os.path.join(py_dir, "pythonw.exe")
            self.python_exe = os.path.abspath(pw if os.path.exists(pw) else sys.executable)

    def run(self):
        url = f"http://{self.host_ip}:{self.host_port}/api/download/{self.file_id}"
        temp_dir = tempfile.mkdtemp(prefix="landrop_upd_")
        zip_path = os.path.join(temp_dir, "update.zip")
        extract_dir = os.path.join(temp_dir, "extracted")

        try:
            req = urllib.request.Request(url)
            req.add_header("Cache-Control", "no-cache")
            with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as out_file:
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
                        self.progress.emit(downloaded, total_bytes, speed_mbps)

                total_elapsed = max(0.001, time.time() - start_time)
                avg_speed = (downloaded / (1024 * 1024)) / total_elapsed
                self.progress.emit(downloaded, total_bytes, avg_speed)

            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            try:
                os.remove(zip_path)
            except Exception:
                pass

            clean_extract = os.path.abspath(extract_dir).rstrip("\\/")
            clean_target = os.path.abspath(self.target_dir).rstrip("\\/")
            clean_py = os.path.abspath(self.python_exe)
            clean_win_dir = os.path.join(clean_target, "windows")
            bat_path = os.path.join(temp_dir, "apply_update.bat")

            bat_content = f"""@echo off
chcp 65001 >nul
title Wgrywanie aktualizacji LAN DROP
echo ========================================================
echo        WGRYWANIE AKTUALIZACJI LAN DROP POOL
echo ========================================================
echo Zamykanie dzialajacej instancji LAN Drop (PID: %1)...
taskkill /f /pid %1 >nul 2>&1
timeout /t 2 /nobreak >nul

echo Kopiowanie nowych plikow do: {clean_target} ...
robocopy "{clean_extract}" "{clean_target}" /E /R:5 /W:1 /NP /NFL /NDO /NJH /NJS >nul 2>&1
if %errorlevel% geq 8 (
    xcopy /s /y /q /i /r /h "{clean_extract}\\*" "{clean_target}\\" >nul 2>&1
)

echo.
echo ========================================================
echo   SUKCES: Aktualizacja zainstalowana pomyslnie!
echo ========================================================
echo Uruchamianie zaktualizowanego programu...
cd /d "{clean_win_dir}"
start "" "{clean_py}" lan_drop.py

echo Czyszczenie plikow instalacyjnych...
timeout /t 2 /nobreak >nul
rd /s /q "{temp_dir}" >nul 2>&1
exit
"""
            with open(bat_path, "w", encoding="utf-8") as bf:
                bf.write(bat_content)

            self.finished.emit(bat_path)
        except Exception as e:
            self.failed.emit(str(e))


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
        layout.setContentsMargins(20, 28, 20, 28)
        layout.setSpacing(6)

        self.icon_label = QLabel("📥")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 34px; background: transparent;")

        self.text_label = QLabel("PRZECIĄGNIJ I UPUŚĆ PLIKI LUB FOLDERY")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 800; letter-spacing: 0.5px; color: #ffffff; background: transparent;")

        self.sub_label = QLabel("Możesz upuścić pliki lub całe foldery w dowolnym miejscu okna")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("font-size: 12px; color: #71717a; background: transparent;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.sub_label)

        self.set_idle_style()

    def set_idle_style(self):
        self.setStyleSheet("""
            #DropZone {
                background-color: #09090b;
                border: 2px dashed #27272a;
                border-radius: 12px;
            }
        """)

    def set_hover_style(self):
        self.setStyleSheet("""
            #DropZone {
                background-color: #121214;
                border: 2px dashed #10b981;
                border-radius: 12px;
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
        paths = [u.toLocalFile() for u in urls if os.path.exists(u.toLocalFile())]
        if paths:
            self.files_dropped.emit(paths)


# =====================================================================
# GŁÓWNE OKNO APLIKACJI (PURE BLACK STEALTH DESIGN)
# =====================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1140, 750)
        self.setMinimumSize(940, 600)

        self.device_id = str(uuid.uuid4())[:8]
        self.hostname = socket.gethostname()
        self.device_name = f"{self.hostname} (PC)"
        self.local_ip = get_local_ip()

        self.hotspot_active = False
        self.hotspot_started_by_us = False
        self.hotspot_worker = None
        self.active_downloads = {}
        self.row_checkboxes = []

        self.pool = PoolManager()
        self.server = LocalServer(self.pool, self.device_id, self.device_name)
        self.server.on_file_received = self.on_web_file_received
        self.server.on_link_received = self.on_web_link_received
        self.server.start()

        self.discovery = LanDiscovery(self.device_id, self.device_name, self.server.port, self.pool)
        self.discovery.peers_updated.connect(self.on_peers_updated)
        self.discovery.start()

        self.setAcceptDrops(True)
        self.setup_ui()
        self.apply_theme()
        QApplication.instance().installEventFilter(self)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

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
        self.ver_badge = QLabel(f"v{APP_VERSION}")
        self.ver_badge.setStyleSheet("background-color: #18181b; color: #10b981; border: 1px solid #27272a; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 800; font-family: monospace;")
        title_box.addWidget(dot)
        title_box.addWidget(app_title)
        title_box.addWidget(self.ver_badge)

        self.ip_badge = QPushButton(f"🌐 {self.local_ip}:{self.server.port}")
        self.ip_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ip_badge.setToolTip(f"Kliknij, aby skopiować link do przeglądarki (http://{self.local_ip}:{self.server.port})")
        self.ip_badge.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #10b981;
                border: 1px solid #27272a;
                padding: 4px 10px;
                border-radius: 6px;
                font-family: monospace;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #27272a; border-color: #10b981; }
        """)
        self.ip_badge.clicked.connect(self.copy_web_url)
        title_box.addWidget(self.ip_badge)

        self.peers_badge = QLabel("Urządzenia: 0")
        self.peers_badge.setStyleSheet("background-color: #18181b; color: #71717a; border: 1px solid #27272a; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;")
        title_box.addWidget(self.peers_badge)

        # Przycisk ręcznego łączenia z IP (gdy router blokuje UDP broadcast)
        self.connect_ip_btn = QPushButton("➕ Połącz z IP")
        self.connect_ip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_ip_btn.setToolTip("Wpisz adres IP drugiego komputera lub telefonu (np. 192.168.1.11)")
        self.connect_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #3f3f46;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #27272a; border-color: #10b981; color: #10b981; }
        """)
        self.connect_ip_btn.clicked.connect(self.prompt_connect_ip)
        title_box.addWidget(self.connect_ip_btn)

        h_layout.addLayout(title_box)
        h_layout.addStretch()

        # Przyciski akcji
        actions = QHBoxLayout()
        actions.setSpacing(8)

        # Przycisk: Szybki zrzut WWW (QR dla dowolnego telefonu)
        self.web_btn = QPushButton("📱 Szybki zrzut (QR)")
        self.web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.web_btn.setToolTip("Otwórz stronę wrzutni na telefonie bez instalacji aplikacji")
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

        # Przycisk: Hotspot Wi-Fi
        self.hotspot_btn = QPushButton("📶 Hotspot Wi-Fi")
        self.hotspot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_hotspot_btn_idle()
        self.hotspot_btn.clicked.connect(self.toggle_hotspot)
        actions.addWidget(self.hotspot_btn)

        # Przycisk: Wystaw aktualizację
        self.share_update_btn = QPushButton("🚀 Wystaw aktualizację")
        self.share_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.share_update_btn.setToolTip("Spakuj i udostępnij program jako aktualizację dla drugiego komputera")
        self.share_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #3f3f46;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272a; border-color: #10b981; color: #10b981; }
        """)
        self.share_update_btn.clicked.connect(self.share_update_to_pool)
        actions.addWidget(self.share_update_btn)

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

        # Przycisk: Zamknij (wyłącza hotspot i zamyka program)
        close_app_btn = QPushButton("✕")
        close_app_btn.setToolTip("Zamknij program (wyłącza hotspot Wi-Fi i zamyka)")
        close_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_app_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #71717a;
                border: 1px solid #27272a;
                padding: 8px 12px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272a; color: #ef4444; border-color: #ef4444; }
        """)
        close_app_btn.clicked.connect(self.close)
        actions.addWidget(close_app_btn)

        h_layout.addLayout(actions)
        main_layout.addWidget(header)

        # Baner dostępnej aktualizacji programu w sieci
        self.update_banner = QFrame()
        self.update_banner.setStyleSheet("""
            QFrame {
                background-color: #064e3b;
                border: 2px solid #10b981;
                border-radius: 12px;
            }
        """)
        u_layout = QHBoxLayout(self.update_banner)
        u_layout.setContentsMargins(18, 12, 18, 12)
        u_layout.setSpacing(14)

        self.update_banner_lbl = QLabel("⚡ WYKRYTO NOWĄ AKTUALIZACJĘ PROGRAMU W SIECI!")
        self.update_banner_lbl.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 13px; background: transparent;")
        u_layout.addWidget(self.update_banner_lbl)
        u_layout.addStretch()

        self.apply_update_btn = QPushButton("⚡ WGRAJ AKTUALIZACJĘ I ZRESTARTUJ")
        self.apply_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #000000;
                font-weight: 900;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover { background-color: #34d399; }
        """)
        u_layout.addWidget(self.apply_update_btn)

        self.update_banner.setVisible(False)
        main_layout.addWidget(self.update_banner)

        # 2. Główny podział (Splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)

        # PANEL LEWY: TWOJA PULA
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #000000; border: 1px solid #1f1f23; border-radius: 14px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_head = QHBoxLayout()
        l_title = QLabel("TWOJA PULA (WYSTAWIONE DLA TELEFONU)")
        l_title.setStyleSheet("font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #a1a1aa;")
        left_head.addWidget(l_title)
        left_head.addStretch()

        # Przyciski szybkiego dodawania
        add_files_btn = QPushButton("➕ Dodaj pliki")
        add_files_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_files_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #e4e4e7; }
        """)
        add_files_btn.clicked.connect(self.choose_files)
        left_head.addWidget(add_files_btn)

        add_folder_btn = QPushButton("📁 Dodaj folder")
        add_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #27272a;
            }
            QPushButton:hover { background-color: #27272a; border-color: #3f3f46; }
        """)
        add_folder_btn.clicked.connect(self.choose_folder)
        left_head.addWidget(add_folder_btn)

        add_link_btn = QPushButton("🔗 Dodaj link")
        add_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_link_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #27272a;
            }
            QPushButton:hover { background-color: #27272a; }
        """)
        add_link_btn.clicked.connect(self.prompt_add_link)
        left_head.addWidget(add_link_btn)

        left_layout.addLayout(left_head)

        # Strefa DropZone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self.add_paths_to_pool)
        left_layout.addWidget(self.drop_zone)

        # Tabela plików Twojej puli
        self.my_table = QTableWidget(0, 3)
        self.my_table.setHorizontalHeaderLabels(["Plik / Link WWW", "Rozmiar", ""])
        self.my_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.my_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.my_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.my_table.verticalHeader().setVisible(False)
        self.my_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        left_layout.addWidget(self.my_table)

        # Pasek podsumowania lewego panelu
        left_foot = QHBoxLayout()
        self.my_summary_lbl = QLabel("W puli: 0 elementów")
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

        # PANEL PRAWY: ELEMENTY W SIECI
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #000000; border: 1px solid #1f1f23; border-radius: 14px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        right_head = QHBoxLayout()
        right_head.setSpacing(6)
        r_title = QLabel("PLIKI I LINKI W SIECI")
        r_title.setStyleSheet("font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #a1a1aa;")
        right_head.addWidget(r_title)
        right_head.addStretch()

        self.select_all_btn = QPushButton("☑ Zaznacz wszystko")
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #ffffff;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 6px;
                border: 1px solid #27272a;
            }
            QPushButton:hover { background-color: #27272a; border-color: #3f3f46; }
        """)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        right_head.addWidget(self.select_all_btn)

        self.dl_selected_btn = QPushButton("⬇ Pobierz zaznaczone")
        self.dl_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #18181b;
                color: #10b981;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
                border: 1px solid #27272a;
            }
            QPushButton:hover { background-color: #27272a; border-color: #10b981; }
        """)
        self.dl_selected_btn.clicked.connect(self.download_selected)
        right_head.addWidget(self.dl_selected_btn)

        self.dl_all_btn = QPushButton("⬇ Pobierz wszystkie")
        self.dl_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #e4e4e7; }
        """)
        self.dl_all_btn.clicked.connect(self.download_all)
        right_head.addWidget(self.dl_all_btn)

        right_layout.addLayout(right_head)

        # Tabela sieciowa (5 kolumn: Checkbox, Urządzenie, Nazwa/Link, Rozmiar, Akcja)
        self.net_table = QTableWidget(0, 5)
        self.net_table.setHorizontalHeaderLabels(["", "Urządzenie", "Nazwa / Link WWW", "Rozmiar", "Akcja"])
        self.net_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.net_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.net_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
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
        self.status_lbl = QLabel("Gotowy. Przeciągnij pliki do lewego panelu lub kliknij 'Dodaj link'.")
        self.status_lbl.setStyleSheet("color: #71717a; font-size: 12px;")
        status_bar.addWidget(self.status_lbl)
        status_bar.addStretch()

        tip_lbl = QLabel("Elementy znikną z sieci po zamknięciu programu")
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

    def on_web_link_received(self, link_url):
        item = self.pool.add_link(link_url)
        if item:
            QTimer.singleShot(0, lambda: self.refresh_my_pool_ui())
            QTimer.singleShot(0, lambda: self.status_lbl.setText(f"Otrzymano link z telefonu: {link_url}"))
            self.discovery._send_beacon("beacon")

    def copy_web_url(self):
        url = f"http://{self.local_ip}:{self.server.port}"
        QApplication.clipboard().setText(url)
        self.status_lbl.setText(f"✓ Skopiowano link WWW do schowka: {url}")

    def prompt_connect_ip(self):
        ip, ok = QInputDialog.getText(
            self,
            "Ręczne łączenie z IP",
            "Wpisz adres IP drugiego komputera w Twojej sieci Wi-Fi:\n(np. 192.168.1.11 lub 192.168.1.11:50505)",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and ip.strip():
            self.connect_to_peer_ip(ip.strip())

    def connect_to_peer_ip(self, target_raw):
        target = target_raw.replace("http://", "").replace("https://", "").strip()
        if ":" in target:
            parts = target.split(":")
            target_ip = parts[0].strip()
            try:
                target_port = int(parts[1].strip().split("/")[0])
            except Exception:
                target_port = DEFAULT_HTTP_PORT
        else:
            target_ip = target.split("/")[0].strip()
            target_port = DEFAULT_HTTP_PORT

        self.status_lbl.setText(f"Łączenie z {target_ip}:{target_port}...")
        QApplication.processEvents()

        self.discovery.known_peer_ips.add(target_ip)
        self.discovery._send_beacon("beacon", target_ip=target_ip)

        threading.Thread(target=self._fetch_manual_ip_worker, args=(target_ip, target_port), daemon=True).start()

    def _fetch_manual_ip_worker(self, ip, port):
        try:
            req = urllib.request.Request(f"http://{ip}:{port}/api/pool?t={int(time.time()*1000)}")
            req.add_header("Cache-Control", "no-cache")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                pid = data.get("deviceId", ip)
                if pid == self.device_id:
                    QTimer.singleShot(0, lambda: self.status_lbl.setText("Podano adres IP tego samego komputera."))
                    return

                parsed_files = []
                for f in data.get("files", []):
                    f_item = {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "size": f.get("size", 0),
                        "type": f.get("type", "file"),
                        "content": f.get("content"),
                        "file_count": f.get("file_count", 1)
                    }
                    if "version" in f:
                        f_item["version"] = f["version"]
                    parsed_files.append(f_item)

                with self.discovery.lock:
                    self.discovery.peers[pid] = {
                        "last_seen": time.time(),
                        "ip": ip,
                        "deviceName": data.get("deviceName", f"Komputer ({ip})"),
                        "platform": "manual_ip",
                        "port": port,
                        "version": data.get("version", 1),
                        "app_version": data.get("app_version"),
                        "files": parsed_files
                    }
                    self.discovery.peers_updated.emit(dict(self.discovery.peers))

                dev_name = data.get("deviceName", ip)
                file_cnt = len(parsed_files)
                QTimer.singleShot(0, lambda: self.status_lbl.setText(f"✓ Połączono z {dev_name} ({ip}:{port})! Pula: {file_cnt} elementów."))
                self.discovery._send_beacon("beacon", target_ip=ip)
        except Exception as e:
            QTimer.singleShot(0, lambda: self.status_lbl.setText(f"Nie udało się połączyć z {ip}:{port}: {e}"))
            QTimer.singleShot(0, lambda: QMessageBox.warning(
                self,
                "Błąd połączenia",
                f"Nie udało się połączyć z adresem {ip}:{port}.\n\n"
                f"Szczegóły: {e}\n\n"
                "Upewnij się, że:\n"
                "1. Oba komputery są połączone z tą samą siecią Wi-Fi.\n"
                "2. Program LAN Drop jest uruchomiony na drugim komputerze.\n"
                "3. Zapora Windows nie blokuje portu 50505."
            ))

    # =================================================================
    # OBSŁUGA TWOJEJ PULI (PLIKI I LINKI)
    # =================================================================

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Wybierz pliki do udostępnienia")
        if files:
            self.add_files_to_pool(files)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder do udostępnienia")
        if folder:
            self.add_folder_to_pool(folder)

    def prompt_add_link(self):
        url, ok = QInputDialog.getText(self, "Udostępnij link WWW", "Wklej adres URL do zawieszenia w puli:")
        if ok and url.strip():
            item = self.pool.add_link(url.strip())
            if item:
                self.refresh_my_pool_ui()
                self.status_lbl.setText(f"Dodano link do puli: {url.strip()}")
                self.discovery._send_beacon("beacon")

    def add_files_to_pool(self, paths):
        added = self.pool.add_files(paths)
        if added:
            self.refresh_my_pool_ui()
            self.status_lbl.setText(f"Dodano {len(added)} plik(ów) do Twojej puli.")
            self.discovery._send_beacon("beacon")

    def add_folder_to_pool(self, folder_path):
        item = self.pool.add_folder(folder_path)
        if item:
            self.refresh_my_pool_ui()
            self.status_lbl.setText(f"Dodano folder '{item.name}' ({item.file_count} plików, {format_size(item.size)}) do Twojej puli.")
            self.discovery._send_beacon("beacon")

    def add_paths_to_pool(self, paths):
        added_files = []
        added_folders = 0
        for p in paths:
            if os.path.isdir(p):
                it = self.pool.add_folder(p)
                if it:
                    added_folders += 1
            elif os.path.isfile(p):
                added_files.append(p)
        if added_files:
            self.pool.add_files(added_files)
        if added_files or added_folders:
            self.refresh_my_pool_ui()
            self.status_lbl.setText(f"Dodano do puli: {len(added_files)} plików, {added_folders} folderów.")
            self.discovery._send_beacon("beacon")

    def share_update_to_pool(self):
        # 1. Sprawdź czy aktualizacja tej wersji jest już wystawiona w naszej puli
        if any(it.type == "update" and parse_version(it.version) >= parse_version(APP_VERSION) for it in self.pool.files.values()):
            self.status_lbl.setText(f"✓ Posiadasz najnowszą wersję (v{APP_VERSION}), która jest już wystawiona w puli.")
            QMessageBox.information(
                self,
                "Aktualna wersja",
                f"Program jest już w najnowszej wersji (v{APP_VERSION}), a paczka aktualizacyjna znajduje się w sieci.\n\nŻadna nowsza aktualizacja nie jest wymagana."
            )
            return

        # 2. Sprawdź połączone urządzenia w sieci
        peers = self.discovery.peers
        if peers:
            known_peer_versions = []
            for p in peers.values():
                p_name = p.get("deviceName", "Drugi komputer")
                p_ver = None
                for f in p.get("files", []):
                    if f.get("version"):
                        p_ver = f.get("version")
                        break
                if p_ver:
                    known_peer_versions.append((p_name, p_ver))

            if known_peer_versions and all(parse_version(pv) >= parse_version(APP_VERSION) for _, pv in known_peer_versions):
                peer_desc = ", ".join(f"{pn} (v{pv})" for pn, pv in known_peer_versions)
                reply = QMessageBox.question(
                    self,
                    "Program jest aktualny",
                    f"Wszystkie komputery w sieci ({peer_desc}) posiadają już najnowszą wersję v{APP_VERSION}.\n\nCzy chcesz mimo to wystawić paczkę aktualizacyjną?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self.status_lbl.setText(f"✓ Program jest w najnowszej wersji (v{APP_VERSION}). Wszystkie komputery są zaktualizowane.")
                    return

        cur_script = os.path.abspath(__file__)
        win_dir = os.path.dirname(cur_script)
        project_root = os.path.dirname(win_dir) if os.path.basename(win_dir).lower() == "windows" else win_dir
        if not os.path.exists(project_root):
            project_root = r"C:\Lan drop pool"

        update_zip_path = os.path.join(project_root, "landrop_update.zip")

        try:
            self.status_lbl.setText("Pakowanie aktualizacji LAN Drop...")
            QApplication.processEvents()

            with zipfile.ZipFile(update_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(project_root):
                    if ".git" in root or "__pycache__" in root or ".venv" in root:
                        continue
                    for f in files:
                        if f == "landrop_update.zip" or f.endswith(".tmp") or f.endswith(".pyc"):
                            continue
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, project_root)
                        zf.write(full_p, arcname=rel_p)

            item = self.pool.add_update(update_zip_path, version=APP_VERSION)
            self.refresh_my_pool_ui()
            self.status_lbl.setText(f"🚀 Wystawiono aktualizację v{APP_VERSION} ({format_size(item.size)})! Drugi komputer wykryje ją natychmiast.")
            self.discovery._send_beacon("beacon")
            QMessageBox.information(
                self,
                "Aktualizacja wystawiona",
                f"Paczka aktualizacyjna LAN Drop (v{APP_VERSION}) została wystawiona w sieci!\n\nNa drugim komputerze natychmiast pojawi się przycisk '⚡ WGRAJ AKTUALIZACJĘ I ZRESTARTUJ'."
            )
        except Exception as e:
            self.status_lbl.setText(f"Błąd tworzenia aktualizacji: {e}")
            QMessageBox.critical(self, "Błąd", f"Nie udało się wystawić aktualizacji:\n{e}")

    def install_update(self, item, force=False):
        f = item["file"]
        dev_name = item.get("deviceName", "drugiego komputera")
        ver = f.get("version")
        if not ver:
            m = re.search(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", f.get("name", ""))
            ver = m.group(1) if m else APP_VERSION

        cur_script = os.path.abspath(__file__)
        win_dir = os.path.dirname(cur_script)
        project_root = os.path.dirname(win_dir) if os.path.basename(win_dir).lower() == "windows" else win_dir

        if force:
            prompt_msg = f"Posiadasz już wersję v{APP_VERSION}.\n\nCzy chcesz mimo to wgrać paczkę z {dev_name} ponownie, aby naprawić lub odświeżyć pliki programu?"
        else:
            prompt_msg = f"Czy chcesz pobrać i zainstalować aktualizację ({ver}) z {dev_name}?\n\nProgram automatycznie podmieni pliki w folderze:\n{project_root}\ni zrestartuje aplikację."

        reply = QMessageBox.question(
            self,
            "Wgrać aktualizację?",
            prompt_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status_lbl.setText("Pobieranie aktualizacji z sieci...")
        self.apply_update_btn.setEnabled(False)
        self.apply_update_btn.setText("Pobieranie aktualizacji...")

        worker = UpdateWorker(f["id"], f["size"], item["ip"], item["port"], target_dir=project_root)

        def on_update_prog(done, total, speed):
            pct = int((done / total) * 100) if total > 0 else 0
            self.status_lbl.setText(f"Pobieranie aktualizacji: {pct}% ({speed:.1f} MB/s)...")
            self.apply_update_btn.setText(f"Pobieranie {pct}%...")

        def on_update_finish(bat_path):
            self.status_lbl.setText("Aktualizacja pobrana. Restartowanie programu...")
            self.apply_update_btn.setText("Restartowanie...")
            try:
                self.stop_hotspot_sync()
            except Exception:
                pass

            pid = str(os.getpid())
            try:
                subprocess.Popen(
                    f'cmd.exe /c start "Aktualizacja LAN Drop" "{bat_path}" {pid}',
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            except Exception:
                subprocess.Popen(["cmd.exe", "/c", bat_path, pid])

            QApplication.quit()
            sys.exit(0)

        def on_update_fail(err):
            self.status_lbl.setText(f"Błąd aktualizacji: {err}")
            self.apply_update_btn.setEnabled(True)
            self.apply_update_btn.setText("⚡ WGRAJ AKTUALIZACJĘ I ZRESTARTUJ")
            QMessageBox.critical(self, "Błąd aktualizacji", f"Nie udało się wgrać aktualizacji:\n{err}")

        worker.progress.connect(on_update_prog)
        worker.finished.connect(on_update_finish)
        worker.failed.connect(on_update_fail)
        self.active_update_worker = worker
        worker.start()

    def remove_from_my_pool(self, file_id):
        if self.pool.remove_file(file_id):
            self.refresh_my_pool_ui()
            self.status_lbl.setText("Usunięto element z Twojej puli.")
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
            ftype = f.get("type", "file")
            is_link = ftype == "link"
            is_folder = ftype == "folder"
            is_update = ftype == "update"

            if is_link:
                prefix = "🔗 "
                size_text = "Link WWW"
            elif is_folder:
                prefix = "📁 "
                size_text = f"{format_size(f['size'])} ({f.get('file_count', 0)} pl.)"
            elif is_update:
                prefix = "🚀 [AKTUALIZACJA] "
                size_text = f"{format_size(f['size'])} (v{f.get('version', '')})"
            else:
                prefix = "📄 "
                size_text = format_size(f["size"])

            name_item = QTableWidgetItem(prefix + f["name"])
            name_item.setToolTip(f["name"])
            self.my_table.setItem(row, 0, name_item)

            size_item = QTableWidgetItem(size_text)
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

        folders_count = sum(1 for f in files if f.get("type") == "folder")
        updates_count = sum(1 for f in files if f.get("type") == "update")
        links_count = sum(1 for f in files if f.get("type") == "link")
        files_count = len(files) - folders_count - updates_count - links_count

        parts = []
        if files_count > 0:
            parts.append(f"{files_count} plik(ów)")
        if folders_count > 0:
            parts.append(f"{folders_count} folder(ów)")
        if links_count > 0:
            parts.append(f"{links_count} link(ów)")
        if updates_count > 0:
            parts.append(f"{updates_count} aktualizacja")

        summary_str = "W puli: " + (", ".join(parts) if parts else "0 elementów")
        summary_str += f" ({format_size(self.pool.total_size())})"
        self.my_summary_lbl.setText(summary_str)

    # =================================================================
    # ELEMENTY W SIECI (Z TELEFONU / INNYCH KOMPUTERÓW)
    # =================================================================

    def on_peers_updated(self, peers):
        self.peers_badge.setText(f"Urządzenia: {len(peers)}")

        previously_checked_ids = {
            item["file"]["id"]
            for cb, item in self.row_checkboxes
            if cb.isChecked()
        }

        all_remote_files = []
        update_item_found = None

        for pid, peer in peers.items():
            device_name = peer.get("deviceName", "Nieznane")
            ip = peer.get("ip")
            port = peer.get("port")
            for f in peer.get("files", []):
                item_data = {
                    "deviceId": pid,
                    "deviceName": device_name,
                    "ip": ip,
                    "port": port,
                    "file": f
                }
                all_remote_files.append(item_data)
                if (f.get("type") == "update" or "landrop_update" in f.get("name", "").lower()) and not update_item_found:
                    update_item_found = item_data

        if update_item_found:
            upd_ver = update_item_found["file"].get("version")
            if not upd_ver:
                m = re.search(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", update_item_found["file"].get("name", ""))
                upd_ver = m.group(1) if m else APP_VERSION
            upd_dev = update_item_found["deviceName"]

            if parse_version(upd_ver) > parse_version(APP_VERSION):
                self.update_banner_lbl.setText(f"⚡ WYKRYTO NOWSZĄ AKTUALIZACJĘ: LAN Drop v{upd_ver} (Twoja wersja: v{APP_VERSION}, z {upd_dev})")
                try:
                    self.apply_update_btn.clicked.disconnect()
                except Exception:
                    pass
                self.apply_update_btn.clicked.connect(lambda _, item=update_item_found: self.install_update(item))
                self.apply_update_btn.setEnabled(True)
                self.apply_update_btn.setText(f"⚡ WGRAJ AKTUALIZACJĘ (v{upd_ver}) I ZRESTARTUJ")
                self.update_banner.setVisible(True)
            else:
                self.update_banner.setVisible(False)
        else:
            self.update_banner.setVisible(False)

        self.net_table.setRowCount(len(all_remote_files))
        self.row_checkboxes.clear()

        for row, item in enumerate(all_remote_files):
            f = item["file"]
            fid = f["id"]
            ftype = f.get("type", "file")
            is_link = ftype == "link"
            is_folder = ftype == "folder"
            is_update = ftype == "update" or "landrop_update" in f.get("name", "").lower()
            link_url = f.get("content") or f.get("name")

            # Kolumna 0: Checkbox
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.setContentsMargins(6, 0, 6, 0)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setStyleSheet("""
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    background: #18181b;
                }
                QCheckBox::indicator:hover {
                    border-color: #10b981;
                }
                QCheckBox::indicator:checked {
                    background-color: #10b981;
                    border-color: #10b981;
                }
            """)
            if is_link or is_update:
                cb.setEnabled(False)
                cb.setVisible(False)
            else:
                cb.setChecked(fid in previously_checked_ids)
                self.row_checkboxes.append((cb, item))
            chk_lay.addWidget(cb)
            self.net_table.setCellWidget(row, 0, chk_widget)

            # Kolumna 1: Urządzenie
            dev_item = QTableWidgetItem(item["deviceName"])
            self.net_table.setItem(row, 1, dev_item)

            # Kolumna 2: Nazwa
            if is_link:
                prefix = "🔗 "
            elif is_folder:
                prefix = "📁 "
            elif is_update:
                prefix = "🚀 [AKTUALIZACJA] "
            else:
                prefix = "📄 "
            name_item = QTableWidgetItem(prefix + f["name"])
            name_item.setToolTip(f["name"])
            self.net_table.setItem(row, 2, name_item)

            # Kolumna 3: Rozmiar
            if is_link:
                size_text = "Link WWW"
            elif is_folder:
                size_text = f"{format_size(f['size'])} ({f.get('file_count', 0)} pl.)"
            elif is_update:
                size_text = f"{format_size(f['size'])} (v{f.get('version', '')})"
            else:
                size_text = format_size(f["size"])
            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.net_table.setItem(row, 3, size_item)

            # Kolumna 4: Akcja
            if is_link:
                act_box = QWidget()
                act_lay = QHBoxLayout(act_box)
                act_lay.setContentsMargins(0, 0, 0, 0)
                act_lay.setSpacing(6)

                open_btn = QPushButton("🌐 Otwórz")
                open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #000000;
                        font-weight: 700;
                        padding: 5px 12px;
                        border-radius: 6px;
                        border: none;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #e4e4e7; }
                """)
                open_btn.clicked.connect(lambda _, u=link_url: self.open_link(u))

                copy_btn = QPushButton("📋")
                copy_btn.setToolTip("Kopiuj link do schowka")
                copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                copy_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #18181b;
                        color: #ffffff;
                        padding: 5px 8px;
                        border-radius: 6px;
                        border: 1px solid #27272a;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #27272a; }
                """)
                copy_btn.clicked.connect(lambda _, u=link_url: self.copy_link(u))

                act_lay.addWidget(open_btn)
                act_lay.addWidget(copy_btn)
                self.net_table.setCellWidget(row, 4, act_box)

            elif is_update:
                upd_ver = f.get("version")
                if not upd_ver:
                    m = re.search(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", f.get("name", ""))
                    upd_ver = m.group(1) if m else APP_VERSION

                if parse_version(upd_ver) > parse_version(APP_VERSION):
                    upd_btn = QPushButton(f"⚡ Wgraj (v{upd_ver})")
                    upd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    upd_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #10b981;
                            color: #000000;
                            font-weight: 800;
                            padding: 6px 14px;
                            border-radius: 6px;
                            border: none;
                            font-size: 12px;
                        }
                        QPushButton:hover { background-color: #34d399; }
                    """)
                    upd_btn.clicked.connect(lambda _, item=item: self.install_update(item))
                else:
                    upd_btn = QPushButton(f"✓ v{APP_VERSION} (Wgraj ponownie)")
                    upd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    upd_btn.setToolTip("Posiadasz tę wersję. Kliknij, jeśli chcesz wgrać ponownie / naprawić pliki.")
                    upd_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #18181b;
                            color: #a1a1aa;
                            font-weight: 600;
                            padding: 6px 12px;
                            border-radius: 6px;
                            border: 1px solid #27272a;
                            font-size: 11px;
                        }
                        QPushButton:hover { background-color: #27272a; color: #10b981; border-color: #10b981; }
                    """)
                    upd_btn.clicked.connect(lambda _, item=item: self.install_update(item, force=True))
                self.net_table.setCellWidget(row, 4, upd_btn)

            else:
                if fid in self.active_downloads:
                    status_lbl = QLabel("Pobieranie...")
                    status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
                    self.net_table.setCellWidget(row, 4, status_lbl)
                else:
                    btn_label = "⬇ Pobierz folder" if is_folder else "⬇ Pobierz"
                    dl_btn = QPushButton(btn_label)
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
                    self.net_table.setCellWidget(row, 4, dl_btn)

    def toggle_select_all(self):
        downloadable_cbs = [cb for cb, item in self.row_checkboxes if item["file"].get("type") not in ("link", "update")]
        if not downloadable_cbs:
            self.status_lbl.setText("Brak plików ani folderów do zaznaczenia w sieci.")
            return

        all_checked = all(cb.isChecked() for cb in downloadable_cbs)
        new_state = not all_checked
        for cb in downloadable_cbs:
            cb.setChecked(new_state)

        if new_state:
            self.select_all_btn.setText("☐ Odznacz wszystko")
            self.status_lbl.setText(f"Zaznaczono wszystkie elementy ({len(downloadable_cbs)}). Kliknij 'Pobierz zaznaczone'.")
        else:
            self.select_all_btn.setText("☑ Zaznacz wszystko")
            self.status_lbl.setText("Odznaczono wszystkie elementy.")

    def download_selected(self):
        selected_items = [item for cb, item in self.row_checkboxes if cb.isChecked() and item["file"].get("type") not in ("link", "update")]
        if not selected_items:
            QMessageBox.information(self, "Pobieranie", "Zaznacz pliki lub foldery, które chcesz pobrać, lub kliknij 'Pobierz wszystkie'.")
            return
        self.download_batch(selected_items)

    def download_all(self):
        all_items = [item for _, item in self.row_checkboxes if item["file"].get("type") not in ("link", "update")]
        if not all_items:
            QMessageBox.information(self, "Pobieranie", "Brak plików lub folderów w sieci do pobrania.")
            return
        self.download_batch(all_items)

    def download_batch(self, items):
        count = len(items)
        started = 0
        for it in items:
            fid = it["file"]["id"]
            if fid not in self.active_downloads:
                self.start_download(it)
                started += 1
        self.status_lbl.setText(f"Rozpoczęto pobieranie {started} z {count} elementów do folderu Downloads/LanDrop (bez pakowania).")

    def open_link(self, url):
        target = url
        if not target.startswith("http://") and not target.startswith("https://"):
            target = "https://" + target
        try:
            webbrowser.open(target)
            self.status_lbl.setText(f"Otwarto w przeglądarce: {target}")
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie można otworzyć linku: {e}")

    def copy_link(self, url):
        QApplication.clipboard().setText(url)
        self.status_lbl.setText(f"Skopiowano link do schowka: {url}")

    def start_download(self, item):
        f = item["file"]
        fid = f["id"]
        fname = f["name"]
        fsize = f["size"]
        ftype = f.get("type", "file")
        ip = item["ip"]
        port = item["port"]

        if fid in self.active_downloads:
            return

        worker = DownloadWorker(fid, fname, fsize, ip, port, item_type=ftype)
        self.active_downloads[fid] = worker

        card = QFrame()
        card.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 10px;")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(8, 6, 8, 6)

        prefix = "📁 " if ftype == "folder" else "📄 "
        info_lbl = QLabel(f"{prefix}{fname} (z {item['deviceName']})")
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

        speed_lbl = QLabel("Pobieranie folderu..." if ftype == "folder" else "Pobieranie...")
        speed_lbl.setStyleSheet("font-size: 11px; color: #71717a;")

        c_lay.addWidget(info_lbl)
        c_lay.addWidget(pbar)
        c_lay.addWidget(speed_lbl)
        self.transfers_box.addWidget(card)

        def on_prog(file_id, done, total, speed_mbps):
            pct = int((done / total) * 100) if total > 0 else 0
            pbar.setValue(pct)
            action_desc = "Pobieranie folderu" if ftype == "folder" else "Pobieranie"
            speed_lbl.setText(f"{action_desc}: {format_size(done)} / {format_size(total)} | {speed_mbps:.1f} MB/s ({pct}%)")

        def on_finish(file_id, save_path):
            pbar.setValue(100)
            if ftype == "folder":
                speed_lbl.setText(f"Folder rozpakowany do: {save_path}")
                self.status_lbl.setText(f"Folder '{fname}' został pobrany i rozpakowany w Downloads/LanDrop!")
            else:
                speed_lbl.setText(f"Ukończono: {save_path}")
                self.status_lbl.setText(f"Pobrano {fname}!")
            speed_lbl.setStyleSheet("font-size: 11px; color: #10b981; font-weight: 700;")
            if file_id in self.active_downloads:
                del self.active_downloads[file_id]

        def on_fail(file_id, err):
            speed_lbl.setText(f"Błąd: {err}")
            speed_lbl.setStyleSheet("font-size: 11px; color: #ef4444;")
            if file_id in self.active_downloads:
                del self.active_downloads[file_id]

        worker.progress.connect(on_prog)
        worker.finished.connect(on_finish)
        worker.failed.connect(on_fail)
        worker.start()
        self.status_lbl.setText(f"Rozpoczęto pobieranie {fname}...")

    def open_downloads_folder(self):
        dl_dir = get_download_folder()
        try:
            if sys.platform == "win32":
                os.startfile(str(dl_dir))
            else:
                subprocess.Popen(["xdg-open", str(dl_dir)])
        except Exception:
            QMessageBox.information(self, "Pobrane", f"Folder pobranych:\n{dl_dir}")

    # =================================================================
    # OBSŁUGA PRZECIĄGNIJ I UPUŚĆ W CAŁYM OKNIE (DRAG & DROP)
    # =================================================================

    def eventFilter(self, watched, event):
        etype = event.type()
        if etype in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if hasattr(event, "mimeData") and event.mimeData().hasUrls():
                event.acceptProposedAction()
                if hasattr(self, "drop_zone"):
                    self.drop_zone.set_hover_style()
                self.status_lbl.setText("Upuść pliki lub foldery w oknie, aby dodać je do puli...")
                return True
        elif etype == QEvent.Type.DragLeave:
            if hasattr(self, "drop_zone"):
                self.drop_zone.set_idle_style()
            self.status_lbl.setText("Gotowy. Przeciągnij pliki lub foldery w dowolne miejsce okna.")
        elif etype == QEvent.Type.Drop:
            if hasattr(event, "mimeData") and event.mimeData().hasUrls():
                if hasattr(self, "drop_zone"):
                    self.drop_zone.set_idle_style()
                event.acceptProposedAction()
                self._handle_dropped_urls(event.mimeData().urls())
                return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if hasattr(self, "drop_zone"):
                self.drop_zone.set_hover_style()
            self.status_lbl.setText("Upuść pliki lub foldery w oknie, aby dodać je do puli...")

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if hasattr(self, "drop_zone"):
            self.drop_zone.set_idle_style()
        self.status_lbl.setText("Gotowy. Przeciągnij pliki lub foldery w dowolne miejsce okna.")

    def dropEvent(self, event: QDropEvent):
        if hasattr(self, "drop_zone"):
            self.drop_zone.set_idle_style()
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._handle_dropped_urls(event.mimeData().urls())

    def _handle_dropped_urls(self, urls):
        paths = [u.toLocalFile() for u in urls if os.path.exists(u.toLocalFile())]
        if paths:
            self.add_paths_to_pool(paths)

    def stop_hotspot_sync(self):
        """Synchroniczne wyłączenie punktu dostępu Wi-Fi przed zamknięciem programu."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotspot_helper.ps1")
        if not os.path.exists(script_path):
            return
        try:
            cmd = [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", script_path, "-Action", "stop"
            ]
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run(cmd, capture_output=True, text=True, timeout=12, creationflags=flags)
        except Exception:
            pass

    def closeEvent(self, event):
        self.status_lbl.setText("Zamykanie...")

        # 1. Sprawdź, czy hotspot był włączony - jeśli tak, wyłącz go NAJPIERW
        if self.hotspot_active or self.hotspot_started_by_us:
            self.status_lbl.setText("Wyłączanie punktu dostępu Wi-Fi...")
            QApplication.processEvents()

            # Pokaż czytelne okno informujące o wyłączaniu hotspotu
            dlg = QDialog(self)
            dlg.setWindowTitle("LAN Drop")
            dlg.setFixedSize(360, 150)
            dlg.setStyleSheet("background-color: #09090b; color: #ffffff; border: 1px solid #27272a; border-radius: 12px;")
            dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

            d_lay = QVBoxLayout(dlg)
            d_lay.setContentsMargins(20, 20, 20, 20)
            d_lay.setSpacing(10)
            d_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            msg = QLabel("Wyłączanie punktu dostępu Wi-Fi...")
            msg.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

            sub = QLabel("Proszę czekać, router jest bezpiecznie zatrzymywany.")
            sub.setStyleSheet("font-size: 12px; color: #a1a1aa;")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pbar = QProgressBar()
            pbar.setRange(0, 0)
            pbar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #27272a;
                    border-radius: 4px;
                    background-color: #121214;
                    height: 10px;
                }
                QProgressBar::chunk {
                    background-color: #10b981;
                    border-radius: 3px;
                }
            """)

            d_lay.addWidget(msg)
            d_lay.addWidget(sub)
            d_lay.addWidget(pbar)

            dlg.show()
            QApplication.processEvents()

            # Bezpieczne wyłączenie hotspotu w systemie Windows
            self.stop_hotspot_sync()
            self.hotspot_active = False
            self.hotspot_started_by_us = False

            dlg.accept()

        # 2. Zatrzymaj rozgłaszanie UDP i wyślij sygnał odejścia (farewell)
        self.discovery.stop()

        # 3. Zatrzymaj lokalny serwer HTTP
        self.server.stop()

        event.accept()


# =====================================================================
# START
# =====================================================================

def set_dark_titlebar(window):
    """Włącza systemowy Pure Black pasek tytułowy w Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        val = ctypes.c_int(1)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        if res != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    set_dark_titlebar(win)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
