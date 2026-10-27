import sys
import re
import ctypes
from ctypes import wintypes

from config import (
    IS_WINDOWS,
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PREV_TRACK,
    VK_MEDIA_STOP,
    VK_MEDIA_PLAY_PAUSE,
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
)

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
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
