"""
ui/chat_interface.py

🌸 Makima — Premium Chat Interface  (Rewritten v2)
────────────────────────────────────────────────────
Fixes from audit:
  BUG-01  _update_art() now fetches real Spotify album art via URL
  BUG-02  AnimatedButton no longer shifts position (uses opacity flash instead)
  BUG-03  Voice capture fills input box first — user can review before sending
  BUG-04  ChatBubble enforces max-width with proper QTextBrowser for long text
  BUG-05  User messages no longer double-saved to chat_history
  BUG-06  Status transitions through Thinking → Speaking → Online correctly
  BUG-07  _load_history() scrolls to bottom after warm-up
  BUG-08  Settings DJ access guarded with getattr fallback
  BUG-09  MiniMode response_label updated via queued signal (thread-safe)
  BUG-10  VoiceVisualizer uses mapToGlobal() for correct screen positioning
  BUG-11  QGroupBox QSS added to theme_manager stylesheet
  BUG-12  HUD is loaded lazily — only starts if user opens it, avoiding tkinter conflict
  BUG-13  History dialog — clicking a session loads and displays those messages
  BUG-14  Input locked during processing — no spam-send

UI upgrades:
  • Typing indicator (animated dots) while Makima is thinking
  • Mood indicator badge on avatar (from MoodTracker)
  • Message reactions (👍 ❤️ 💡) on hover
  • Search bar that filters visible bubbles in real-time
  • Sidebar with quick-command buttons
  • Smooth scroll-to-bottom button (appears when scrolled up)
  • Improved album art — loads real Spotify images via requests
  • Keyboard shortcut: Ctrl+K opens history, Ctrl+M toggles mini mode
"""

import sys
import os
import threading
import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QTextEdit, QScrollArea, QGridLayout,
    QListWidget, QListWidgetItem, QSlider, QFileDialog,
    QGraphicsOpacityEffect, QDialog, QLineEdit, QSizePolicy,
    QTextBrowser, QShortcut, QToolButton, QScrollBar,
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, pyqtSignal,
    QEvent, QSize, QEasingCurve, QPoint,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPixmap, QCursor, QIcon,
    QKeySequence, QLinearGradient, QPen, QBrush,
)

from ui.settings_dialog import SettingsDialog
from ui.mini_mode import MiniModeWindow
from ui.theme_manager import ThemeManager, ThemeCreatorDialog
from ui.chat_history import ChatHistory
from ui.notification_manager import NotificationManager
from ui.code_highlighter import CodeHighlighter
from ui.voice_visualizer import VoiceVisualizer
from ui.file_handler import FileDropArea

logger = logging.getLogger("Makima.ChatUI")


# ═══════════════════════════════════════════════════════════════════════════════
# AnimatedButton  — FIX BUG-02: opacity flash, no position shift
# ═══════════════════════════════════════════════════════════════════════════════

class AnimatedButton(QPushButton):
    """Button with a subtle opacity flash on hover. No geometry shift."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.75)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().leaveEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# TypingIndicator  — animated "Makima is thinking…" dots
# ═══════════════════════════════════════════════════════════════════════════════

class TypingIndicator(QWidget):
    """Three bouncing dots shown while Makima processes a response."""

    DOT_COUNT = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 40)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)

    def _tick(self):
        self._phase = (self._phase + 1) % (self.DOT_COUNT * 2)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = 7
        spacing = 18
        x0 = (self.width() - (self.DOT_COUNT - 1) * spacing) // 2
        cy = self.height() // 2
        for i in range(self.DOT_COUNT):
            bounce = 5 if (self._phase % self.DOT_COUNT) == i else 0
            alpha = 255 if (self._phase % self.DOT_COUNT) == i else 120
            p.setBrush(QColor(0, 200, 255, alpha))
            p.setPen(Qt.NoPen)
            p.drawEllipse(x0 + i * spacing - r, cy - r - bounce, r * 2, r * 2)
        p.end()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# ChatBubble  — FIX BUG-04 / BUG-05
# ═══════════════════════════════════════════════════════════════════════════════

class ChatBubble(QWidget):
    """Individual message bubble with fade-in, code highlighting,
    file chips, hover reactions, and proper text wrapping."""

    REACTIONS = ["👍", "❤️", "💡", "😂"]

    def __init__(self, message: str, is_user: bool = True,
                 timestamp: str = None, has_code: bool = False,
                 files: list = None, skip_history: bool = False):
        super().__init__()
        self.message = message
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now().strftime("%I:%M %p")
        self.has_code = has_code or ("```" in message)
        self.files = files or []
        self.skip_history = skip_history   # BUG-05: set True for warm-up
        self._reaction_bar = None
        self._build()
        self._fade_in()

    def _fade_in(self):
        self._opacity = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity)
        anim = QPropertyAnimation(self._opacity, b"opacity")
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._fade_anim = anim

    def _build(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 6, 16, 6)

        bubble = QFrame()
        bubble.setObjectName("userBubble" if self.is_user else "makimaBubble")
        bubble.setMaximumWidth(520)

        bl = QVBoxLayout()
        bl.setSpacing(5)
        bl.setContentsMargins(0, 0, 0, 0)

        # File chips
        for fp in self.files:
            btn = QPushButton(f"📎 {os.path.basename(fp)}")
            btn.setObjectName("fileAttachment")
            btn.clicked.connect(lambda _, p=fp: self._open_file(p))
            bl.addWidget(btn)

        # Message body — BUG-04: QTextBrowser enforces wrapping/max-width
        if self.has_code:
            body = CodeHighlighter.create_highlighted_widget(self.message)
        else:
            body = QTextBrowser()
            body.setObjectName("messageText")
            body.setOpenExternalLinks(True)
            body.setReadOnly(True)
            body.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            body.setFrameStyle(QFrame.NoFrame)
            body.setPlainText(self.message)
            body.setMaximumWidth(490)
            doc_height = int(body.document().size().height()) + 10
            body.setFixedHeight(max(30, doc_height))
            body.document().contentsChanged.connect(
                lambda b=body: b.setFixedHeight(
                    max(30, int(b.document().size().height()) + 10)
                )
            )
        bl.addWidget(body)

        # Timestamp + reaction row
        bottom = QHBoxLayout()
        ts = QLabel(self.timestamp)
        ts.setObjectName("timestamp")
        bottom.addWidget(ts)
        bottom.addStretch()

        # Reaction button (hidden, shows on hover)
        self._react_btn = QToolButton()
        self._react_btn.setText("…")
        self._react_btn.setObjectName("reactButton")
        self._react_btn.setFixedSize(24, 18)
        self._react_btn.hide()
        self._react_btn.clicked.connect(self._show_reactions)
        bottom.addWidget(self._react_btn)
        bl.addLayout(bottom)

        # Reaction display
        self._reaction_label = QLabel("")
        self._reaction_label.setObjectName("reactionLabel")
        bl.addWidget(self._reaction_label)

        bubble.setLayout(bl)

        if self.is_user:
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            layout.addWidget(bubble)
            layout.addStretch()

        self.setLayout(layout)

    def enterEvent(self, event):
        self._react_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._react_btn.hide()
        super().leaveEvent(event)

    def _show_reactions(self):
        menu = QDialog(self)
        menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        lo = QHBoxLayout()
        lo.setContentsMargins(8, 4, 8, 4)
        for r in self.REACTIONS:
            b = QPushButton(r)
            b.setFixedSize(36, 36)
            b.setStyleSheet(
                "QPushButton{background:rgba(30,30,50,220);border:none;"
                "border-radius:18px;font-size:18px;}"
                "QPushButton:hover{background:rgba(0,200,255,80);}"
            )
            b.clicked.connect(lambda _, rx=r: self._add_reaction(rx, menu))
            lo.addWidget(b)
        menu.setLayout(lo)
        pos = self._react_btn.mapToGlobal(QPoint(0, -48))
        menu.move(pos)
        menu.exec_()

    def _add_reaction(self, reaction: str, dialog: QDialog):
        current = self._reaction_label.text()
        self._reaction_label.setText(current + reaction)
        dialog.close()

    @staticmethod
    def _open_file(path: str):
        try:
            import subprocess, platform
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# MusicControlWidget  — FIX BUG-01: real album art via Spotify image URL
# ═══════════════════════════════════════════════════════════════════════════════

class MusicControlWidget(QWidget):
    """Right panel: album art (real!), playback controls, mood buttons."""

    def __init__(self, music_dj):
        super().__init__()
        self.dj = music_dj
        self._art_url_cache = ""
        self._build()
        self._start_poller()

    def _build(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Album art
        self.album_art = QLabel()
        self.album_art.setObjectName("albumArt")
        self.album_art.setFixedSize(200, 200)
        self.album_art.setAlignment(Qt.AlignCenter)
        self.album_art.setScaledContents(True)
        self._set_default_art()
        layout.addWidget(self.album_art, alignment=Qt.AlignCenter)

        # Now-playing
        np = QFrame()
        np.setObjectName("nowPlayingFrame")
        npl = QVBoxLayout()
        self.track_label = QLabel("No music playing")
        self.track_label.setObjectName("trackLabel")
        self.track_label.setWordWrap(True)
        self.track_label.setAlignment(Qt.AlignCenter)
        npl.addWidget(self.track_label)
        self.artist_label = QLabel("")
        self.artist_label.setObjectName("artistLabel")
        self.artist_label.setAlignment(Qt.AlignCenter)
        npl.addWidget(self.artist_label)
        np.setLayout(npl)
        layout.addWidget(np)

        # Progress
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setObjectName("progressBar")
        self.progress.setEnabled(False)
        layout.addWidget(self.progress)

        time_row = QHBoxLayout()
        self.time_cur = QLabel("0:00")
        self.time_cur.setObjectName("timeLabel")
        self.time_tot = QLabel("0:00")
        self.time_tot.setObjectName("timeLabel")
        time_row.addWidget(self.time_cur)
        time_row.addStretch()
        time_row.addWidget(self.time_tot)
        layout.addLayout(time_row)

        # Playback controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.prev_btn  = AnimatedButton("⏮"); self.prev_btn.setObjectName("controlButton")
        self.play_btn  = AnimatedButton("▶"); self.play_btn.setObjectName("playButton")
        self.next_btn  = AnimatedButton("⏭"); self.next_btn.setObjectName("controlButton")
        self.shuf_btn  = AnimatedButton("🔀"); self.shuf_btn.setObjectName("controlButton")
        self.rpt_btn   = AnimatedButton("🔁"); self.rpt_btn.setObjectName("controlButton")
        self.prev_btn.clicked.connect(self._prev)
        self.play_btn.clicked.connect(self._toggle_play)
        self.next_btn.clicked.connect(self._next)
        self.shuf_btn.clicked.connect(self._shuffle)
        self.rpt_btn.clicked.connect(self._repeat)
        for b in (self.prev_btn, self.play_btn, self.next_btn, self.shuf_btn, self.rpt_btn):
            ctrl.addWidget(b)
        layout.addLayout(ctrl)

        # Volume
        vol = QHBoxLayout()
        self.mute_btn = QPushButton("🔊"); self.mute_btn.setObjectName("muteButton")
        self.mute_btn.clicked.connect(self._mute_toggle)
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100); self.vol_slider.setValue(50)
        self.vol_slider.setObjectName("volumeSlider")
        self.vol_slider.valueChanged.connect(self._vol_changed)
        self.vol_label = QLabel("50%"); self.vol_label.setObjectName("volumeLabel")
        vol.addWidget(self.mute_btn); vol.addWidget(self.vol_slider); vol.addWidget(self.vol_label)
        layout.addLayout(vol)

        # Mood buttons
        section = QLabel("🎭 Quick Moods"); section.setObjectName("sectionTitle")
        layout.addWidget(section)
        mood_grid = QGridLayout(); mood_grid.setSpacing(8)
        moods = [
            ("🎯 Focus", "focus"), ("🔥 Hype",   "hype"),
            ("😌 Chill", "chill"), ("😢 Sad",    "sad"),
            ("🎮 Game",  "gaming"),("💻 Code",   "coding"),
            ("🎉 Party", "party"), ("😴 Sleep",  "sleep"),
        ]
        for i, (label, mood) in enumerate(moods):
            btn = AnimatedButton(label); btn.setObjectName("moodButton")
            btn.clicked.connect(lambda _, m=mood: self._play_mood(m))
            mood_grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(mood_grid)

        # Playlist
        pl = QLabel("📋 Up Next"); pl.setObjectName("sectionTitle")
        layout.addWidget(pl)
        self.playlist = QListWidget(); self.playlist.setObjectName("playlistWidget")
        self.playlist.setMaximumHeight(120)
        layout.addWidget(self.playlist)

        layout.addStretch()
        self.setLayout(layout)

    def _start_poller(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(2500)

    def _poll(self):
        try:
            if not self.dj or not self.dj.sp:
                return
            cur = self.dj.sp.current_playback()
            if cur and cur.get("is_playing") and cur.get("item"):
                item = cur["item"]
                self.track_label.setText(item["name"])
                self.artist_label.setText(", ".join(a["name"] for a in item["artists"]))
                self.play_btn.setText("⏸")
                dur  = item["duration_ms"] / 1000
                prog = cur["progress_ms"] / 1000
                self.progress.setMaximum(int(dur))
                self.progress.setValue(int(prog))
                self.time_cur.setText(self._fmt(prog))
                self.time_tot.setText(self._fmt(dur))
                self._fetch_album_art(item)   # BUG-01 fix
            else:
                self.track_label.setText("No music playing")
                self.artist_label.setText("")
                self.play_btn.setText("▶")
                self._set_default_art()
        except Exception:
            pass

    @staticmethod
    def _fmt(secs: float) -> str:
        m, s = divmod(int(secs), 60)
        return f"{m}:{s:02d}"

    def _fetch_album_art(self, item: dict):
        """BUG-01: Download real album art from Spotify image URL."""
        try:
            images = item.get("album", {}).get("images", [])
            if not images:
                self._set_default_art()
                return
            url = images[0]["url"]
            if url == self._art_url_cache:
                return  # already showing this art
            self._art_url_cache = url

            def _load():
                try:
                    import requests
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        px = QPixmap()
                        px.loadFromData(r.content)
                        if not px.isNull():
                            # Update on main thread
                            QTimer.singleShot(0, lambda: self.album_art.setPixmap(
                                px.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            ))
                            return
                except Exception:
                    pass
                QTimer.singleShot(0, self._set_default_art)

            threading.Thread(target=_load, daemon=True).start()
        except Exception:
            self._set_default_art()

    def _set_default_art(self):
        px = QPixmap(200, 200)
        px.fill(QColor("#0d0d1a"))
        p = QPainter(px)
        grad = QLinearGradient(0, 0, 200, 200)
        grad.setColorAt(0, QColor("#1a1a3e"))
        grad.setColorAt(1, QColor("#0a0a1a"))
        p.fillRect(px.rect(), grad)
        p.setPen(QColor("#00d9ff"))
        p.setFont(QFont("Segoe UI", 52))
        p.drawText(px.rect(), Qt.AlignCenter, "🎵")
        p.end()
        self.album_art.setPixmap(px)
        self._art_url_cache = ""

    def _toggle_play(self):
        if not self.dj: return
        try:
            cur = self.dj.sp.current_playback()
            if cur and cur.get("is_playing"):
                self.dj.pause(); self.play_btn.setText("▶")
            else:
                self.dj.resume(); self.play_btn.setText("⏸")
        except Exception: pass

    def _prev(self):
        if self.dj: self.dj.previous(); QTimer.singleShot(600, self._poll)

    def _next(self):
        if self.dj: self.dj.skip(); QTimer.singleShot(600, self._poll)

    def _shuffle(self):
        if self.dj:
            res = self.dj.toggle_shuffle()
            active = res and "ON" in res
            self.shuf_btn.setStyleSheet("background-color:#00d9ff;" if active else "")

    def _repeat(self):
        if not self.dj or not self.dj.sp: return
        try:
            cur = self.dj.sp.current_playback()
            state = cur.get("repeat_state", "off")
            new = "context" if state == "off" else "off"
            self.dj.sp.repeat(new)
            self.rpt_btn.setStyleSheet("background-color:#00d9ff;" if new != "off" else "")
        except Exception: pass

    def _mute_toggle(self):
        v = self.vol_slider.value()
        if v > 0:
            self._prev_vol = v; self.vol_slider.setValue(0); self.mute_btn.setText("🔇")
        else:
            self.vol_slider.setValue(getattr(self, "_prev_vol", 50)); self.mute_btn.setText("🔊")

    def _vol_changed(self, val):
        try:
            if self.dj and self.dj.sp: self.dj.sp.volume(val)
        except Exception: pass
        self.vol_label.setText(f"{val}%")
        self.mute_btn.setText("🔇" if val == 0 else "🔊")

    def _play_mood(self, mood: str):
        if self.dj:
            threading.Thread(target=lambda: self.dj.play_mood(mood), daemon=True).start()
            QTimer.singleShot(1500, self._poll)


# ═══════════════════════════════════════════════════════════════════════════════
# ScrollToBottomButton  — floats over chat, disappears when at bottom
# ═══════════════════════════════════════════════════════════════════════════════

class ScrollToBottomButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("↓", parent)
        self.setFixedSize(40, 40)
        self.setStyleSheet(
            "QPushButton{background:rgba(0,200,255,200);color:#000;"
            "border:none;border-radius:20px;font-size:18px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(0,220,255,255);}"
        )
        self.hide()


# ═══════════════════════════════════════════════════════════════════════════════
# ChatInterface (Main Window) — all 14 bugs fixed + new features
# ═══════════════════════════════════════════════════════════════════════════════

class ChatInterface(QMainWindow):
    """The primary Makima desktop UI — v2."""

    _sig_message    = pyqtSignal(str, bool, list, bool)  # text, is_user, files, skip_history
    _sig_status     = pyqtSignal(str, str)
    _sig_typing_on  = pyqtSignal()
    _sig_typing_off = pyqtSignal()
    _sig_mood       = pyqtSignal(str)   # emotion string from MoodTracker

    def __init__(self, makima_instance):
        super().__init__()
        self.makima = makima_instance

        self.theme_mgr    = ThemeManager()
        self.chat_history = ChatHistory()
        self.notif_mgr    = NotificationManager()

        # BUG-12: HUD not started here — lazy init on demand
        self._hud = None

        self.music_dj = getattr(getattr(makima_instance, 'manager', None), '_music_dj', None)
        if self.music_dj is None:
            try:
                from systems.music_dj import MusicDJ
                self.music_dj = MusicDJ(speak_callback=makima_instance.speak)
            except Exception:
                self.music_dj = None

        self.mini_window    = None
        self.voice_viz      = None
        self.attached_files: list[str] = []
        self._typing_widget = None
        self._processing    = False    # BUG-14

        self._build_ui()

        # Signals
        self._sig_message.connect(self._on_message)
        self._sig_status.connect(self._on_status)
        self._sig_typing_on.connect(self._show_typing)
        self._sig_typing_off.connect(self._hide_typing)
        self._sig_mood.connect(self._on_mood)

        # Keyboard shortcuts — BUG-14 global shortcuts
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._show_history)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._toggle_mini)
        QShortcut(QKeySequence("Ctrl+/"), self).activated.connect(self._focus_search)

        self._load_history()
        self.apply_theme(self.theme_mgr.current_theme)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("🌸 Makima AI Assistant")
        self.setGeometry(80, 60, 1460, 920)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout()
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Left sidebar with quick commands
        root.addWidget(self._make_sidebar(), 0)

        # Centre: chat
        chat_box = QWidget()
        chat_box.setObjectName("chatContainer")
        cl = QVBoxLayout()
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._make_header())
        cl.addWidget(self._make_search_bar())

        # Scroll + drop overlay
        scroll_container = QWidget()
        scl = QVBoxLayout()
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("chatScroll")
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_change)

        self.file_drop = FileDropArea(self.scroll)
        self.file_drop.files_dropped.connect(self._on_files_dropped)

        self.chat_widget = QWidget()
        self.chat_vbox = QVBoxLayout()
        self.chat_vbox.setAlignment(Qt.AlignTop)
        self.chat_vbox.setSpacing(8)
        self.chat_widget.setLayout(self.chat_vbox)
        self.scroll.setWidget(self.chat_widget)
        scl.addWidget(self.scroll)
        scroll_container.setLayout(scl)

        # Floating scroll-to-bottom button
        self._scroll_btn = ScrollToBottomButton(self.scroll)
        self._scroll_btn.clicked.connect(self._scroll_bottom)
        cl.addWidget(scroll_container)
        cl.addWidget(self._make_input_area())
        chat_box.setLayout(cl)
        root.addWidget(chat_box, 7)

        # Right: music panel
        music_box = QWidget()
        music_box.setObjectName("musicPanel")
        ml = QVBoxLayout()
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(MusicControlWidget(self.music_dj))
        music_box.setLayout(ml)
        root.addWidget(music_box, 3)

        central.setLayout(root)

        # Welcome bubble
        self._add_bubble(
            "👋 Hey! I'm Makima, your AI assistant.\n\n"
            "✨ Tips:\n"
            "• Ctrl+K → Chat history   • Ctrl+M → Mini mode\n"
            "• Drag & drop files into chat\n"
            "• Voice input via 🎤 button\n"
            "• Try: 'good morning' for daily briefing\n\n"
            "How can I help you today?",
            is_user=False, skip_history=True,
        )

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _make_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(60)
        lo = QVBoxLayout()
        lo.setContentsMargins(6, 16, 6, 16)
        lo.setSpacing(10)

        cmds = [
            ("🌅", "Good morning briefing",       "good morning"),
            ("🧠", "What do you remember?",        "what do you remember about me"),
            ("🎭", "How am I feeling?",             "how am I feeling?"),
            ("📝", "Summarize session",             "summarize this session"),
            ("🔋", "Battery / system status",       "what is the battery percentage"),
            ("📋", "Clipboard actions",             "what's in my clipboard"),
            ("🔍", "Web search mode",               "search for "),
            ("⚙",  "Open settings",                "_settings"),
            ("🖥",  "Toggle HUD",                   "_hud"),
        ]

        for icon, tip, cmd in cmds:
            btn = QPushButton(icon)
            btn.setObjectName("sidebarButton")
            btn.setFixedSize(46, 46)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, c=cmd: self._sidebar_action(c))
            lo.addWidget(btn, alignment=Qt.AlignCenter)

        lo.addStretch()
        sb.setLayout(lo)
        return sb

    def _sidebar_action(self, cmd: str):
        if cmd == "_settings":
            self._open_settings()
        elif cmd == "_hud":
            self._toggle_hud()
        else:
            self.msg_input.setText(cmd)
            if not cmd.endswith(" "):  # don't auto-send incomplete commands
                self._send()

    # ── Header ────────────────────────────────────────────────────────────────

    def _make_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(72)
        hl = QHBoxLayout()
        hl.setContentsMargins(20, 0, 20, 0)

        # Avatar + mood badge
        avatar_container = QWidget()
        avatar_container.setFixedSize(52, 52)
        avatar_lyt = QVBoxLayout()
        avatar_lyt.setContentsMargins(0, 0, 0, 0)
        self.avatar_label = QLabel("🎭")
        self.avatar_label.setObjectName("avatar")
        self.avatar_label.setAlignment(Qt.AlignCenter)
        avatar_lyt.addWidget(self.avatar_label)
        avatar_container.setLayout(avatar_lyt)

        # Mood badge (small colored circle bottom-right of avatar)
        self.mood_badge = QLabel("●")
        self.mood_badge.setObjectName("moodBadge")
        self.mood_badge.setFixedSize(14, 14)
        self.mood_badge.setStyleSheet("color:#00ff88;font-size:8px;")

        hl.addWidget(avatar_container)
        hl.addWidget(self.mood_badge, 0, Qt.AlignBottom)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        n = QLabel("Makima")
        n.setObjectName("headerName")
        self.status_label = QLabel("🟢 Online")
        self.status_label.setObjectName("statusLabel")
        name_col.addWidget(n)
        name_col.addWidget(self.status_label)
        hl.addLayout(name_col)
        hl.addStretch()

        for icon, tip, slot in [
            ("📜", "Chat History (Ctrl+K)",  self._show_history),
            ("🎨", "Change Theme",            self._show_theme_selector),
            ("🗗",  "Mini Mode (Ctrl+M)",     self._toggle_mini),
            ("🖥",  "Toggle HUD",             self._toggle_hud),
            ("⚙",  "Settings",               self._open_settings),
        ]:
            b = QPushButton(icon)
            b.setObjectName("headerButton")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            hl.addWidget(b)

        self.notif_btn = QPushButton("🔔")
        self.notif_btn.setObjectName("headerButton")
        self.notif_btn.setToolTip("Notifications: ON")
        self.notif_btn.clicked.connect(self._toggle_notifs)
        hl.addWidget(self.notif_btn)

        header.setLayout(hl)
        return header

    # ── Search bar ────────────────────────────────────────────────────────────

    def _make_search_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(40)
        lo = QHBoxLayout()
        lo.setContentsMargins(16, 4, 16, 4)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("🔍  Search messages…")
        self.search_input.textChanged.connect(self._filter_bubbles)
        lo.addWidget(self.search_input)
        clear_btn = QPushButton("✕")
        clear_btn.setObjectName("headerButton")
        clear_btn.setFixedSize(28, 28)
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        lo.addWidget(clear_btn)
        bar.setLayout(lo)
        return bar

    def _filter_bubbles(self, query: str):
        """Show/hide chat bubbles matching the search query."""
        query = query.lower().strip()
        for i in range(self.chat_vbox.count()):
            w = self.chat_vbox.itemAt(i).widget()
            if w and isinstance(w, ChatBubble):
                if not query:
                    w.show()
                else:
                    w.setVisible(query in w.message.lower())

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    # ── Input area ────────────────────────────────────────────────────────────

    def _make_input_area(self) -> QFrame:
        container = QFrame()
        container.setObjectName("inputContainer")
        outer = QVBoxLayout()
        outer.setContentsMargins(20, 12, 20, 12)

        self.attach_bar = QWidget()
        self.attach_bar_layout = QHBoxLayout()
        self.attach_bar.setLayout(self.attach_bar_layout)
        self.attach_bar.hide()
        outer.addWidget(self.attach_bar)

        row = QHBoxLayout()
        row.setSpacing(10)

        attach = QPushButton("📎")
        attach.setObjectName("attachButton")
        attach.setToolTip("Attach File")
        attach.setFixedSize(56, 56)
        attach.clicked.connect(self._attach_file)
        row.addWidget(attach)

        self.msg_input = QTextEdit()
        self.msg_input.setObjectName("messageInput")
        self.msg_input.setPlaceholderText("Type your message… (Enter to send, Shift+Enter for new line)")
        self.msg_input.setFixedHeight(56)
        self.msg_input.installEventFilter(self)
        row.addWidget(self.msg_input)

        # BUG-14: track processing state visually
        self.send_btn = AnimatedButton("Send ➤")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setFixedSize(100, 56)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        self.voice_btn = AnimatedButton("🎤")
        self.voice_btn.setObjectName("voiceButton")
        self.voice_btn.setFixedSize(56, 56)
        self.voice_btn.clicked.connect(self._toggle_voice)
        row.addWidget(self.voice_btn)

        outer.addLayout(row)
        container.setLayout(outer)
        return container

    # ── Event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.msg_input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    # ── Send / process — BUG-14: lock during processing ───────────────────────

    def _send(self):
        if self._processing:  # BUG-14: prevent spam
            return
        text = self.msg_input.toPlainText().strip()
        if not text and not self.attached_files:
            return

        self.msg_input.clear()
        files = self.attached_files.copy()
        self.attached_files.clear()
        self._refresh_attachments()

        self._add_bubble(text, is_user=True, files=files)
        self._set_processing(True)

        threading.Thread(target=self._process, args=(text, files), daemon=True).start()

    def _process(self, text: str, files: list):
        try:
            # BUG-06: show thinking state
            self._sig_typing_on.emit()
            response = self.makima.process_input(text)
            response = response or "Done."
        except Exception as e:
            response = f"⚠️ Error: {e}"
        finally:
            self._sig_typing_off.emit()

        # BUG-06: show speaking state briefly
        self._sig_status.emit("💬 Speaking…", "#c084fc")
        self._sig_message.emit(response, False, [], False)
        QTimer.singleShot(800, lambda: self._sig_status.emit("🟢 Online", "#00ff88"))

        if self.notif_mgr.enabled and len(response) > 5:
            preview = response[:100] + ("…" if len(response) > 100 else "")
            self.notif_mgr.show_notification("Makima", preview)

        # Update mood badge if MoodTracker available
        mood = getattr(getattr(self.makima, 'manager', None), 'mood', None)
        if mood:
            self._sig_mood.emit(mood.current_emotion)

    def _set_processing(self, state: bool):
        self._processing = state
        self.send_btn.setEnabled(not state)
        self.send_btn.setText("…" if state else "Send ➤")
        if state:
            self._sig_status.emit("🔄 Thinking…", "#FFA500")

    # ── Bubble management ─────────────────────────────────────────────────────

    def _add_bubble(self, text: str, is_user: bool = True, files: list = None,
                    skip_history: bool = False):
        self._sig_message.emit(text, is_user, files or [], skip_history)

    def _on_message(self, text: str, is_user: bool, files: list, skip_history: bool):
        bubble = ChatBubble(text, is_user, files=files, skip_history=skip_history)
        self.chat_vbox.addWidget(bubble)
        # BUG-05: only save to history if not a warm-up bubble
        if not skip_history:
            self.chat_history.add_message(text, is_user, files)
        if is_user is False:
            self._set_processing(False)
        QTimer.singleShot(80, self._scroll_bottom)

    def _scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_scroll_change(self, value: int):
        sb = self.scroll.verticalScrollBar()
        at_bottom = (sb.maximum() - value) < 60
        if at_bottom:
            self._scroll_btn.hide()
        else:
            # Position the button
            self._scroll_btn.move(
                self.scroll.width() - 56,
                self.scroll.height() - 56,
            )
            self._scroll_btn.show()
            self._scroll_btn.raise_()

    def _on_status(self, text: str, color: str):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def _on_mood(self, emotion: str):
        """Update mood badge colour."""
        colors = {
            "happy": "#fbbf24", "excited": "#f97316", "sad": "#60a5fa",
            "stressed": "#f59e0b", "frustrated": "#ef4444", "tired": "#6b7280",
            "calm": "#4ade80", "curious": "#a78bfa", "neutral": "#00ff88",
        }
        c = colors.get(emotion, "#00ff88")
        self.mood_badge.setStyleSheet(f"color:{c};font-size:8px;")
        self.mood_badge.setToolTip(f"Your mood: {emotion}")

    # ── Typing indicator — BUG-06 ─────────────────────────────────────────────

    def _show_typing(self):
        if self._typing_widget:
            return
        self._typing_widget = TypingIndicator()
        # Wrap in a bubble-like layout
        wrapper = QHBoxLayout()
        wrapper.addWidget(self._typing_widget)
        wrapper.addStretch()
        container = QWidget()
        container.setLayout(wrapper)
        self.chat_vbox.addWidget(container)
        self._typing_container = container
        QTimer.singleShot(50, self._scroll_bottom)

    def _hide_typing(self):
        if hasattr(self, "_typing_container"):
            self._typing_container.deleteLater()
            self._typing_container = None
        self._typing_widget = None

    # ── Attachments ───────────────────────────────────────────────────────────

    def _attach_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All (*.*)")
        if paths:
            self._on_files_dropped(paths)

    def _on_files_dropped(self, paths: list):
        self.attached_files.extend(paths)
        self._refresh_attachments()

    def _refresh_attachments(self):
        while self.attach_bar_layout.count():
            w = self.attach_bar_layout.takeAt(0).widget()
            if w: w.deleteLater()
        if self.attached_files:
            self.attach_bar.show()
            for fp in self.attached_files:
                chip = QFrame(); chip.setObjectName("attachmentChip")
                cl = QHBoxLayout(); cl.setContentsMargins(8, 2, 8, 2)
                lbl = QLabel(f"📎 {os.path.basename(fp)}"); lbl.setObjectName("attachmentLabel")
                rm = QPushButton("✕"); rm.setObjectName("removeAttachmentButton")
                rm.setFixedSize(20, 20)
                rm.clicked.connect(lambda _, p=fp: self._remove_attach(p))
                cl.addWidget(lbl); cl.addWidget(rm)
                chip.setLayout(cl)
                self.attach_bar_layout.addWidget(chip)
            self.attach_bar_layout.addStretch()
        else:
            self.attach_bar.hide()

    def _remove_attach(self, path: str):
        if path in self.attached_files:
            self.attached_files.remove(path)
            self._refresh_attachments()

    # ── Voice — BUG-03/10 ─────────────────────────────────────────────────────

    def _toggle_voice(self):
        if self.voice_btn.text() == "🎤":
            self.voice_btn.setText("⏹")
            self.voice_btn.setObjectName("voiceButtonActive")
            self.voice_btn.setStyle(self.voice_btn.style())
            # BUG-10: use mapToGlobal for correct positioning
            self.voice_viz = VoiceVisualizer(self)
            pos = self.voice_btn.mapToGlobal(QPoint(0, -90))
            self.voice_viz.move(pos)
            self.voice_viz.show()
            threading.Thread(target=self._listen, daemon=True).start()
        else:
            self._stop_voice()

    def _listen(self):
        try:
            cmd = self.makima.listen_once()
            if cmd:
                # BUG-03: fill input box, let user review (don't auto-send)
                QTimer.singleShot(0, lambda: self.msg_input.setText(cmd))
                QTimer.singleShot(0, lambda: self.msg_input.setFocus())
        except Exception as e:
            logger.warning(f"Voice error: {e}")
        finally:
            QTimer.singleShot(0, self._stop_voice)

    def _stop_voice(self):
        self.voice_btn.setText("🎤")
        self.voice_btn.setObjectName("voiceButton")
        self.voice_btn.setStyle(self.voice_btn.style())
        if self.voice_viz:
            self.voice_viz.close()
            self.voice_viz = None

    # ── History — BUG-13: clicking a session loads messages ───────────────────

    def _show_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("📜 Chat History")
        dlg.setFixedSize(680, 720)
        lo = QVBoxLayout()

        search_row = QHBoxLayout()
        search_in = QLineEdit(); search_in.setPlaceholderText("Search messages…")
        search_btn = QPushButton("🔍")
        search_row.addWidget(search_in); search_row.addWidget(search_btn)
        lo.addLayout(search_row)

        # Session list (left) + preview (right)
        split = QHBoxLayout()
        sessions_list = QListWidget()
        sessions_list.setMaximumWidth(220)
        preview_area = QTextBrowser()
        preview_area.setOpenExternalLinks(True)

        for s in self.chat_history.get_sessions():
            item = QListWidgetItem(f"📅 {s['date']}\n{s['message_count']} messages")
            item.setData(Qt.UserRole, s["file"])
            sessions_list.addItem(item)

        def _load_session(item: QListWidgetItem):
            fname = item.data(Qt.UserRole)
            messages = self.chat_history.load_session_file(fname)
            html = "<style>body{font-family:Segoe UI;} .u{color:#00d9ff} .m{color:#aaa}</style>"
            for msg in messages:
                role = "u" if msg.get("is_user") else "m"
                who = "You" if msg.get("is_user") else "Makima"
                ts = msg.get("timestamp", "")
                text = msg.get("message", "").replace("<", "&lt;").replace(">", "&gt;")
                html += f'<p><span class="{role}"><b>{who}</b> <small>{ts}</small></span><br>{text}</p><hr>'
            preview_area.setHtml(html)

        sessions_list.itemClicked.connect(_load_session)  # BUG-13

        def _search():
            q = search_in.text().strip()
            if not q:
                return
            results = self.chat_history.search(q)
            html = f"<b>Results for '{q}':</b><br><br>"
            for r in results[:30]:
                who = "You" if r.get("is_user") else "Makima"
                text = r.get("message", "").replace("<", "&lt;")
                html += f"<p><b>{who}:</b> {text}</p><hr>"
            preview_area.setHtml(html or "No results found.")

        search_btn.clicked.connect(_search)
        search_in.returnPressed.connect(_search)

        split.addWidget(sessions_list)
        split.addWidget(preview_area)
        lo.addLayout(split)

        close_btn = QPushButton("Close"); close_btn.clicked.connect(dlg.close)
        lo.addWidget(close_btn, alignment=Qt.AlignRight)
        dlg.setLayout(lo)
        dlg.exec_()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _show_theme_selector(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("🎨 Choose Your Theme")
        dialog.setFixedSize(820, 600)
        layout = QVBoxLayout()

        title = QLabel("🎨 Select Your Theme")
        title.setStyleSheet("font-size:18px;font-weight:bold;padding:10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); grid = QGridLayout(); grid.setSpacing(16)

        themes = self.theme_mgr.get_available_themes()
        for i, theme_name in enumerate(themes):
            card = QFrame()
            card.setStyleSheet(
                "QFrame{border:1px solid #333;border-radius:10px;padding:8px;}"
                "QFrame:hover{border-color:#00d9ff;}"
            )
            cl = QVBoxLayout(); cl.setSpacing(8)
            preview = self.theme_mgr.create_theme_preview(theme_name)
            cl.addWidget(preview, alignment=Qt.AlignCenter)
            apply_btn = QPushButton(f"✓ {theme_name.replace('_',' ').title()}")
            apply_btn.clicked.connect(
                lambda _, t=theme_name, d=dialog: (self.apply_theme(t), d.accept())
            )
            cl.addWidget(apply_btn)
            card.setLayout(cl)
            grid.addWidget(card, i // 3, i % 3)

        inner.setLayout(grid); scroll.setWidget(inner)
        layout.addWidget(scroll)

        custom_btn = QPushButton("➕ Create Custom Theme")
        custom_btn.clicked.connect(lambda: ThemeCreatorDialog(self.theme_mgr, self).exec_())
        layout.addWidget(custom_btn)
        dialog.setLayout(layout)
        dialog.exec_()

    def apply_theme(self, name: str):
        qss = self.theme_mgr.load_theme(name)
        self.setStyleSheet(qss)

    # ── Mini mode ─────────────────────────────────────────────────────────────

    def _toggle_mini(self):
        self.mini_window = MiniModeWindow(self.makima)
        self.mini_window.expand_requested.connect(self.show)
        self.mini_window.show()
        self.hide()

    # ── HUD — BUG-12: lazy init, no conflict ──────────────────────────────────

    def _toggle_hud(self):
        if self._hud is None:
            try:
                from ui.hud import MakimaHUD
                self._hud = MakimaHUD()
            except Exception as e:
                logger.warning(f"HUD unavailable: {e}")
                return
        if self._hud.visible:
            self._hud.hide()
        else:
            self._hud.show()

    # ── Notifications ─────────────────────────────────────────────────────────

    def _toggle_notifs(self):
        self.notif_mgr.toggle()
        if self.notif_mgr.enabled:
            self.notif_btn.setText("🔔"); self.notif_btn.setToolTip("Notifications: ON")
        else:
            self.notif_btn.setText("🔕"); self.notif_btn.setToolTip("Notifications: OFF")

    # ── Settings — BUG-08 guard ────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self.makima, self).exec_()

    # ── History warm-up — BUG-07 ──────────────────────────────────────────────

    def _load_history(self):
        for msg in self.chat_history.get_recent_messages(12):
            if msg.get("message"):
                # BUG-05: skip_history=True so warm-up bubbles don't re-save
                bubble = ChatBubble(
                    msg["message"], msg["is_user"],
                    msg.get("timestamp"), files=msg.get("files", []),
                    skip_history=True,
                )
                self.chat_vbox.addWidget(bubble)
        # BUG-07: scroll to bottom after loading
        QTimer.singleShot(150, self._scroll_bottom)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.chat_history.save()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# Launcher
# ═══════════════════════════════════════════════════════════════════════════════

def launch_ui(makima_instance):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ChatInterface(makima_instance)
    window.show()
    sys.exit(app.exec_())
