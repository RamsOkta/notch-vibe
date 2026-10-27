"""
Nusa-Lite (macOS Dynamic Notch Edition)
=======================================
File ini dipertahankan untuk backward compatibility.
Kini kode telah dipecah secara modular:
- main.py: Entry point
- notch_window.py: LivingNotch Window
- widgets/: Komponen UI visual (AppleWaveform, VinylDiscWidget, SmoothProgressBar)
- media/: Deteksi media Windows & Lirik (MediaWorker, LRCLIB, Win32 API)
- config.py: Konfigurasi & konstanta ukuran
"""

import sys
from main import main
from notch_window import LivingNotch

if __name__ == "__main__":
    main()
