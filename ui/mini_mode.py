"""
ui/mini_mode.py

Mini Mode — Compact Floating Window
─────────────────────────────────────
A small, always-on-top, frameless window with a single input line
and minimal output. Drag to reposition. Double-click to expand
back to the full chat interface.
"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSizeGrip, QFrame,
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QColor

logger = logging.getLogger("Makima.MiniMode")


class MiniModeWindow(QWidget):
    """Compact floating assistant window."""

    expand_requested = pyqtSignal()  # emitted on double-click
    _sig_response = pyqtSignal(str)  # BUG-09: thread-safe response update

    def __init__(self, makima, parent=None):
        super().__init__(parent)
        self.makima = makima
        self._drag_pos = QPoint()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 140)

        self._build_ui()
        self._sig_response.connect(self.response_label.setText)  # BUG-09

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        # Container frame for rounded styling
        frame = QFrame()
        frame.setObjectName("miniFrame")
        frame.setStyleSheet("""
            #miniFrame {
                background-color: rgba(10, 14, 23, 230);
                border: 1px solid #2a3155;
                border-radius: 16px;
            }
        """)
        fl = QVBoxLayout()
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        title = QLabel("🌸 Makima")
        title.setStyleSheet("color: #00d9ff; font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #64748b;"
            "  border: none; font-size: 14px; }"
            "QPushButton:hover { color: #ff3366; }"
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        fl.addLayout(header)

        # Response label (last Makima reply)
        self.response_label = QLabel("How can I help?")
        self.response_label.setWordWrap(True)
        self.response_label.setStyleSheet(
            "color: #e2e8f0; font-size: 12px; padding: 4px 0;"
        )
        self.response_label.setMaximumHeight(40)
        fl.addWidget(self.response_label)

        # Input row
        inp_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a command…")
        self.input_field.setStyleSheet(
            "QLineEdit {"
            "  background-color: #111827; color: #e2e8f0;"
            "  border: 1px solid #2a3155; border-radius: 8px;"
            "  padding: 6px 10px; font-size: 12px;"
            "}"
            "QLineEdit:focus { border-color: #00d9ff; }"
        )
        self.input_field.returnPressed.connect(self._send)
        inp_row.addWidget(self.input_field)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(32, 32)
        send_btn.setStyleSheet(
            "QPushButton { background-color: #00d9ff; color: #0a0e17;"
            "  border: none; border-radius: 8px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #33e1ff; }"
        )
        send_btn.clicked.connect(self._send)
        inp_row.addWidget(send_btn)

        fl.addLayout(inp_row)
        frame.setLayout(fl)
        outer.addWidget(frame)
        self.setLayout(outer)

    # ── Sending ───────────────────────────────────────────────────────────────

    def _send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.response_label.setText("⏳ Thinking…")

        import threading
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text: str):
        try:
            response = self.makima.process_input(text)
            display = (response or "Done.")[:120]
            self._sig_response.emit(display)  # BUG-09: use signal, not direct call
        except Exception as e:
            self._sig_response.emit(f"Error: {e}")

    # ── Dragging ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.expand_requested.emit()
        self.close()
