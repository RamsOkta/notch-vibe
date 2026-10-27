from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QPen, QCursor
from PyQt6.QtWidgets import QWidget


class MediaIconButton(QWidget):
    """
    Tombol ikon media vektor presisi tinggi khas Nusa (https://rama2555.github.io/nusa/):
    - Digambar langsung dengan QPainter (bebas dependensi font/emoji)
    - Jenis ikon: 'prev', 'play', 'pause', 'next', 'lyrics_bubble', 'arrow_right'
    - Efek hover & press yang responsif dan elegan
    """
    clicked = pyqtSignal()

    def __init__(self, icon_type: str, size: int = 24, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.is_hovered = False
        self.is_pressed = False
        self.is_active = False  # Untuk toggle seperti tombol lirik

    def set_active(self, active: bool):
        if self.is_active != active:
            self.is_active = active
            self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.is_pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_pressed:
                self.is_pressed = False
                self.update()
                self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        # Warna icon dinamis: idle = 0.85, hover = 1.0, pressed = 0.6
        if self.is_pressed:
            fill_color = QColor(255, 255, 255, 160)
        elif self.is_hovered or self.is_active:
            fill_color = QColor(255, 255, 255, 255)
        else:
            fill_color = QColor(255, 255, 255, 215)

        painter.setBrush(fill_color)
        painter.setPen(Qt.PenStyle.NoPen)

        if self.icon_type == "prev":
            # Ganda segitiga ke kiri ◀◀
            s = 6.0
            # Segitiga kiri
            p1 = QPainterPath()
            p1.moveTo(cx - 1.0, cy)
            p1.lineTo(cx + s - 1.0, cy - s)
            p1.lineTo(cx + s - 1.0, cy + s)
            p1.closeSubpath()
            painter.fillPath(p1, fill_color)

            # Segitiga kanan
            p2 = QPainterPath()
            p2.moveTo(cx - s - 1.0, cy)
            p2.lineTo(cx - 1.0, cy - s)
            p2.lineTo(cx - 1.0, cy + s)
            p2.closeSubpath()
            painter.fillPath(p2, fill_color)

        elif self.icon_type == "next":
            # Ganda segitiga ke kanan ▶▶
            s = 6.0
            p1 = QPainterPath()
            p1.moveTo(cx + 1.0, cy)
            p1.lineTo(cx - s + 1.0, cy - s)
            p1.lineTo(cx - s + 1.0, cy + s)
            p1.closeSubpath()
            painter.fillPath(p1, fill_color)

            p2 = QPainterPath()
            p2.moveTo(cx + s + 1.0, cy)
            p2.lineTo(cx + 1.0, cy - s)
            p2.lineTo(cx + 1.0, cy + s)
            p2.closeSubpath()
            painter.fillPath(p2, fill_color)

        elif self.icon_type == "pause":
            # Dua batang vertikal ❚❚
            bar_w = 3.6
            bar_h = 13.0
            gap = 4.2
            r = 1.5
            x1 = cx - gap / 2.0 - bar_w
            x2 = cx + gap / 2.0
            y = cy - bar_h / 2.0
            painter.drawRoundedRect(QRectF(x1, y, bar_w, bar_h), r, r)
            painter.drawRoundedRect(QRectF(x2, y, bar_w, bar_h), r, r)

        elif self.icon_type == "play":
            # Segitiga Play ▶
            s = 7.0
            p = QPainterPath()
            p.moveTo(cx - s + 2.0, cy - s)
            p.lineTo(cx + s + 1.0, cy)
            p.lineTo(cx - s + 2.0, cy + s)
            p.closeSubpath()
            painter.fillPath(p, fill_color)

        elif self.icon_type == "lyrics_bubble":
            # Balon percakapan dengan titik-titik di dalamnya 💬
            bw = 18.0
            bh = 14.0
            bx = cx - bw / 2.0
            by = cy - bh / 2.0 - 1.0
            r = 3.5

            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, by, bw, bh), r, r)
            # Ekor balon kecil di kiri bawah
            tail = QPainterPath()
            tail.moveTo(bx + 4.0, by + bh)
            tail.lineTo(bx + 2.0, by + bh + 3.0)
            tail.lineTo(bx + 7.5, by + bh)
            tail.closeSubpath()
            bubble = path.united(tail)

            if self.is_active:
                painter.fillPath(bubble, fill_color)
                # Titik di dalam balon warna gelap saat aktif
                painter.setBrush(QColor(0, 0, 0, 220))
                painter.drawEllipse(QPointF(cx - 3.5, cy - 1.0), 1.2, 1.2)
                painter.drawEllipse(QPointF(cx + 3.5, cy - 1.0), 1.2, 1.2)
            else:
                # Balon outline
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pen = QPen(fill_color, 1.4)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(bubble)

                # Titik di dalam balon
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill_color)
                painter.drawEllipse(QPointF(cx - 3.5, cy - 1.0), 1.2, 1.2)
                painter.drawEllipse(QPointF(cx + 3.5, cy - 1.0), 1.2, 1.2)

        elif self.icon_type == "arrow_right":
            # Tombol lingkaran dengan panah >
            radius = min(w, h) / 2.0 - 1.0
            circle_color = QColor(255, 255, 255, 70 if self.is_hovered else 45)
            painter.setBrush(circle_color)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

            # Chevron panah >
            pen = QPen(QColor(255, 255, 255), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            path = QPainterPath()
            path.moveTo(cx - 2.0, cy - 4.5)
            path.lineTo(cx + 2.5, cy)
            path.lineTo(cx - 2.0, cy + 4.5)
            painter.drawPath(path)

        elif self.icon_type == "pin":
            # Apple-style pin icon (Toggle stay-open / pin)
            if self.is_active:
                pin_color = QColor(255, 255, 255, 255)
            else:
                pin_color = QColor(255, 255, 255, 140 if self.is_hovered else 80)

            pen = QPen(pin_color, 1.3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(pin_color if self.is_active else Qt.BrushStyle.NoBrush)

            pin_path = QPainterPath()
            # Top cap
            pin_path.moveTo(cx - 3.5, cy - 5.0)
            pin_path.lineTo(cx + 3.5, cy - 5.0)
            # Tapered body
            pin_path.lineTo(cx + 2.0, cy - 1.0)
            pin_path.lineTo(cx + 4.0, cy + 1.0)
            pin_path.lineTo(cx - 4.0, cy + 1.0)
            pin_path.lineTo(cx - 2.0, cy - 1.0)
            pin_path.closeSubpath()
            painter.drawPath(pin_path)

            # Pin needle
            painter.drawLine(QPointF(cx, cy + 1.0), QPointF(cx, cy + 6.0))

