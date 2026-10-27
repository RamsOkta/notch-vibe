import sys

IS_WINDOWS = sys.platform == "win32"

# Dimensi Notch sesuai Contoh Gambar 1 & 2 Nusa:
COMPACT_W, COMPACT_H = 250.0, 32.0     # Tertutup / Idle
MUSIC_W, MUSIC_H = 430.0, 142.0         # Gambar 1: Music Mode
LYRICS_W, LYRICS_H = 570.0, 154.0       # Gambar 2: Side-by-Side Lyrics Mode (Anti-Terpotong)

# Kanvas Tetap (Zero Window-Resize Jitter)
CANVAS_W = 620
CANVAS_H = 195
EAR_RADIUS = 12.0

# Tipografi
FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI', sans-serif"

# Win32 Virtual Key Codes
if IS_WINDOWS:
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
