import json
import time
import threading
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal

from config import (
    IS_WINDOWS,
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PREV_TRACK,
    VK_MEDIA_PLAY_PAUSE,
)
from media.win32_api import (
    send_windows_media_key,
    clean_song_metadata,
    detect_playing_media_win32_fallback,
)
from media.lyrics import fetch_lyrics_from_lrclib
from media.artwork import fetch_artwork_url, download_artwork_bytes

# Script PowerShell GSMTC dengan kalkulasi presisi tinggi via LastUpdatedTime WinRT
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
            $isPlaying = ($pb.PlaybackStatus.ToString() -eq 'Playing')
            $pos = 0.0
            $dur = 0.0
            if ($null -ne $tl) {
                $pos = [double]$tl.Position.TotalSeconds
                $dur = [double]$tl.EndTime.TotalSeconds
                # Kompensasi posisi waktu nyata: tambahkan selisih detik sejak snapshot LastUpdatedTime
                if ($isPlaying -and $null -ne $tl.LastUpdatedTime -and $tl.LastUpdatedTime.Ticks -gt 0) {
                    $now = [DateTimeOffset]::UtcNow
                    $diff = ($now - $tl.LastUpdatedTime.ToUniversalTime()).TotalSeconds
                    if ($diff -gt 0 -and $diff -lt 86400) {
                        $rate = 1.0
                        if ($pb.PlaybackRate) { $rate = [double]$pb.PlaybackRate }
                        $pos += ($diff * $rate)
                    }
                }
            }
            $out = @{
                has_media  = $true
                title      = [string]$props.Title
                artist     = [string]$props.Artist
                is_playing = $isPlaying
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
    Start-Sleep -Milliseconds 600
}
"""


class MediaWorker(QObject):
    """
    Worker background Dual-Engine (GSMTC + Win32 Fallback),
    Pencari Lirik Tersinkronisasi LRCLIB, dan Cover Art Resmi iTunes.
    """
    media_updated = pyqtSignal(dict)
    lyrics_updated = pyqtSignal(list, str)
    artwork_updated = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.running = True
        self.current_track_key = ""
        self.track_duration = 210.0
        self.current_position = 0.0
        self.local_anchor_time = time.monotonic()
        self.is_playing = False
        self.manual_offset = 0.0
        self.current_art_key = ""
        self.ps_process = None

    def start_worker(self):
        # 1. Thread pembaca GSMTC / Win32
        threading.Thread(target=self._run_media_listener, daemon=True).start()
        # 2. Thread pemancar waktu halus (High-frequency clock, 60fps / 16ms accuracy)
        threading.Thread(target=self._run_clock_emitter, daemon=True).start()

    def _run_media_listener(self):
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
                        data = detect_playing_media_win32_fallback()
                    self._process_media_data(data)
                except Exception:
                    pass
        except Exception:
            # Fallback murni Win32 loop
            while self.running:
                data = detect_playing_media_win32_fallback()
                self._process_media_data(data)
                time.sleep(1.0)

    def _process_media_data(self, data: dict):
        if not data.get("has_media") or not data.get("title"):
            self.is_playing = False
            self.current_position = 0.0
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
        track_key = f"{clean_artist.lower()}|{clean_title.lower()}"

        if reported_dur > 5.0:
            self.track_duration = reported_dur

        # Lagu Baru Berputar
        if track_key != self.current_track_key and clean_title:
            self.current_track_key = track_key
            self.is_playing = is_playing
            self.current_position = max(0.0, reported_pos)
            self.local_anchor_time = time.monotonic()
            self.manual_offset = 0.0
            if reported_dur <= 5.0:
                self.track_duration = 210.0

            # Cari Lirik & Artwork di Background Thread
            threading.Thread(
                target=self._fetch_lyrics_and_art,
                args=(clean_title, clean_artist, raw_title, self.track_duration),
                daemon=True,
            ).start()
        else:
            # Lagu Sama: sinkronisasikan clock lokal dengan GSMTC jika ada pergeseran (seek)
            self.is_playing = is_playing
            if is_playing:
                # Hitung posisi lokal saat ini
                local_elapsed = self.current_position + (time.monotonic() - self.local_anchor_time)
                drift = abs(local_elapsed - reported_pos)
                if drift > 1.8:
                    # User melakukan seek bar di Spotify / YouTube: update langsung
                    self.current_position = reported_pos
                    self.local_anchor_time = time.monotonic()
                else:
                    # Nudge halus untuk mengoreksi drift milidetik tanpa melompat
                    self.current_position += (reported_pos - local_elapsed) * 0.20
            else:
                self.current_position = reported_pos
                self.local_anchor_time = time.monotonic()

    def _run_clock_emitter(self):
        """Loop clock 30 FPS untuk memberikan posisi real-time yang mulus ke UI."""
        while self.running:
            try:
                if self.is_playing:
                    now_mono = time.monotonic()
                    live_pos = self.current_position + (now_mono - self.local_anchor_time) + self.manual_offset
                else:
                    live_pos = self.current_position + self.manual_offset

                # Emit posisi presisi ke UI jika track aktif
                if self.current_track_key and self.running:
                    parts = self.current_track_key.split("|", 1)
                    artist = parts[0].title() if len(parts) > 0 else ""
                    title = parts[1].title() if len(parts) > 1 else ""
                    self.media_updated.emit({
                        "title": title,
                        "artist": artist,
                        "is_playing": self.is_playing,
                        "position": max(0.0, min(live_pos, self.track_duration)),
                        "duration": max(1.0, self.track_duration),
                    })
            except Exception:
                break
            time.sleep(0.033)  # ~30fps clock sync

    def _fetch_lyrics_and_art(self, clean_title: str, clean_artist: str, raw_title: str, duration: float):
        try:
            # 1. Ambil Lirik
            if self.running:
                self.lyrics_updated.emit([], f"Mencari lirik: {clean_title}...")
            parsed, sync_type, lrc_dur = fetch_lyrics_from_lrclib(clean_title, clean_artist, raw_title, duration)
            if not self.running:
                return

            if parsed:
                if lrc_dur > 10.0:
                    self.track_duration = lrc_dur
                self.lyrics_updated.emit(parsed, sync_type)
            else:
                self.lyrics_updated.emit([], f"Lirik '{clean_title}' belum tersedia")

            # 2. Ambil Cover Art Resmi dari iTunes
            art_key = f"{clean_artist.lower()}|{clean_title.lower()}"
            if art_key != self.current_art_key:
                self.current_art_key = art_key
                art_url = fetch_artwork_url(clean_title, clean_artist)
                if not self.running:
                    return
                if art_url:
                    img_bytes = download_artwork_bytes(art_url)
                    if self.running:
                        self.artwork_updated.emit(img_bytes if img_bytes else b"")
                else:
                    if self.running:
                        self.artwork_updated.emit(b"")
        except Exception:
            pass

    def adjust_lyric_offset(self, delta_seconds: float):
        self.manual_offset += delta_seconds

    def reset_lyric_timer(self):
        self.manual_offset = 0.0

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
