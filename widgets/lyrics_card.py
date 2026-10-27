from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QWidget
)
from config import FONT_FAMILY


class AppleLyricsWidget(QWidget):
    """
    Tampilan Lirik Karaoke Kolom Kanan Sesuai Gambar 2 Nusa:
    - Tidak terpotong (Auto-Wrap dengan alokasi ruang vertikal optimal)
    - Teks Rata Kiri (Left-Aligned) Bersih
    - Baris 1: Lirik sebelumnya (11.5px, color: rgba(255, 255, 255, 0.35))
    - Baris 2: Lirik aktif saat ini (14.5px, color: #FFFFFF, tebal font-weight: 700)
    - Baris 3: Lirik berikutnya (11.5px, color: rgba(255, 255, 255, 0.50))
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lyrics_list = []
        self.current_idx = -1
        self.status_msg = "Menunggu lagu..."

        self.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 2, 6, 2)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Baris 1: Lirik Sebelumnya
        self.lbl_prev = QLabel("")
        self.lbl_prev.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.lbl_prev.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            font-family: {FONT_FAMILY};
        """)
        self.lbl_prev.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_prev.setWordWrap(True)

        # Baris 2: Lirik Aktif Saat Ini (Putih Bersih 100%, Tebal 700, 14.5px)
        self.lbl_curr = QLabel("Menunggu lagu...")
        self.lbl_curr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_curr.setStyleSheet(f"""
            color: #FFFFFF;
            background: transparent;
            border: none;
            font-family: {FONT_FAMILY};
            font-weight: 700;
            line-height: 1.2;
        """)
        self.lbl_curr.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_curr.setWordWrap(True)

        # Baris 3: Lirik Berikutnya
        self.lbl_next = QLabel("")
        self.lbl_next.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.lbl_next.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.50);
            background: transparent;
            border: none;
            font-family: {FONT_FAMILY};
        """)
        self.lbl_next.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_next.setWordWrap(True)

        layout.addWidget(self.lbl_prev)
        layout.addWidget(self.lbl_curr)
        layout.addWidget(self.lbl_next)

    def set_lyrics(self, lyrics: list, status: str = ""):
        self.lyrics_list = lyrics
        self.status_msg = status
        self.current_idx = -1
        if not lyrics:
            self.lbl_prev.setText("")
            self.lbl_curr.setText(status if status else "Lirik belum tersedia")
            self.lbl_curr.setStyleSheet(f"color: rgba(255, 255, 255, 0.55); background: transparent; border: none; font-family: {FONT_FAMILY};")
            self.lbl_next.setText("")
        else:
            self.lbl_curr.setStyleSheet(f"color: #FFFFFF; background: transparent; border: none; font-family: {FONT_FAMILY}; font-weight: 700;")

    def sync_time(self, elapsed_sec: float) -> str:
        """Menyinkronkan posisi lirik dengan detik lagu saat ini."""
        if not self.lyrics_list:
            return ""

        idx = -1
        for i, (timestamp, text) in enumerate(self.lyrics_list):
            if elapsed_sec >= timestamp:
                idx = i
            else:
                break

        if idx != self.current_idx:
            self.current_idx = idx
            if idx == -1:
                self.lbl_prev.setText("")
                self.lbl_curr.setText("Instrumental Intro")
                self.lbl_curr.setStyleSheet(f"color: rgba(255, 255, 255, 0.45); background: transparent; border: none; font-family: {FONT_FAMILY};")
                self.lbl_next.setText(self.lyrics_list[0][1] if self.lyrics_list else "")
                return "Intro"
            else:
                prev_text = self.lyrics_list[idx - 1][1] if idx > 0 else ""
                curr_text = self.lyrics_list[idx][1]
                next_text = (
                    self.lyrics_list[idx + 1][1]
                    if idx + 1 < len(self.lyrics_list)
                    else ""
                )

                self.lbl_prev.setText(prev_text)
                self.lbl_curr.setText(curr_text)
                self.lbl_curr.setStyleSheet(f"color: #FFFFFF; background: transparent; border: none; font-family: {FONT_FAMILY}; font-weight: 700;")
                self.lbl_next.setText(next_text)
                return curr_text

        if idx >= 0 and idx < len(self.lyrics_list):
            return self.lyrics_list[idx][1]
        return ""
