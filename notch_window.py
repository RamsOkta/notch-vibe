import time
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, QRectF, QPointF, QEasingCurve,
    pyqtProperty, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QFont, QAction, QCursor,
    QLinearGradient, QRadialGradient, QPen, QBrush, QRegion, QFontMetrics
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMenu, QGraphicsOpacityEffect, QFrame, QStackedWidget
)

from config import (
    COMPACT_W, COMPACT_H,
    MUSIC_W, MUSIC_H,
    LYRICS_W, LYRICS_H,
    CANVAS_W, CANVAS_H,
    EAR_RADIUS,
    FONT_FAMILY,
)
from widgets import (
    AppleWaveform,
    AppleAlbumArtWidget,
    SmoothProgressBar,
    AppleLyricsWidget,
    MediaIconButton,
    StatusRingWidget,
)
from media import MediaWorker


class LivingNotch(QWidget):
    """
    Nusa: Living Notch untuk Windows (Sesuai Gambar 1 & 2):
    - Mode 1: Music Dashboard (Gambar 1, 430x142) dengan Cover Art, Scrubber & Ikon Kontrol Minimalis
    - Mode 2: Side-by-Side Lyrics (Gambar 2, 570x154) dengan Lirik Anti-Terpotong
    - Mode 3: Compact Notch saat idle (250x32)
    - Diagram Baterai Perangkat Real-time + Teks % Baterai
    - Ikon Kontrol Vektor Elegan (Speech Bubble, Prev, Play/Pause, Next, Arrow)
    - Background Hitam Pekat Murni (#000000) & Tipografi Putih Bersih
    """

    COMPACT_W, COMPACT_H = COMPACT_W, COMPACT_H
    MUSIC_W, MUSIC_H = MUSIC_W, MUSIC_H
    LYRICS_W, LYRICS_H = LYRICS_W, LYRICS_H
    CANVAS_W, CANVAS_H = CANVAS_W, CANVAS_H
    EAR_RADIUS = EAR_RADIUS

    def __init__(self):
        super().__init__()
        self.is_expanded = False
        self.active_mode = "music"  # 'music' (Gambar 1) atau 'lyrics' (Gambar 2)
        self.last_position = 0.0
        self.track_duration = 210.0
        self.is_playing = False
        self.current_title = "Paper Sky"
        self.current_artist = "Lumen Coast - Summer Flows"
        self.battery_pct = 100

        self._notch_w = COMPACT_W
        self._notch_h = COMPACT_H
        self._morph_progress = 0.0

        # Konfigurasi Window Transparan, Frameless, Always on Top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Kunci posisi di tengah atas layar monitor utama
        screen_x, screen_w = self._get_screen_geometry()
        win_x = screen_x + (screen_w - CANVAS_W) // 2
        self.setGeometry(win_x, 0, CANVAS_W, CANVAS_H)

        self._init_ui()
        self._init_animations()
        self._init_timers()
        self._update_mask_and_layout()

        # Inisialisasi Background Media Worker
        self.worker = MediaWorker()
        self.worker.media_updated.connect(self._on_media_updated)
        self.worker.lyrics_updated.connect(self._on_lyrics_updated)
        self.worker.artwork_updated.connect(self._on_artwork_updated)
        self.worker.start_worker()

        QApplication.instance().aboutToQuit.connect(self.worker.stop_worker)

    @pyqtProperty(float)
    def notchWidth(self) -> float:
        return self._notch_w

    @notchWidth.setter
    def notchWidth(self, val: float):
        self._notch_w = val
        self._update_mask_and_layout()
        self.update()

    @pyqtProperty(float)
    def notchHeight(self) -> float:
        return self._notch_h

    @notchHeight.setter
    def notchHeight(self, val: float):
        self._notch_h = val
        self._update_mask_and_layout()
        self.update()

    @pyqtProperty(float)
    def morphProgress(self) -> float:
        return self._morph_progress

    @morphProgress.setter
    def morphProgress(self, val: float):
        self._morph_progress = val
        self.update()

    def _get_screen_geometry(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            return geom.x(), geom.width()
        return 0, 1920

    def _get_pill_rect(self) -> QRectF:
        x = (CANVAS_W - self._notch_w) / 2.0
        return QRectF(x, 0.0, self._notch_w, self._notch_h)

    def _update_mask_and_layout(self):
        rect = self._get_pill_rect()
        ear = EAR_RADIUS

        inner_x = int(rect.x() + ear + 6)
        inner_w = int(rect.width() - (ear + 6) * 2)
        inner_h = int(rect.height() - 4)
        self.inner_container.setGeometry(inner_x, 3, max(100, inner_w), max(24, inner_h))

        mask_rect = QRect(
            int(rect.x()),
            0,
            int(rect.width()),
            int(rect.height() + 4),
        )
        self.setMask(QRegion(mask_rect))

    def _init_ui(self):
        self.inner_container = QWidget(self)
        self.inner_container.setMouseTracking(True)

        self.root_layout = QVBoxLayout(self.inner_container)
        self.root_layout.setContentsMargins(6, 3, 6, 4)
        self.root_layout.setSpacing(4)

        # =====================================================================
        # 1. HEADER ATAS (Ring Baterai • % Baterai • Tanggal & Jam • Waveform)
        # =====================================================================
        self.header_bar = QHBoxLayout()
        self.header_bar.setContentsMargins(2, 0, 2, 0)
        self.header_bar.setSpacing(6)

        # Diagram Lingkaran Baterai
        self.status_ring = StatusRingWidget(self)
        self.status_ring.battery_changed.connect(self._on_battery_changed)
        self.header_bar.addWidget(self.status_ring)

        # Label Angka Persentase Baterai Real-time
        self.battery_label = QLabel(f"{self.status_ring.percent}%")
        self.battery_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.battery_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.65);
            font-family: {FONT_FAMILY};
            padding-right: 4px;
        """)
        self.header_bar.addWidget(self.battery_label)

        # Tanggal & Jam
        self.header_date_time = QLabel("Mon 26 Oct 2026  <b>14:09</b>")
        self.header_date_time.setFont(QFont("Segoe UI", 9))
        self.header_date_time.setStyleSheet(f"""
            color: #FFFFFF;
            font-family: {FONT_FAMILY};
        """)
        self.header_bar.addWidget(self.header_date_time)
        self.header_bar.addStretch()

        self.waveform = AppleWaveform(self)
        self.header_bar.addWidget(self.waveform)

        self.root_layout.addLayout(self.header_bar)

        # =====================================================================
        # 2. CONTAINER STACK (Mode 1: Music View vs Mode 2: Lyrics View)
        # =====================================================================
        self.stack_container = QStackedWidget(self)

        self.expanded_opacity = QGraphicsOpacityEffect(self.stack_container)
        self.expanded_opacity.setOpacity(0.0)
        self.stack_container.setGraphicsEffect(self.expanded_opacity)

        # --- A. MODE 1: MUSIC VIEW (Gambar 1) ---
        self.music_page = QWidget()
        music_layout = QVBoxLayout(self.music_page)
        music_layout.setContentsMargins(4, 2, 4, 2)
        music_layout.setSpacing(6)

        # Baris Info Lagu (Cover Art + Title/Artist + Tombol Arrow Right)
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.m1_art = AppleAlbumArtWidget(self)
        top_row.addWidget(self.m1_art)

        m1_col = QVBoxLayout()
        m1_col.setSpacing(1)
        m1_col.setContentsMargins(0, 4, 0, 4)

        self.m1_title = QLabel("Paper Sky")
        self.m1_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.m1_title.setStyleSheet(f"""
            color: #FFFFFF;
            font-family: {FONT_FAMILY};
            font-weight: 700;
        """)

        self.m1_artist = QLabel("Lumen Coast - Summer Flows")
        self.m1_artist.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        self.m1_artist.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.50);
            font-family: {FONT_FAMILY};
        """)

        m1_col.addWidget(self.m1_title)
        m1_col.addWidget(self.m1_artist)
        top_row.addLayout(m1_col, stretch=1)

        # Tombol panah kanan > untuk beralih ke Mode Lirik
        self.btn_goto_lyrics = MediaIconButton("arrow_right", size=24, parent=self)
        self.btn_goto_lyrics.clicked.connect(self._toggle_mode)
        top_row.addWidget(self.btn_goto_lyrics)

        music_layout.addLayout(top_row)

        # Baris Scrubber Timeline: 03:13 ━━━━━━─── -01:03
        scrub_row = QHBoxLayout()
        scrub_row.setContentsMargins(2, 0, 2, 0)
        scrub_row.setSpacing(8)

        self.m1_elapsed = QLabel("03:13")
        self.m1_elapsed.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.m1_elapsed.setStyleSheet(f"color: rgba(255, 255, 255, 0.65); font-family: {FONT_FAMILY}; min-width: 32px;")

        self.m1_prog = SmoothProgressBar(self)

        self.m1_remaining = QLabel("-01:03")
        self.m1_remaining.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        self.m1_remaining.setStyleSheet(f"color: rgba(255, 255, 255, 0.65); font-family: {FONT_FAMILY}; min-width: 36px; text-align: right;")

        scrub_row.addWidget(self.m1_elapsed)
        scrub_row.addWidget(self.m1_prog, stretch=1)
        scrub_row.addWidget(self.m1_remaining)
        music_layout.addLayout(scrub_row)

        # Baris Tombol Kontrol Bawah: [💬] di kiri, [◀◀ ❚❚ ▶▶] di tengah
        ctl_row = QHBoxLayout()
        ctl_row.setContentsMargins(4, 0, 4, 0)
        ctl_row.setSpacing(14)

        self.m1_btn_lyrics = MediaIconButton("lyrics_bubble", size=20, parent=self)
        self.m1_btn_lyrics.clicked.connect(self._toggle_mode)
        ctl_row.addWidget(self.m1_btn_lyrics)
        ctl_row.addStretch()

        self.m1_btn_prev = MediaIconButton("prev", size=22, parent=self)
        self.m1_btn_prev.clicked.connect(lambda: self.worker.send_command("prev"))

        self.m1_btn_play = MediaIconButton("pause", size=24, parent=self)
        self.m1_btn_play.clicked.connect(lambda: self.worker.send_command("play_pause"))

        self.m1_btn_next = MediaIconButton("next", size=22, parent=self)
        self.m1_btn_next.clicked.connect(lambda: self.worker.send_command("next"))

        ctl_row.addWidget(self.m1_btn_prev)
        ctl_row.addWidget(self.m1_btn_play)
        ctl_row.addWidget(self.m1_btn_next)
        ctl_row.addStretch()

        spacer = QWidget()
        spacer.setFixedSize(20, 20)
        ctl_row.addWidget(spacer)

        music_layout.addLayout(ctl_row)
        self.stack_container.addWidget(self.music_page)

        # --- B. MODE 2: SIDE-BY-SIDE LYRICS VIEW (Gambar 2) ---
        self.lyrics_page = QWidget()
        lyr_page_layout = QHBoxLayout(self.lyrics_page)
        lyr_page_layout.setContentsMargins(2, 0, 2, 0)
        lyr_page_layout.setSpacing(10)

        # Kolom Kiri: Player Kompak (Lebar Tetap 205px agar Lirik Mendapat Ruang Lega)
        left_player = QWidget()
        left_player.setFixedWidth(205)
        lp_layout = QVBoxLayout(left_player)
        lp_layout.setContentsMargins(0, 0, 0, 0)
        lp_layout.setSpacing(5)

        lp_top = QHBoxLayout()
        lp_top.setSpacing(8)

        self.m2_art = AppleAlbumArtWidget(self)
        self.m2_art.setFixedSize(46, 46)
        lp_top.addWidget(self.m2_art)

        lp_col = QVBoxLayout()
        lp_col.setSpacing(1)
        lp_col.setContentsMargins(0, 2, 0, 2)

        self.m2_title = QLabel("Paper Sky")
        self.m2_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.m2_title.setStyleSheet(f"color: #FFFFFF; font-family: {FONT_FAMILY}; font-weight: 700;")

        self.m2_artist = QLabel("Lumen Coast - Summ...")
        self.m2_artist.setFont(QFont("Segoe UI", 8))
        self.m2_artist.setStyleSheet(f"color: rgba(255, 255, 255, 0.50); font-family: {FONT_FAMILY};")

        lp_col.addWidget(self.m2_title)
        lp_col.addWidget(self.m2_artist)
        lp_top.addLayout(lp_col, stretch=1)
        lp_layout.addLayout(lp_top)

        # Scrubber Baris Kiri
        lp_scrub = QHBoxLayout()
        lp_scrub.setSpacing(6)

        self.m2_elapsed = QLabel("02:59")
        self.m2_elapsed.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
        self.m2_elapsed.setStyleSheet(f"color: rgba(255, 255, 255, 0.65); font-family: {FONT_FAMILY}; min-width: 28px;")

        self.m2_prog = SmoothProgressBar(self)

        self.m2_remaining = QLabel("-01:17")
        self.m2_remaining.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
        self.m2_remaining.setStyleSheet(f"color: rgba(255, 255, 255, 0.65); font-family: {FONT_FAMILY}; min-width: 32px; text-align: right;")

        lp_scrub.addWidget(self.m2_elapsed)
        lp_scrub.addWidget(self.m2_prog, stretch=1)
        lp_scrub.addWidget(self.m2_remaining)
        lp_layout.addLayout(lp_scrub)

        # Tombol Kontrol Kiri: [💬 (Active)] [◀◀] [❚❚] [▶▶]
        lp_ctl = QHBoxLayout()
        lp_ctl.setSpacing(10)

        self.m2_btn_lyrics = MediaIconButton("lyrics_bubble", size=18, parent=self)
        self.m2_btn_lyrics.set_active(True)
        self.m2_btn_lyrics.clicked.connect(self._toggle_mode)
        lp_ctl.addWidget(self.m2_btn_lyrics)
        lp_ctl.addStretch()

        self.m2_btn_prev = MediaIconButton("prev", size=18, parent=self)
        self.m2_btn_prev.clicked.connect(lambda: self.worker.send_command("prev"))

        self.m2_btn_play = MediaIconButton("pause", size=20, parent=self)
        self.m2_btn_play.clicked.connect(lambda: self.worker.send_command("play_pause"))

        self.m2_btn_next = MediaIconButton("next", size=18, parent=self)
        self.m2_btn_next.clicked.connect(lambda: self.worker.send_command("next"))

        lp_ctl.addWidget(self.m2_btn_prev)
        lp_ctl.addWidget(self.m2_btn_play)
        lp_ctl.addWidget(self.m2_btn_next)
        lp_ctl.addStretch()

        lp_layout.addLayout(lp_ctl)
        lyr_page_layout.addWidget(left_player)

        # Garis Pembatas Vertikal Tipis 1px
        v_divider = QFrame()
        v_divider.setFixedWidth(1)
        v_divider.setFixedHeight(100)
        v_divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.12); border: none;")
        lyr_page_layout.addWidget(v_divider)

        # Kolom Kanan: Tampilan Lirik Karaoke (Mendapat sisa ruang luas ~340px agar teks tidak terpotong)
        self.lyrics_widget = AppleLyricsWidget(self)
        lyr_page_layout.addWidget(self.lyrics_widget, stretch=1)

        self.stack_container.addWidget(self.lyrics_page)

        self.stack_container.hide()
        self.root_layout.addWidget(self.stack_container)

    def _on_battery_changed(self, percent: int, is_charging: bool):
        self.battery_pct = percent
        charging_icon = "⚡" if is_charging else ""
        self.battery_label.setText(f"{charging_icon}{percent}%")

    def _toggle_mode(self):
        """Beralih secara mulus antara Mode Musik (Gambar 1) dan Mode Lirik (Gambar 2)."""
        if self.active_mode == "music":
            self.active_mode = "lyrics"
            self.stack_container.setCurrentWidget(self.lyrics_page)
            target_w = LYRICS_W
            target_h = LYRICS_H
        else:
            self.active_mode = "music"
            self.stack_container.setCurrentWidget(self.music_page)
            target_w = MUSIC_W
            target_h = MUSIC_H

        if self.is_expanded:
            self._animate_size(target_w, target_h, 280)

    def _init_animations(self):
        """Animasi kurva pegas (Spring Physics) khas Nusa."""
        self.anim_w = QPropertyAnimation(self, b"notchWidth")
        self.anim_h = QPropertyAnimation(self, b"notchHeight")
        self.anim_morph = QPropertyAnimation(self, b"morphProgress")
        self.anim_opacity = QPropertyAnimation(self.expanded_opacity, b"opacity")

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.anim_w)
        self.anim_group.addAnimation(self.anim_h)
        self.anim_group.addAnimation(self.anim_morph)
        self.anim_group.addAnimation(self.anim_opacity)
        self.anim_group.finished.connect(self._on_animation_finished)

    def _animate_size(self, target_w: float, target_h: float, duration: int = 300):
        self.anim_group.stop()
        spring_curve = QEasingCurve(QEasingCurve.Type.OutBack)
        spring_curve.setOvershoot(0.65)

        self.anim_w.setDuration(duration)
        self.anim_w.setEasingCurve(spring_curve)
        self.anim_w.setStartValue(self._notch_w)
        self.anim_w.setEndValue(target_w)

        self.anim_h.setDuration(int(duration * 0.9))
        self.anim_h.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.anim_h.setStartValue(self._notch_h)
        self.anim_h.setEndValue(target_h)

        self.anim_morph.setDuration(int(duration * 0.9))
        self.anim_morph.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim_morph.setStartValue(self._morph_progress)
        self.anim_morph.setEndValue(1.0 if self.is_expanded else 0.0)

        self.anim_opacity.setDuration(int(duration * 0.75))
        self.anim_opacity.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim_opacity.setStartValue(self.expanded_opacity.opacity())
        self.anim_opacity.setEndValue(1.0 if self.is_expanded else 0.0)

        self.anim_group.start()

    def _init_timers(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(500)
        self._update_clock()

        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._collapse_notch)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = max(0, int(seconds))
        return f"{s // 60:02d}:{s % 60:02d}"

    def _update_clock(self):
        now = datetime.now()
        date_str = now.strftime("%a %d %b %Y")
        time_str = now.strftime("%H:%M")
        if self.is_expanded:
            self.header_date_time.setText(f"{date_str}  <b>{time_str}</b>")
        else:
            self.header_date_time.setText(f"<b>{time_str}</b>")

    def _on_media_updated(self, info: dict):
        self.is_playing = info["is_playing"]
        self.last_position = info["position"]
        self.track_duration = info.get("duration", 210.0)
        self.current_title = info["title"]
        self.current_artist = info["artist"]

        self.waveform.set_playing(self.is_playing)

        # Update tombol Play vs Pause (Vektor)
        play_icon = "pause" if self.is_playing else "play"
        self.m1_btn_play.icon_type = play_icon
        self.m1_btn_play.update()
        self.m2_btn_play.icon_type = play_icon
        self.m2_btn_play.update()

        # Update Scrubber Waktu Lagu
        elapsed = self.last_position
        remaining = max(0.0, self.track_duration - elapsed)
        el_txt = self._fmt_time(elapsed)
        rem_txt = f"-{self._fmt_time(remaining)}"

        self.m1_elapsed.setText(el_txt)
        self.m1_remaining.setText(rem_txt)
        self.m2_elapsed.setText(el_txt)
        self.m2_remaining.setText(rem_txt)

        progress_ratio = elapsed / max(1.0, self.track_duration)
        self.m1_prog.set_progress(progress_ratio)
        self.m2_prog.set_progress(progress_ratio)

        # Sinkronisasi Lirik
        self.lyrics_widget.sync_time(elapsed)

        # Update Teks Judul & Artis (Elided rapi)
        fm1_t = QFontMetrics(self.m1_title.font())
        fm1_a = QFontMetrics(self.m1_artist.font())
        self.m1_title.setText(fm1_t.elidedText(self.current_title, Qt.TextElideMode.ElideRight, 260))
        self.m1_artist.setText(fm1_a.elidedText(self.current_artist, Qt.TextElideMode.ElideRight, 260))

        fm2_t = QFontMetrics(self.m2_title.font())
        fm2_a = QFontMetrics(self.m2_artist.font())
        self.m2_title.setText(fm2_t.elidedText(self.current_title, Qt.TextElideMode.ElideRight, 150))
        self.m2_artist.setText(fm2_a.elidedText(self.current_artist, Qt.TextElideMode.ElideRight, 150))

    def _on_lyrics_updated(self, lyrics_list: list, status: str):
        self.lyrics_widget.set_lyrics(lyrics_list, status)

    def _on_artwork_updated(self, img_bytes: bytes):
        self.m1_art.set_artwork(img_bytes, self.current_title)
        self.m2_art.set_artwork(img_bytes, self.current_title)

    def enterEvent(self, event):
        self.collapse_timer.stop()
        if not self.is_expanded:
            self._expand_notch()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.collapse_timer.start(240)
        super().leaveEvent(event)

    def _expand_notch(self):
        self.is_expanded = True
        self.stack_container.show()
        target_w = LYRICS_W if self.active_mode == "lyrics" else MUSIC_W
        target_h = LYRICS_H if self.active_mode == "lyrics" else MUSIC_H
        self._animate_size(target_w, target_h, 320)
        self._update_clock()

    def _collapse_notch(self):
        if self.is_expanded:
            local_pos = self.mapFromGlobal(QCursor.pos())
            if self._get_pill_rect().contains(QPointF(local_pos)):
                return

            self.is_expanded = False
            self._animate_size(COMPACT_W, COMPACT_H, 260)
            self._update_clock()

    def _on_animation_finished(self):
        if not self.is_expanded:
            self.stack_container.hide()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #0c0e14;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                padding: 6px;
                font-family: {FONT_FAMILY};
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: rgba(255, 255, 255, 0.14);
            }}
        """)

        toggle_view_action = QAction("Ganti Tampilan (Musik / Lirik)", self)
        toggle_view_action.triggered.connect(self._toggle_mode)

        reset_sync_action = QAction("Reset Offset Lirik (0s)", self)
        reset_sync_action.triggered.connect(self.worker.reset_lyric_timer)

        quit_action = QAction("Keluar dari Nusa", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(toggle_view_action)
        menu.addAction(reset_sync_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    @staticmethod
    def _build_mac_notch_path(x: float, w: float, h: float, ear_r: float, corner_r: float) -> QPainterPath:
        """Geometri Autentik Notch Nusa / MacBook Pro."""
        corner_r = min(corner_r, max(4.0, h - ear_r - 2.0))
        path = QPainterPath()
        path.moveTo(x, 0.0)
        path.cubicTo(x + ear_r * 0.45, 0.0, x + ear_r, ear_r * 0.45, x + ear_r, ear_r)
        path.lineTo(x + ear_r, h - corner_r)
        path.cubicTo(
            x + ear_r, h - corner_r * 0.45,
            x + ear_r + corner_r * 0.45, h,
            x + ear_r + corner_r, h
        )
        path.lineTo(x + w - ear_r - corner_r, h)
        path.cubicTo(
            x + w - ear_r - corner_r * 0.45, h,
            x + w - ear_r, h - corner_r * 0.45,
            x + w - ear_r, h - corner_r
        )
        path.lineTo(x + w - ear_r, ear_r)
        path.cubicTo(x + w - ear_r, ear_r * 0.45, x + w - ear_r * 0.45, 0.0, x + w, 0.0)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._get_pill_rect()
        x = rect.x()
        w = rect.width()
        h = rect.height()
        ear_r = EAR_RADIUS
        corner_r = 16.0 + 8.0 * self._morph_progress

        # 1. Bayangan Ambient Drop Shadow (box-shadow: 0 14px 34px -16px rgba(0,0,0,.95))
        for i in range(1, 5):
            spread = float(i * 2.8)
            alpha = int(34 - i * 6)
            if alpha > 0:
                shadow_path = self._build_mac_notch_path(
                    x - spread * 0.4,
                    w + spread * 0.8,
                    h + spread,
                    ear_r,
                    corner_r + spread * 0.5,
                )
                painter.fillPath(shadow_path, QColor(0, 0, 0, alpha))

        # 2. Bodi Notch Hitam Pekat Murni (#000000 - Pure OLED Black khas Nusa)
        main_path = self._build_mac_notch_path(x, w, h, ear_r, corner_r)
        painter.fillPath(main_path, QColor(0, 0, 0, 255))

        # 3. Cahaya Ambient Gradien Khas Nusa (--glow: #19b8ff, #2d5bff, #7b4bff)
        if self.is_playing:
            amb_grad = QLinearGradient(x, 0.0, x + w, 0.0)
            amb_grad.setColorAt(0.0, QColor(25, 184, 255, 12))
            amb_grad.setColorAt(0.5, QColor(45, 91, 255, 16))
            amb_grad.setColorAt(1.0, QColor(123, 75, 255, 14))
            painter.fillPath(main_path, amb_grad)

        # 4. Lubang Kamera & Indikator LED di Bezel Tengah Atas
        cam_cx = x + w / 2.0
        cam_cy = 13.0

        # Lensa Kamera Mini
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 20, 28, 200))
        painter.drawEllipse(QPointF(cam_cx, cam_cy), 3.0, 3.0)

        # Pantulan biru gelap lensa
        painter.setBrush(QColor(30, 58, 138, 160))
        painter.drawEllipse(QPointF(cam_cx, cam_cy), 1.8, 1.8)

        # Titik LED Hijau saat Musik Aktif
        if self.is_playing:
            painter.setBrush(QColor(51, 224, 122, 230))
            painter.drawEllipse(QPointF(cam_cx + 10.0, cam_cy), 1.5, 1.5)

        # 5. Rim Light Kaca Tipis (1px Border Translucent khas Nusa)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rim_grad = QLinearGradient(x, 0.0, x, h)
        rim_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        rim_grad.setColorAt(0.40, QColor(255, 255, 255, 14))
        rim_grad.setColorAt(1.0, QColor(255, 255, 255, 30))
        painter.strokePath(main_path, QPen(QBrush(rim_grad), 1.0))
