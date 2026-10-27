from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget


class SmoothProgressBar(QWidget):
    """
    Scrubber bar durasi lagu minimalis sesuai Gambar 1 & 2 Nusa:
    - Tinggi 3.5px
    - Track background: rgba(255, 255, 255, 0.22)
    - Fill progress: #FFFFFF solid
    - Mendukung klik langsung untuk seek posisi lagu
    """
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress = 0.0  # 0.0 s/d 1.0
        self.is_hovered = False

    def set_progress(self, value: float):
        val = max(0.0, min(1.0, value))
        if abs(val - self.progress) > 0.0008:
            self.progress = val
            self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ratio = max(0.0, min(1.0, event.position().x() / float(self.width())))
            self.progress = ratio
            self.update()
            self.seek_requested.emit(ratio)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = 3.8
        y = (self.height() - h) / 2.0
        radius = 1.9

        # Track Latar Belakang (Translucent White 22%)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 55))
        painter.drawRoundedRect(QRectF(0.0, y, w, h), radius, radius)

        # Fill Kemajuan Lagu (Putih Bersih Solid)
        fill_w = max(h, w * self.progress) if self.progress > 0 else 0.0
        if fill_w > 0:
            painter.setBrush(QColor(255, 255, 255, 250))
            painter.drawRoundedRect(QRectF(0.0, y, fill_w, h), radius, radius)

            # Thumb bulat saat hover
            if self.is_hovered:
                thumb_x = fill_w
                thumb_r = 4.5
                painter.drawEllipse(QRectF(thumb_x - thumb_r, self.height() / 2.0 - thumb_r, thumb_r * 2, thumb_r * 2))
