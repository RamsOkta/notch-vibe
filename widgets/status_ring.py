import ctypes
from ctypes import wintypes
from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor
from PyQt6.QtWidgets import QWidget


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def get_system_battery_info():
    """Mengambil status baterai perangkat Windows melalui Win32 API."""
    sps = SYSTEM_POWER_STATUS()
    try:
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
            percent = int(sps.BatteryLifePercent)
            is_charging = sps.ACLineStatus == 1
            has_battery = percent <= 100
            return (percent if has_battery else 100), is_charging, has_battery
    except Exception:
        pass
    return 100, False, False


class StatusRingWidget(QWidget):
    """
    Diagram lingkaran baterai perangkat (Real-time Battery Ring):
    - Merefleksikan % sisa baterai perangkat secara akurat
    - Berubah warna: Hijau (>20%), Oranye/Merah (<=20%), Kilat saat di-charge
    - Tooltip & sinyal persentase baterai real-time
    """
    battery_changed = pyqtSignal(int, bool)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.percent = 100
        self.is_charging = False
        self.has_battery = True

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_battery)
        self._timer.start(3000)  # Cek baterai tiap 3 detik
        self.refresh_battery()

    def refresh_battery(self):
        p, chg, has_b = get_system_battery_info()
        changed = (p != self.percent) or (chg != self.is_charging)
        self.percent = p
        self.is_charging = chg
        self.has_battery = has_b

        status_text = "Mengisi Daya" if self.is_charging else "Baterai"
        self.setToolTip(f"{status_text}: {self.percent}%")

        if changed:
            self.battery_changed.emit(self.percent, self.is_charging)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(2.0, 2.0, 12.0, 12.0)

        # Penentuan Warna Berdasarkan Kapasitas & Status Pengisian
        if self.is_charging:
            ring_color = QColor(52, 211, 153)  # Emerald charging
            bg_color = QColor(52, 211, 153, 50)
        elif self.percent <= 20:
            ring_color = QColor(248, 113, 113)  # Merah peringatan
            bg_color = QColor(248, 113, 113, 50)
        elif self.percent <= 40:
            ring_color = QColor(251, 191, 36)   # Amber
            bg_color = QColor(251, 191, 36, 50)
        else:
            ring_color = QColor(51, 224, 122)   # Hijau normal Nusa
            bg_color = QColor(51, 224, 122, 50)

        # 1. Lingkaran Dasar (Background Track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(bg_color, 1.8))
        painter.drawEllipse(rect)

        # 2. Busur Tingkat Persentase Baterai (0 s/d 360 derajat)
        span_angle = int((self.percent / 100.0) * 360.0 * 16)
        active_pen = QPen(ring_color, 2.0)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(active_pen)
        # Mulai dari atas (90 derajat) berputar searah jarum jam
        painter.drawArc(rect, 90 * 16, -span_angle)

        # 3. Titik atau Indikator Petir Mini jika sedang mengisi daya
        if self.is_charging:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawEllipse(QRectF(6.5, 6.5, 3.0, 3.0))
