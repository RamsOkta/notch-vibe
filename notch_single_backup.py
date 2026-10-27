"""
Nusa-Lite (macOS Dynamic Notch Edition) untuk Windows 10/11
===========================================================
Keunggulan Arsitektur UI & Animasi (Persis macOS Notch / Dynamic Island):
1. ZERO-JITTER FIXED CANVAS:
   Tidak lagi melakukan resize window OS saat hover! Jendela transparan dikunci pada ukuran
   kanvas tetap, sementara bentuk kurva Notch digambar & dianimasikan secara internal
   dengan kecepatan 60 FPS menggunakan fisika pegas (Spring / Critically Damped Physics).
2. MACBOOK CONCAVE TOP EARS:
   Lekukan telinga atas (concave bezier curves) menyatu mulus ke bezel atas layar
   dengan ambient drop-shadow lembut dan rim-light tipis khas macOS Sonoma/Sequoia.
3. INTERACTIVE COMPACT & EXPANDED LAYOUT:
   - Mode Compact: Jam di kiri, kamera/sensor di tengah, waveform visualizer & mini-title di kanan.
   - Mode Expanded: Album Art Vinyl berputar/berdenyut, info lagu, progress bar waktu real-time,
     tombol kontrol media bergaya Apple Music, dan kartu Synced Lyrics dari LRCLIB.
4. DETEKSI MUSIK DUAL-ENGINE (GSMTC Background + Win32 Fallback):
   Tetap mendeteksi lagu meskipun tab YouTube/Spotify tertutup tab lain di browser,
   100% kompatibel dengan Python 3.15 tanpa perlu 'winsdk' atau Visual Studio C++.

Cara Menjalankan:
   pip install PyQt6 requests
   python nusa_notch.py
"""

import sys
import re
import json
import math
import time
import random
import ctypes
from ctypes import wintypes
import threading
import subprocess
import urllib.parse
from datetime import datetime

import requests
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, QRectF, QPointF, QEasingCurve,
    pyqtSignal, pyqtProperty, QObject, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QFont, QAction, QCursor,
    QLinearGradient, QRadialGradient, QPen, QBrush, QRegion, QFontMetrics
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMenu, QGraphicsOpacityEffect, QFrame
)

# ---------------------------------------------------------------------------
# KONFIGURASI WIN32 API & WINDOWS MEDIA OVERLAY (GSMTC BRIDGE)
# ---------------------------------------------------------------------------
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def send_windows_media_key(vk_code: int):
    """Mengirim sinyal tombol media hardware (Play/Pause/Next/Prev) ke Windows."""
    if not IS_WINDOWS:
        return
    user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def get_process_exe_name(hwnd) -> str:
    """Mendapatkan nama file .exe dari sebuah window handle (Win32 API fallback)."""
    if not IS_WINDOWS:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return buf.value.split("\\")[-1].lower()
    finally:
        kernel32.CloseHandle(h_proc)
    return ""


def clean_song_metadata(raw_title: str, raw_artist: str):
    """
    Membersihkan judul lagu dari YouTube/Spotify seperti:
    '(67) Armada "Mabuk Cinta" (Official Video)' -> Title: 'Mabuk Cinta', Artist: 'Armada'
    """
    title = raw_title.strip()
    artist = raw_artist.strip()

    # Hilangkan angka notifikasi tab YouTube di awal seperti "(67) "
    title = re.sub(r"^\(\d+\)\s*", "", title)

    # Hilangkan akhiran aplikasi/browser jika berasal dari Window Title
    title = re.sub(
        r"\s+-\s+(YouTube Music|YouTube|Google Chrome|Microsoft\u200b?\s*Edge|Brave|Mozilla Firefox|Opera|VLC media player).*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    # Hilangkan tag video umum di dalam kurung
    noise_pattern = r"[\(\[\{][^)\]\}]*?(?:official|video|mv|lyric|lirik|audio|live|visualizer|hd|4k|hq|remastered|clip|version|karoke|karaoke)[^)\]\}]*?[\)\]\}]"
    title = re.sub(noise_pattern, "", title, flags=re.IGNORECASE).strip()

    # Deteksi pola tanda kutip: Armada "Mabuk Cinta" atau Armada “Mabuk Cinta”
    quote_match = re.match(r"^([^\"“”]+?)\s*[\"“]([^\"”]+)[\"”]", title)
    if quote_match:
        extracted_artist = quote_match.group(1).strip(" -–—:|")
        extracted_title = quote_match.group(2).strip()
        if extracted_artist and extracted_title:
            return extracted_title, extracted_artist

    # Deteksi pola tanda pemisah: Artis - Judul
    for sep in (" - ", " – ", " — ", " | ", " : "):
        if sep in title:
            parts = title.split(sep, 1)
            left, right = parts[0].strip(), parts[1].strip().strip('"\'“”')
            if left and right:
                return right, left

    return title.strip('"\'“” '), artist


def detect_playing_media_win32_fallback() -> dict:
    """Fallback super cepat via Win32 Window Title jika GSMTC belum merespons."""
    default_info = {
        "has_media": False,
        "title": "Tidak ada musik",
        "artist": "Putar Spotify / YouTube",
        "is_playing": False,
        "position": 0.0,
        "duration": 0.0,
    }
    if not IS_WINDOWS:
        return default_info

    found_media = []

    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        win_title = buf.value.strip()
        if not win_title:
            return True

        exe_name = get_process_exe_name(hwnd)

        if exe_name == "spotify.exe":
            if win_title.lower() not in ("spotify", "spotify free", "spotify premium"):
                t, a = clean_song_metadata(win_title, "Spotify")
                found_media.append((3, t, a, True))
        elif exe_name in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"):
            if " - YouTube" in win_title:
                t, a = clean_song_metadata(win_title, "YouTube")
                found_media.append((2, t, a, True))
        elif exe_name == "vlc.exe" and " - VLC media player" in win_title:
            t, a = clean_song_metadata(win_title, "VLC")
            found_media.append((2, t, a, True))
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    if found_media:
        found_media.sort(key=lambda x: x[0], reverse=True)
        _, title, artist, is_playing = found_media[0]
        return {
            "has_media": True,
            "title": title,
            "artist": artist,
            "is_playing": is_playing,
            "position": 0.0,
            "duration": 0.0,
        }
    return default_info


# Script PowerShell Persistent untuk membaca Windows Media Overlay (GSMTC)
POWERSHELL_GSMTC_SCRIPT = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media.Control,ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(1500) | Out-Null
    return $netTask.Result
}

$mgrType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]
$propType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties]
$mgr = Await ($mgrType::RequestAsync()) $mgrType

while ($true) {
    try {
        if ($null -eq $mgr) {
            $mgr = Await ($mgrType::RequestAsync()) $mgrType
        }
        $sessions = $mgr.GetSessions()
        $chosen = $null
        foreach ($s in $sessions) {
            $pb = $s.GetPlaybackInfo()
            if ($pb -and $pb.PlaybackStatus.ToString() -eq 'Playing') {
                $chosen = $s
                break
            }
        }
        if ($null -eq $chosen) {
            $chosen = $mgr.GetCurrentSession()
        }
        if ($null -ne $chosen) {
            $props = Await ($chosen.TryGetMediaPropertiesAsync()) $propType
            $pb = $chosen.GetPlaybackInfo()
            $tl = $chosen.GetTimelineProperties()
            $pos = 0.0
            $dur = 0.0
            if ($null -ne $tl) {
                $pos = $tl.Position.TotalSeconds
                $dur = $tl.EndTime.TotalSeconds
            }
            $out = @{
                has_media  = $true
                title      = [string]$props.Title
                artist     = [string]$props.Artist
                is_playing = ($pb.PlaybackStatus.ToString() -eq 'Playing')
                position   = [double]$pos
                duration   = [double]$dur
            }
            Write-Output ($out | ConvertTo-Json -Compress)
        } else {
            Write-Output '{"has_media":false}'
        }
    } catch {
        Write-Output '{"has_media":false}'
    }
    Start-Sleep -Milliseconds 850
}
"""


class MediaWorker(QObject):
    """Worker background Dual-Engine (GSMTC + Win32 Fallback) & Pencari Lirik LRCLIB."""
    media_updated = pyqtSignal(dict)
    lyrics_updated = pyqtSignal(list, str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.current_track_key = ""
        self.track_start_time = time.time()
        self.paused_elapsed = 0.0
        self.track_duration = 210.0
        self.was_playing = False
        self.manual_offset = 0.0
        self.lyrics_cache = {}
        self.ps_process = None

    def start_worker(self):
        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()

    def _run_worker(self):
        if not IS_WINDOWS:
            return

        creation_flags = 0x08000000  # CREATE_NO_WINDOW
        try:
            self.ps_process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NoLogo",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    POWERSHELL_GSMTC_SCRIPT,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
            )

            for line in self.ps_process.stdout:
                if not self.running:
                    break
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    data = json.loads(line)
                    if not data.get("has_media") or not data.get("title"):
                        # Jika GSMTC kosong, coba fallback Win32 Window Title
                        data = detect_playing_media_win32_fallback()
                    self._process_media_data(data)
                except Exception:
                    pass
        except Exception:
            # Jika PowerShell diblokir, jalankan fallback Win32 loop murni
            while self.running:
                data = detect_playing_media_win32_fallback()
                self._process_media_data(data)
                time.sleep(1.0)

    def _process_media_data(self, data: dict):
        if not data.get("has_media") or not data.get("title"):
            self.media_updated.emit({
                "title": "Tidak ada musik",
                "artist": "Putar Spotify / YouTube",
                "is_playing": False,
                "position": 0.0,
                "duration": 0.0,
            })
            return

        raw_title = data.get("title", "")
        raw_artist = data.get("artist", "")
        is_playing = bool(data.get("is_playing", False))
        reported_pos = float(data.get("position", 0.0))
        reported_dur = float(data.get("duration", 0.0))

        clean_title, clean_artist = clean_song_metadata(raw_title, raw_artist)
        track_key = f"{clean_title.lower()}|{clean_artist.lower()}"

        if reported_dur > 5.0:
            self.track_duration = reported_dur

        if track_key != self.current_track_key and clean_title:
            self.current_track_key = track_key
            self.track_start_time = time.time() - (reported_pos if reported_pos > 0 else 0.0)
            self.paused_elapsed = reported_pos if reported_pos > 0 else 0.0
            self.manual_offset = 0.0
            if reported_dur <= 5.0:
                self.track_duration = 210.0
            self.was_playing = is_playing
            threading.Thread(
                target=self._fetch_lyrics,
                args=(clean_title, clean_artist, raw_title),
                daemon=True,
            ).start()
        else:
            if reported_pos > 0:
                if is_playing:
                    estimated = time.time() - self.track_start_time
                    if abs(estimated - reported_pos) > 1.5:
                        self.track_start_time = time.time() - reported_pos
                else:
                    self.paused_elapsed = reported_pos
            else:
                if is_playing and not self.was_playing:
                    self.track_start_time = time.time() - self.paused_elapsed
                elif not is_playing and self.was_playing:
                    self.paused_elapsed = time.time() - self.track_start_time
            self.was_playing = is_playing

        current_pos = (
            (time.time() - self.track_start_time) if is_playing else self.paused_elapsed
        ) + self.manual_offset

        self.media_updated.emit({
            "title": clean_title,
            "artist": clean_artist if clean_artist else raw_artist,
            "is_playing": is_playing,
            "position": max(0.0, current_pos),
            "duration": max(1.0, self.track_duration),
        })

    def adjust_lyric_offset(self, delta_seconds: float):
        self.manual_offset += delta_seconds

    def reset_lyric_timer(self):
        self.track_start_time = time.time()
        self.paused_elapsed = 0.0
        self.manual_offset = 0.0

    def _fetch_lyrics(self, clean_title: str, clean_artist: str, raw_title: str):
        cache_key = f"{clean_title.lower()}|{clean_artist.lower()}"
        if cache_key in self.lyrics_cache:
            cached_lines, cached_dur = self.lyrics_cache[cache_key]
            if cached_dur > 0:
                self.track_duration = cached_dur
            self.lyrics_updated.emit(cached_lines, "Synced")
            return

        self.lyrics_updated.emit([], f"Mencari lirik: {clean_title}...")

        queries = []
        if clean_artist and clean_artist.lower() not in clean_title.lower():
            queries.append(f"{clean_artist} {clean_title}")
        queries.append(clean_title)
        if raw_title != clean_title:
            queries.append(re.sub(r"^\(\d+\)\s*", "", raw_title))

        for q in queries:
            q = q.strip()
            if not q:
                continue
            try:
                url = f"https://lrclib.net/api/search?{urllib.parse.urlencode({'q': q})}"
                resp = requests.get(url, timeout=6, headers={"User-Agent": "NusaMacNotch/2.0"})
                if resp.status_code == 200:
                    results = resp.json()
                    if not results:
                        continue

                    synced_lrc = None
                    plain_lrc = None
                    lrc_dur = 0.0
                    for item in results:
                        if item.get("syncedLyrics"):
                            synced_lrc = item["syncedLyrics"]
                            lrc_dur = float(item.get("duration") or 0.0)
                            break
                        elif item.get("plainLyrics") and not plain_lrc:
                            plain_lrc = item["plainLyrics"]
                            lrc_dur = float(item.get("duration") or 0.0)

                    if lrc_dur > 10.0 and self.track_duration == 210.0:
                        self.track_duration = lrc_dur

                    if synced_lrc:
                        parsed = self._parse_lrc(synced_lrc)
                        if parsed:
                            if parsed[-1][0] > self.track_duration:
                                self.track_duration = parsed[-1][0] + 10.0
                            self.lyrics_cache[cache_key] = (parsed, self.track_duration)
                            self.lyrics_updated.emit(parsed, "Synced")
                            return
                    elif plain_lrc:
                        lines = [
                            (i * 4.0, line.strip())
                            for i, line in enumerate(plain_lrc.splitlines())
                            if line.strip()
                        ]
                        if lines:
                            self.lyrics_cache[cache_key] = (lines, self.track_duration)
                            self.lyrics_updated.emit(lines, "Plain")
                            return
            except Exception:
                pass

        self.lyrics_updated.emit([], f"Lirik '{clean_title}' belum tersedia")

    @staticmethod
    def _parse_lrc(lrc_text: str):
        pattern = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
        parsed = []
        for line in lrc_text.splitlines():
            match = pattern.match(line.strip())
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                if text:
                    parsed.append((minutes * 60 + seconds, text))
        parsed.sort(key=lambda x: x[0])
        return parsed

    def send_command(self, cmd: str):
        if not IS_WINDOWS:
            return
        if cmd == "play_pause":
            send_windows_media_key(VK_MEDIA_PLAY_PAUSE)
        elif cmd == "next":
            send_windows_media_key(VK_MEDIA_NEXT_TRACK)
            self.reset_lyric_timer()
        elif cmd == "prev":
            send_windows_media_key(VK_MEDIA_PREV_TRACK)
            self.reset_lyric_timer()

    def stop_worker(self):
        self.running = False
        if self.ps_process:
            try:
                self.ps_process.terminate()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# KOMPONEN VISUAL KUSTOM BERGAYA MACOS DYNAMIC ISLAND / NOTCH
# ---------------------------------------------------------------------------

class AppleWaveform(QWidget):
    """Visualizer 5-bar gelombang suara organik ala Apple Music di Dynamic Island."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 15)
        self.is_playing = False
        self.phase = 0.0
        self.heights = [0.22, 0.22, 0.22, 0.22, 0.22]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)  # 25fps halus & hemat CPU

    def set_playing(self, playing: bool):
        if self.is_playing != playing:
            self.is_playing = playing
            self.update()

    def _tick(self):
        if self.is_playing:
            self.phase += 0.32
            freqs = [1.1, 1.7, 2.3, 1.4, 1.9]
            offsets = [0.0, 1.2, 2.5, 0.8, 3.1]
            for i in range(5):
                target = 0.25 + 0.70 * abs(math.sin(self.phase * freqs[i] + offsets[i]))
                self.heights[i] += (target - self.heights[i]) * 0.45
        else:
            for i in range(5):
                self.heights[i] += (0.20 - self.heights[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_w = 2.4
        gap = 1.8
        total_w = 5 * bar_w + 4 * gap
        start_x = (self.width() - total_w) / 2.0
        max_h = float(self.height() - 2)

        for i in range(5):
            h = max(2.4, self.heights[i] * max_h)
            x = start_x + i * (bar_w + gap)
            y = (self.height() - h) / 2.0  # Center-aligned seperti Apple Music waveform

            if self.is_playing:
                grad = QLinearGradient(x, y, x, y + h)
                grad.setColorAt(0.0, QColor(52, 211, 153))   # Emerald
                grad.setColorAt(0.5, QColor(251, 191, 36))   # Amber
                grad.setColorAt(1.0, QColor(244, 114, 182))  # Pink
                painter.setBrush(grad)
            else:
                painter.setBrush(QColor(113, 113, 122, 160))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, h), 1.2, 1.2)


class VinylDiscWidget(QWidget):
    """Ikon piringan hitam / Album Art yang berputar lembut saat lagu berputar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.is_playing = False
        self.angle = 0.0
        self.title_seed = "Nusa"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(40)

    def set_state(self, playing: bool, title: str):
        self.is_playing = playing
        if title:
            self.title_seed = title
        self.update()

    def _rotate(self):
        if self.is_playing:
            self.angle = (self.angle + 2.5) % 360.0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        radius = min(cx, cy) - 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle)

        # Lingkaran luar piringan hitam (Vinyl)
        vinyl_grad = QRadialGradient(0, 0, radius)
        vinyl_grad.setColorAt(0.0, QColor(40, 40, 48))
        vinyl_grad.setColorAt(0.7, QColor(18, 18, 22))
        vinyl_grad.setColorAt(1.0, QColor(35, 35, 42))
        painter.setBrush(vinyl_grad)
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        painter.drawEllipse(QPointF(0, 0), radius, radius)

        # Garis pantulan cahaya diagonal pada piringan hitam
        shine_pen = QPen(QColor(255, 255, 255, 22), 2.0)
        painter.setPen(shine_pen)
        painter.drawArc(QRectF(-radius + 5, -radius + 5, (radius - 5) * 2, (radius - 5) * 2), 35 * 16, 40 * 16)
        painter.drawArc(QRectF(-radius + 5, -radius + 5, (radius - 5) * 2, (radius - 5) * 2), 215 * 16, 40 * 16)

        # Warna tengah sampul album dinamis berdasarkan judul lagu
        h_val = sum(ord(c) for c in self.title_seed) % 360
        c1 = QColor.fromHsv(h_val, 190, 235)
        c2 = QColor.fromHsv((h_val + 45) % 360, 210, 180)
        core_r = radius * 0.46
        core_grad = QLinearGradient(-core_r, -core_r, core_r, core_r)
        core_grad.setColorAt(0.0, c1)
        core_grad.setColorAt(1.0, c2)

        painter.setBrush(core_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0, 0), core_r, core_r)

        # Lubang tengah piringan hitam
        painter.setBrush(QColor(12, 12, 15))
        painter.drawEllipse(QPointF(0, 0), 3.2, 3.2)

        painter.restore()


class SmoothProgressBar(QWidget):
    """Progress bar durasi lagu tipis & elegan ala macOS Media Player."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.progress = 0.0  # 0.0 s/d 1.0

    def set_progress(self, value: float):
        val = max(0.0, min(1.0, value))
        if abs(val - self.progress) > 0.001:
            self.progress = val
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = 3.5
        y = (self.height() - h) / 2.0

        # Track latar belakang
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 32))
        painter.drawRoundedRect(QRectF(0.0, y, w, h), 1.75, 1.75)

        # Fill progress aktif
        fill_w = max(4.0, w * self.progress) if self.progress > 0 else 0.0
        if fill_w > 0:
            grad = QLinearGradient(0.0, 0.0, fill_w, 0.0)
            grad.setColorAt(0.0, QColor(255, 255, 255, 230))
            grad.setColorAt(1.0, QColor(52, 211, 153, 255))
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(0.0, y, fill_w, h), 1.75, 1.75)


class LivingNotch(QWidget):
    """
    Notch macOS / Dynamic Island dengan Kanvas Tetap (Zero Window-Resize Jitter)
    dan Fisika Pegas (Spring Morphing) 60 FPS.
    """

    # Ukuran Notch saat tertutup (Compact) dan saat terbuka (Expanded)
    COMPACT_W, COMPACT_H = 260.0, 35.0
    EXPANDED_W, EXPANDED_H = 470.0, 196.0

    # Padding ekstra untuk menampung lonjakan pegas (Spring Overshoot) & Bayangan (Drop Shadow)
    CANVAS_W = 540
    CANVAS_H = 235
    EAR_RADIUS = 13.0

    def __init__(self):
        super().__init__()
        self.is_expanded = False
        self.show_lyrics = True
        self.current_lyrics = []
        self.lyrics_status = "Menunggu musik..."
        self.last_position = 0.0
        self.track_duration = 210.0
        self.last_update_timestamp = time.time()
        self.is_playing = False

        # Variabel internal untuk animasi morfologi 60fps tanpa mengubah ukuran jendela OS
        self._notch_w = self.COMPACT_W
        self._notch_h = self.COMPACT_H
        self._morph_progress = 0.0  # 0.0 = Compact, 1.0 = Expanded

        # Konfigurasi Jendela Transparan, Frameless, Always on Top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Kunci ukuran jendela OS sekali saja di tengah atas layar (Anti-Flicker!)
        screen_x, screen_w = self._get_screen_geometry()
        win_x = screen_x + (screen_w - self.CANVAS_W) // 2
        self.setGeometry(win_x, 0, self.CANVAS_W, self.CANVAS_H)

        self._init_ui()
        self._init_animations()
        self._init_timers()
        self._update_mask_and_layout()

        # Jalankan Worker Deteksi Musik & Lirik
        self.worker = MediaWorker()
        self.worker.media_updated.connect(self._on_media_updated)
        self.worker.lyrics_updated.connect(self._on_lyrics_updated)
        self.worker.start_worker()

        QApplication.instance().aboutToQuit.connect(self.worker.stop_worker)

    # --- Properti Qt untuk dianimasikan secara mulus pada 60 FPS ---
    @pyqtProperty(float)
    def notchWidth(self) -> float:
        return self._notch_w

    @notchWidth.setter
    def notchWidth(self, val: float):
        self._notch_w = val
        self._update_mask_and_layout()
        self.update()

    @pyqtProperty(float)
    def notchHeight(self) -> float:
        return self._notch_h

    @notchHeight.setter
    def notchHeight(self, val: float):
        self._notch_h = val
        self._update_mask_and_layout()
        self.update()

    @pyqtProperty(float)
    def morphProgress(self) -> float:
        return self._morph_progress

    @morphProgress.setter
    def morphProgress(self, val: float):
        self._morph_progress = val
        self.update()

    def _get_screen_geometry(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            return geom.x(), geom.width()
        return 0, 1920

    def _get_pill_rect(self) -> QRectF:
        """Menghitung koordinat pill Notch tepat di tengah kanvas."""
        x = (self.CANVAS_W - self._notch_w) / 2.0
        return QRectF(x, 0.0, self._notch_w, self._notch_h)

    def _update_mask_and_layout(self):
        """
        Memperbarui posisi konten internal & QRegion Mask agar bagian luar Notch
        100% tembus klik (click-through) ke aplikasi di bawahnya.
        """
        rect = self._get_pill_rect()
        ear = self.EAR_RADIUS

        # Posisikan container konten tepat di dalam batas lekukan Notch saat ini
        inner_x = int(rect.x() + ear + 10)
        inner_w = int(rect.width() - (ear + 10) * 2)
        inner_h = int(rect.height() - 6)
        self.inner_container.setGeometry(inner_x, 4, max(100, inner_w), max(24, inner_h))

        # Masking klik hanya seluas area Notch aktif (+ sedikit margin bawah)
        mask_rect = QRect(
            int(rect.x()),
            0,
            int(rect.width()),
            int(rect.height() + 4),
        )
        self.setMask(QRegion(mask_rect))

    def _init_ui(self):
        self.inner_container = QWidget(self)
        self.inner_container.setMouseTracking(True)

        self.main_layout = QVBoxLayout(self.inner_container)
        self.main_layout.setContentsMargins(4, 2, 4, 6)
        self.main_layout.setSpacing(6)

        # --- BARIS ATAS: Jam (Kiri) • Indikator Kamera Tengah • Waveform & Status (Kanan) ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 2, 0)
        top_bar.setSpacing(8)

        self.clock_label = QLabel("00:00")
        self.clock_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.clock_label.setStyleSheet("color: #FFFFFF; letter-spacing: 0.3px;")

        self.status_container = QWidget()
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)

        self.waveform = AppleWaveform(self)
        self.status_dot = QLabel("(• ‿ •)")
        self.status_dot.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.status_dot.setStyleSheet("color: #A1A1AA;")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        status_layout.addWidget(self.waveform)
        status_layout.addWidget(self.status_dot)

        top_bar.addWidget(self.clock_label)
        top_bar.addStretch()
        top_bar.addWidget(self.status_container)
        self.main_layout.addLayout(top_bar)

        # --- KONTEN SAAT NOTCH TERBUKA (Expanded Dashboard) ---
        self.expanded_container = QWidget()
        exp_layout = QVBoxLayout(self.expanded_container)
        exp_layout.setContentsMargins(2, 4, 2, 0)
        exp_layout.setSpacing(7)

        self.expanded_opacity = QGraphicsOpacityEffect(self.expanded_container)
        self.expanded_opacity.setOpacity(0.0)
        self.expanded_container.setGraphicsEffect(self.expanded_opacity)

        # Baris 1: Vinyl Disc + Judul/Artis + Tombol Kontrol Media Apple-Style
        media_row = QHBoxLayout()
        media_row.setSpacing(10)

        self.vinyl_widget = VinylDiscWidget(self)
        media_row.addWidget(self.vinyl_widget)

        song_info_col = QVBoxLayout()
        song_info_col.setSpacing(1)
        song_info_col.setContentsMargins(0, 2, 0, 2)

        self.song_title_lbl = QLabel("Tidak ada musik")
        self.song_title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.song_title_lbl.setStyleSheet("color: #FFFFFF;")

        self.song_artist_lbl = QLabel("Putar Spotify / YouTube")
        self.song_artist_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.song_artist_lbl.setStyleSheet("color: #A1A1AA;")

        song_info_col.addWidget(self.song_title_lbl)
        song_info_col.addWidget(self.song_artist_lbl)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(5)

        self.btn_prev = self._create_control_btn("⏮", lambda: self.worker.send_command("prev"), "Sebelumnya", width=30)
        self.btn_play = self._create_control_btn("⏯", lambda: self.worker.send_command("play_pause"), "Putar / Jeda", width=34, primary=True)
        self.btn_next = self._create_control_btn("⏭", lambda: self.worker.send_command("next"), "Berikutnya", width=30)
        self.btn_sync_back = self._create_control_btn("-1s", lambda: self.worker.adjust_lyric_offset(-1.0), "Mundurkan lirik 1 detik", width=32)
        self.btn_sync_fwd = self._create_control_btn("+1s", lambda: self.worker.adjust_lyric_offset(1.0), "Majukan lirik 1 detik", width=32)

        controls_row.addWidget(self.btn_prev)
        controls_row.addWidget(self.btn_play)
        controls_row.addWidget(self.btn_next)
        controls_row.addWidget(self.btn_sync_back)
        controls_row.addWidget(self.btn_sync_fwd)

        media_row.addLayout(song_info_col, stretch=1)
        media_row.addLayout(controls_row)
        exp_layout.addLayout(media_row)

        # Baris 2: Progress Bar Waktu Lagu Real-Time (01:15 ━━━━━━─── 03:40)
        timeline_row = QHBoxLayout()
        timeline_row.setContentsMargins(2, 0, 2, 0)
        timeline_row.setSpacing(8)

        self.time_elapsed_lbl = QLabel("00:00")
        self.time_elapsed_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        self.time_elapsed_lbl.setStyleSheet("color: #71717A;")

        self.progress_bar = SmoothProgressBar(self)

        self.time_total_lbl = QLabel("03:30")
        self.time_total_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        self.time_total_lbl.setStyleSheet("color: #71717A;")

        timeline_row.addWidget(self.time_elapsed_lbl)
        timeline_row.addWidget(self.progress_bar, stretch=1)
        timeline_row.addWidget(self.time_total_lbl)
        exp_layout.addLayout(timeline_row)

        # Baris 3: Kartu Synced Lyrics (Frosted Glass Pill)
        self.lyrics_box = QFrame()
        self.lyrics_box.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.055);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 12px;
            }
        """)
        lyrics_layout = QVBoxLayout(self.lyrics_box)
        lyrics_layout.setContentsMargins(12, 6, 12, 6)
        lyrics_layout.setSpacing(2)

        self.lyric_current_lbl = QLabel("♪ Menunggu lagu diputar...")
        self.lyric_current_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lyric_current_lbl.setStyleSheet("color: #FBBF24; background: transparent; border: none;")
        self.lyric_current_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_current_lbl.setWordWrap(True)

        self.lyric_next_lbl = QLabel("Arahkan kursor ke Notch untuk kontrol penuh")
        self.lyric_next_lbl.setFont(QFont("Segoe UI", 8))
        self.lyric_next_lbl.setStyleSheet("color: #71717A; background: transparent; border: none;")
        self.lyric_next_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lyrics_layout.addWidget(self.lyric_current_lbl)
        lyrics_layout.addWidget(self.lyric_next_lbl)
        exp_layout.addWidget(self.lyrics_box)

        self.expanded_container.hide()
        self.main_layout.addWidget(self.expanded_container)

    def _create_control_btn(
        self, text: str, callback, tooltip: str = "", width: int = 30, primary: bool = False
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(width, 28)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if tooltip:
            btn.setToolTip(tooltip)
        btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.18);
                    color: #FFFFFF;
                    border: 1px solid rgba(255, 255, 255, 0.22);
                    border-radius: 9px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.30);
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.40);
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #E4E4E7;
                    border: 1px solid rgba(255, 255, 255, 0.07);
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.18);
                    color: #FFFFFF;
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.26);
                }
            """)
        btn.clicked.connect(callback)
        return btn

    def _init_animations(self):
        """
        Menggunakan kurva pegas (OutBack) untuk lebar dan kurva eksponensial halus (OutExpo)
        untuk tinggi sehingga gerakan persis seperti cairan Dynamic Island di macOS/iOS.
        """
        self.anim_w = QPropertyAnimation(self, b"notchWidth")
        self.anim_h = QPropertyAnimation(self, b"notchHeight")
        self.anim_morph = QPropertyAnimation(self, b"morphProgress")
        self.anim_opacity = QPropertyAnimation(self.expanded_opacity, b"opacity")

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.anim_w)
        self.anim_group.addAnimation(self.anim_h)
        self.anim_group.addAnimation(self.anim_morph)
        self.anim_group.addAnimation(self.anim_opacity)
        self.anim_group.finished.connect(self._on_animation_finished)

    def _init_timers(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock_and_lyrics)
        self.clock_timer.start(150)
        self._update_clock_and_lyrics()

        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._collapse_notch)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = max(0, int(seconds))
        return f"{s // 60:02d}:{s % 60:02d}"

    def _update_clock_and_lyrics(self):
        now = datetime.now()
        if self.is_expanded:
            self.clock_label.setText(now.strftime("%a, %d %b  •  %H:%M:%S"))
        else:
            self.clock_label.setText(now.strftime("%H:%M"))

        elapsed = (
            self.last_position + (time.time() - self.last_update_timestamp)
            if self.is_playing
            else self.last_position
        )

        # Update progress bar & label durasi
        if self.is_playing or self.last_position > 0:
            self.time_elapsed_lbl.setText(self._fmt_time(elapsed))
            self.time_total_lbl.setText(self._fmt_time(self.track_duration))
            self.progress_bar.set_progress(elapsed / max(1.0, self.track_duration))
        else:
            self.time_elapsed_lbl.setText("00:00")
            self.time_total_lbl.setText("00:00")
            self.progress_bar.set_progress(0.0)

        # Update sinkronisasi baris lirik
        if self.current_lyrics and self.is_playing:
            idx = 0
            for i, (sec, _) in enumerate(self.current_lyrics):
                if elapsed >= sec:
                    idx = i
                else:
                    break

            curr_text = self.current_lyrics[idx][1]
            next_text = (
                self.current_lyrics[idx + 1][1]
                if idx + 1 < len(self.current_lyrics)
                else ""
            )
            self.lyric_current_lbl.setText(f"♪ {curr_text}")
            self.lyric_next_lbl.setText(next_text)
            if not self.is_expanded:
                short_lyric = curr_text[:15] + "…" if len(curr_text) > 15 else curr_text
                self.status_dot.setText(short_lyric)
                self.status_dot.setStyleSheet("color: #FBBF24;")

    def _on_media_updated(self, info: dict):
        self.is_playing = info["is_playing"]
        self.last_position = info["position"]
        self.track_duration = info.get("duration", 210.0)
        self.last_update_timestamp = time.time()

        title = info["title"]
        artist = info["artist"]

        self.waveform.set_playing(self.is_playing)
        self.vinyl_widget.set_state(self.is_playing, title)

        # Elide teks secara rapi agar tidak pernah merusak layout
        fm_title = QFontMetrics(self.song_title_lbl.font())
        fm_artist = QFontMetrics(self.song_artist_lbl.font())
        self.song_title_lbl.setText(fm_title.elidedText(title, Qt.TextElideMode.ElideRight, 210))
        self.song_artist_lbl.setText(fm_artist.elidedText(artist, Qt.TextElideMode.ElideRight, 210))
        self.btn_play.setText("⏸" if self.is_playing else "▶")

        if not self.is_expanded:
            if self.is_playing and not self.current_lyrics:
                short_title = title[:14] + "…" if len(title) > 14 else title
                self.status_dot.setText(short_title)
                self.status_dot.setStyleSheet("color: #F4F4F5;")
            elif not self.is_playing:
                self.status_dot.setText("(• ‿ •)")
                self.status_dot.setStyleSheet("color: #A1A1AA;")
        else:
            self.status_dot.setText("Playing" if self.is_playing else "Paused")
            self.status_dot.setStyleSheet("color: #34D399;" if self.is_playing else "color: #A1A1AA;")

    def _on_lyrics_updated(self, lyrics_list: list, status: str):
        self.current_lyrics = lyrics_list
        self.lyrics_status = status
        if not lyrics_list:
            self.lyric_current_lbl.setText(f"♪ {status}")
            self.lyric_next_lbl.setText("")
        else:
            self.lyric_current_lbl.setText(f"♪ {lyrics_list[0][1]}")
            self.lyric_next_lbl.setText(lyrics_list[1][1] if len(lyrics_list) > 1 else "")

    def _toggle_lyrics_view(self):
        self.show_lyrics = not self.show_lyrics
        self.lyrics_box.setVisible(self.show_lyrics)
        self.EXPANDED_H = 196.0 if self.show_lyrics else 128.0
        if self.is_expanded:
            self._expand_notch(force=True)

    def enterEvent(self, event):
        self.collapse_timer.stop()
        if not self.is_expanded:
            self._expand_notch()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Tunggu 220ms sebelum menutup agar gerakan kursor di tepi tidak memicu kedipan
        self.collapse_timer.start(220)
        super().leaveEvent(event)

    def _expand_notch(self, force: bool = False):
        self.is_expanded = True
        self.expanded_container.show()
        self.anim_group.stop()

        # Lebar melompat dengan kurva pegas lembut (OutBack) seperti Dynamic Island macOS
        spring_curve = QEasingCurve(QEasingCurve.Type.OutBack)
        spring_curve.setOvershoot(0.85)

        self.anim_w.setDuration(360)
        self.anim_w.setEasingCurve(spring_curve)
        self.anim_w.setStartValue(self._notch_w)
        self.anim_w.setEndValue(self.EXPANDED_W)

        self.anim_h.setDuration(330)
        self.anim_h.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.anim_h.setStartValue(self._notch_h)
        self.anim_h.setEndValue(self.EXPANDED_H)

        self.anim_morph.setDuration(330)
        self.anim_morph.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim_morph.setStartValue(self._morph_progress)
        self.anim_morph.setEndValue(1.0)

        self.anim_opacity.setDuration(240)
        self.anim_opacity.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim_opacity.setStartValue(self.expanded_opacity.opacity())
        self.anim_opacity.setEndValue(1.0)

        self.anim_group.start()
        self._update_clock_and_lyrics()

    def _collapse_notch(self):
        if self.is_expanded:
            # Pastikan kursor benar-benar sudah berada di luar area Notch
            local_pos = self.mapFromGlobal(QCursor.pos())
            if self._get_pill_rect().contains(QPointF(local_pos)):
                return

            self.is_expanded = False
            self.anim_group.stop()

            self.anim_w.setDuration(290)
            self.anim_w.setEasingCurve(QEasingCurve.Type.OutQuart)
            self.anim_w.setStartValue(self._notch_w)
            self.anim_w.setEndValue(self.COMPACT_W)

            self.anim_h.setDuration(270)
            self.anim_h.setEasingCurve(QEasingCurve.Type.OutQuart)
            self.anim_h.setStartValue(self._notch_h)
            self.anim_h.setEndValue(self.COMPACT_H)

            self.anim_morph.setDuration(270)
            self.anim_morph.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_morph.setStartValue(self._morph_progress)
            self.anim_morph.setEndValue(0.0)

            self.anim_opacity.setDuration(120)
            self.anim_opacity.setEasingCurve(QEasingCurve.Type.InQuad)
            self.anim_opacity.setStartValue(self.expanded_opacity.opacity())
            self.anim_opacity.setEndValue(0.0)

            self.anim_group.start()
            self._update_clock_and_lyrics()

    def _on_animation_finished(self):
        if not self.is_expanded:
            self.expanded_container.hide()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #141418;
                color: #F4F4F5;
                border: 1px solid #27272A;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #27272A;
            }
        """)
        toggle_lrc_action = QAction("Sembunyikan / Tampilkan Lirik", self)
        toggle_lrc_action.triggered.connect(self._toggle_lyrics_view)

        reset_sync_action = QAction("Reset Timer Lirik ke Awal (0:00)", self)
        reset_sync_action.triggered.connect(self.worker.reset_lyric_timer)

        quit_action = QAction("Keluar dari Nusa-Lite", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(toggle_lrc_action)
        menu.addAction(reset_sync_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    @staticmethod
    def _build_mac_notch_path(x: float, w: float, h: float, ear_r: float, corner_r: float) -> QPainterPath:
        """
        Membangun kurva geometri mulus Notch MacBook Pro dengan:
        - Concave Top Ears (telinga atas melengkung ke luar menyatu dengan tepi atas monitor)
        - Smooth Convex Bottom Corners (sudut bawah melengkung mulus seperti kapsul Apple)
        """
        corner_r = min(corner_r, max(4.0, h - ear_r - 2.0))
        path = QPainterPath()
        # Mulai dari ujung kiri telinga atas
        path.moveTo(x, 0.0)
        # Lekukan telinga kiri atas (concave)
        path.cubicTo(x + ear_r * 0.55, 0.0, x + ear_r, ear_r * 0.45, x + ear_r, ear_r)
        # Turun ke sudut kiri bawah
        path.lineTo(x + ear_r, h - corner_r)
        # Sudut kiri bawah (convex)
        path.cubicTo(
            x + ear_r, h - corner_r * 0.45,
            x + ear_r + corner_r * 0.45, h,
            x + ear_r + corner_r, h
        )
        # Garis datar bawah
        path.lineTo(x + w - ear_r - corner_r, h)
        # Sudut kanan bawah (convex)
        path.cubicTo(
            x + w - ear_r - corner_r * 0.45, h,
            x + w - ear_r, h - corner_r * 0.45,
            x + w - ear_r, h - corner_r
        )
        # Naik ke telinga kanan atas
        path.lineTo(x + w - ear_r, ear_r)
        # Lekukan telinga kanan atas (concave)
        path.cubicTo(x + w - ear_r, ear_r * 0.45, x + w - ear_r * 0.55, 0.0, x + w, 0.0)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._get_pill_rect()
        x = rect.x()
        w = rect.width()
        h = rect.height()
        ear_r = self.EAR_RADIUS
        # Radius sudut bawah membesar secara mulus dari 15px (compact) ke 24px (expanded)
        corner_r = 15.0 + 9.0 * self._morph_progress

        # 1. Gambar Ambient Drop Shadow bertingkat (Soft macOS Window Shadow)
        for i in range(1, 5):
            spread = float(i * 2.5)
            alpha = int(28 - i * 5)
            if alpha > 0:
                shadow_path = self._build_mac_notch_path(
                    x - spread * 0.4,
                    w + spread * 0.8,
                    h + spread,
                    ear_r,
                    corner_r + spread * 0.5,
                )
                painter.fillPath(shadow_path, QColor(0, 0, 0, alpha))

        # 2. Gambar Bodi Utama Notch (Deep Pitch-Black OLED khas MacBook Notch)
        main_path = self._build_mac_notch_path(x, w, h, ear_r, corner_r)
        bg_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        bg_grad.setColorAt(0.0, QColor(8, 8, 10, 255))
        bg_grad.setColorAt(0.75, QColor(12, 12, 16, 254))
        bg_grad.setColorAt(1.0, QColor(16, 16, 22, 252))
        painter.fillPath(main_path, bg_grad)

        # 3. Gambar Lensa Kamera & Indikator Sensor di Tengah Atas (Detail Autentik MacBook)
        cam_cx = x + w / 2.0
        cam_cy = 17.0
        # Cincin luar lensa kamera
        painter.setPen(QPen(QColor(38, 38, 46, 180), 1.0))
        painter.setBrush(QColor(15, 15, 20))
        painter.drawEllipse(QPointF(cam_cx, cam_cy), 4.5, 4.5)
        # Pantulan kaca biru gelap di dalam lensa
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 58, 138, 150))
        painter.drawEllipse(QPointF(cam_cx - 1.0, cam_cy - 1.0), 1.8, 1.8)

        # Titik LED indikator hijau/oranye kecil di sebelah kanan kamera saat musik aktif
        if self.is_playing:
            painter.setBrush(QColor(52, 211, 153, 230))
            painter.drawEllipse(QPointF(cam_cx + 12.0, cam_cy), 2.0, 2.0)

        # 4. Rim Light (Garis kilau kaca tipis di sepanjang lekukan bawah, tanpa mencoret tepi atas)
        rim_grad = QLinearGradient(x, 0.0, x, h)
        rim_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        rim_grad.setColorAt(0.35, QColor(255, 255, 255, 18))
        rim_grad.setColorAt(1.0, QColor(255, 255, 255, 42))
        painter.setPen(QPen(QBrush(rim_grad), 1.1))
        painter.drawPath(main_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    notch = LivingNotch()
    notch.show()
    sys.exit(app.exec())