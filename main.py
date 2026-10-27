"""
Nusa-Lite (macOS Dynamic Notch Edition) untuk Windows 10/11
===========================================================
Entry point utama aplikasi.
"""

import sys
from PyQt6.QtWidgets import QApplication
from notch_window import LivingNotch


def main():
    app = QApplication(sys.argv)
    notch = LivingNotch()
    notch.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
