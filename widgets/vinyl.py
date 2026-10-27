from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QRadialGradient, QLinearGradient, QColor, QPen
from PyQt6.QtWidgets import QWidget


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
