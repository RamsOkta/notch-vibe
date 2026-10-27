from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QRadialGradient, QLinearGradient, QColor, QPen,
    QPixmap, QPainterPath
)
from PyQt6.QtWidgets import QWidget


class AppleAlbumArtWidget(QWidget):
    """
    Cover Art Squircle minimalis khas Nusa (https://rama2555.github.io/nusa/):
    - Squircle dengan corner radius 10px
    - Border kaca lembut 1px (rgba(255, 255, 255, 0.14))
    - Dukungan gambar resolusi tinggi dari iTunes / cover lokal
    - Fallback artistik abstrak geometris khas Nusa saat tanpa koneksi
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(58, 58)
        self.pixmap = None
        self.title_seed = "Paper Sky"

    def set_playing(self, playing: bool):
        pass

    def set_artwork(self, img_bytes: bytes, title: str = ""):
        if title:
            self.title_seed = title
        if img_bytes:
            pix = QPixmap()
            if pix.loadFromData(img_bytes):
                self.pixmap = pix.scaled(
                    self.width(), self.height(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
            else:
                self.pixmap = None
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = float(self.width())
        h = float(self.height())
        corner_r = 10.0
        rect = QRectF(0.0, 0.0, w, h)

        path = QPainterPath()
        path.addRoundedRect(rect, corner_r, corner_r)

        painter.save()
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            painter.drawPixmap(0, 0, int(w), int(h), self.pixmap)
        else:
            # Fallback: Motif Abstrak Biru Langit khas Nusa (Paper Sky / Summer Flows)
            h_val = sum(ord(c) for c in self.title_seed) % 360
            grad = QLinearGradient(0.0, 0.0, w, h)
            grad.setColorAt(0.0, QColor(220, 235, 255))
            grad.setColorAt(1.0, QColor(175, 205, 250))
            painter.fillRect(rect, grad)

            # Pola garis horizontal tipis khas sampul Nusa
            painter.setPen(QPen(QColor(46, 127, 224, 38), 1.0))
            for y_line in range(4, int(h), 5):
                painter.drawLine(0, y_line, int(w), y_line)

            # Lingkaran konsentris biru
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(46, 127, 224, 210))
            painter.drawEllipse(QPointF(w * 0.38, h * 0.55), 14.0, 14.0)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(90, 166, 242), 2.2))
            painter.drawEllipse(QPointF(w * 0.38, h * 0.55), 18.0, 18.0)

            # Garis diagonal tipis
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.6))
            painter.drawLine(int(w * 0.20), int(h * 0.85), int(w * 0.58), int(h * 0.15))

        # Efek kilau cahaya diagonal lembut (soft sheen)
        sheen = QLinearGradient(0.0, 0.0, w * 0.6, h * 0.6)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 45))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, sheen)

        painter.restore()

        # Border tipis squircle
        painter.setPen(QPen(QColor(255, 255, 255, 32), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
