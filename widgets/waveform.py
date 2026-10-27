import math
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget


class AppleWaveform(QWidget):
    """
    Visualizer gelombang audio 5-bar minimalis ala Nusa (https://rama2555.github.io/nusa/):
    - Bar putih bersih (#FFFFFF) saat aktif
    - Translucent gray saat jeda
    - Gerakan organik halus 30 FPS
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 14)
        self.is_playing = False
        self.phase = 0.0
        self.heights = [0.25, 0.25, 0.25, 0.25, 0.25]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(35)

    def set_playing(self, playing: bool):
        if self.is_playing != playing:
            self.is_playing = playing
            self.update()

    def _tick(self):
        if self.is_playing:
            self.phase += 0.35
            freqs = [1.2, 1.8, 2.4, 1.5, 2.0]
            offsets = [0.0, 1.1, 2.3, 0.7, 2.9]
            for i in range(5):
                target = 0.25 + 0.72 * abs(math.sin(self.phase * freqs[i] + offsets[i]))
                self.heights[i] += (target - self.heights[i]) * 0.45
        else:
            for i in range(5):
                self.heights[i] += (0.20 - self.heights[i]) * 0.25
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_w = 2.2
        gap = 1.8
        total_w = 5 * bar_w + 4 * gap
        start_x = (self.width() - total_w) / 2.0
        max_h = float(self.height() - 2)

        for i in range(5):
            h = max(2.4, self.heights[i] * max_h)
            x = start_x + i * (bar_w + gap)
            y = (self.height() - h) / 2.0

            if self.is_playing:
                painter.setBrush(QColor(255, 255, 255, 245))  # Putih Bersih khas Nusa
            else:
                painter.setBrush(QColor(255, 255, 255, 80))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, h), 1.1, 1.1)
