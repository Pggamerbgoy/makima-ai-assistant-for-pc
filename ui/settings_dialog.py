"""
ui/settings_dialog.py

Settings Dialog
────────────────
Tabbed settings panel for Makima — covers:
  • General (persona, language, startup)
  • Voice  (TTS engine, mic index, energy threshold)
  • AI     (model backend, temperature, max tokens)
  • Music  (auto-DJ toggle, default volume overrides)
  • Theme  (pick theme, accent color)
"""

import os
import json
import logging
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QCheckBox, QSlider, QSpinBox,
    QPushButton, QLineEdit, QGroupBox, QFormLayout,
)
from PyQt5.QtCore import Qt

logger = logging.getLogger("Makima.Settings")


class SettingsDialog(QDialog):
    """Tabbed settings dialog."""

    def __init__(self, makima, parent=None):
        super().__init__(parent)
        self.makima = makima
        self.setWindowTitle("⚙ Makima Settings")
        self.setFixedSize(550, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(),  "General")
        tabs.addTab(self._voice_tab(),    "Voice")
        tabs.addTab(self._ai_tab(),       "AI")
        tabs.addTab(self._music_tab(),    "Music DJ")
        tabs.addTab(self._api_tab(),      "Accounts & API")
        layout.addWidget(tabs)

        # Footer buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("sendButton")
        save_btn.clicked.connect(self._save_all)
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    # ── General ───────────────────────────────────────────────────────────────

    def _general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout()

        # Persona
        self.persona_combo = QComboBox()
        self.persona_combo.addItems(["makima", "normal", "date"])
        try:
            current = self.makima.ai.persona
            idx = self.persona_combo.findText(current)
            if idx >= 0:
                self.persona_combo.setCurrentIndex(idx)
        except Exception:
            pass
        form.addRow("Persona:", self.persona_combo)

        # Language
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Auto-detect", "English", "Hindi"])
        form.addRow("Language:", self.lang_combo)

        # Wake word
        self.wake_word_input = QLineEdit(
            os.getenv("MAKIMA_WAKE_WORD", "hey makima")
        )
        form.addRow("Wake Word:", self.wake_word_input)

        # Start minimized
        self.start_mini_cb = QCheckBox("Start in mini mode")
        form.addRow("", self.start_mini_cb)

        tab.setLayout(form)
        return tab

    # ── Voice ─────────────────────────────────────────────────────────────────

    def _voice_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout()

        self.energy_slider = QSlider(Qt.Horizontal)
        self.energy_slider.setRange(100, 2000)
        self.energy_slider.setValue(
            int(os.getenv("MAKIMA_ENERGY_THRESHOLD", "500"))
        )
        form.addRow("Mic Sensitivity:", self.energy_slider)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(1, 30)
        self.pause_spin.setSuffix(" s")
        self.pause_spin.setValue(
            int(float(os.getenv("MAKIMA_PAUSE_THRESHOLD", "0.8")) * 10)
        )
        form.addRow("Pause Threshold:", self.pause_spin)

        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["Edge Neural", "pyttsx3 Offline", "ElevenLabs"])
        form.addRow("TTS Engine:", self.tts_combo)

        tab.setLayout(form)
        return tab

    # ── AI ────────────────────────────────────────────────────────────────────

    def _ai_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout()

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["Auto (Gemini → Ollama)", "Gemini Only", "Ollama Only"])
        form.addRow("Backend:", self.backend_combo)

        self.model_input = QLineEdit(
            os.getenv("OLLAMA_MODEL", "makima-v3")
        )
        form.addRow("Ollama Model:", self.model_input)

        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 20)  # ×0.1
        self.temp_slider.setValue(7)
        form.addRow("Temperature:", self.temp_slider)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(64, 8192)
        self.max_tokens_spin.setValue(1024)
        self.max_tokens_spin.setSingleStep(128)
        form.addRow("Max Tokens:", self.max_tokens_spin)

        tab.setLayout(form)
        return tab

    # ── Music DJ ──────────────────────────────────────────────────────────────

    def _music_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout()

        self.auto_dj_cb = QCheckBox("Enable Auto-DJ (activity detection)")
        form.addRow("", self.auto_dj_cb)

        # Per-mood volume overrides
        group = QGroupBox("Default Volumes per Mood")
        g_form = QFormLayout()
        self._vol_sliders = {}
        for mood in ["focus", "hype", "chill", "gaming",
                      "coding", "party", "sleep", "sad"]:
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            g_form.addRow(f"{mood.title()}:", slider)
            self._vol_sliders[mood] = slider
        group.setLayout(g_form)
        form.addRow(group)

        tab.setLayout(form)
        return tab

    # ── Accounts & API ────────────────────────────────────────────────────────

    def _api_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout()

        # Basic user info
        self.user_name_input = QLineEdit(os.getenv("USER_NAME", "User"))
        form.addRow("Your Name:", self.user_name_input)

        # Gemini
        self.gemini_api_key = QLineEdit(os.getenv("GEMINI_API_KEY", ""))
        self.gemini_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("Gemini API Key:", self.gemini_api_key)

        # Weather
        self.weather_api_key = QLineEdit(os.getenv("WEATHER_API_KEY", ""))
        self.weather_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("Weather API Key:", self.weather_api_key)

        # Telegram
        self.telegram_token = QLineEdit(os.getenv("TELEGRAM_BOT_TOKEN", ""))
        self.telegram_token.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("Telegram Bot Token:", self.telegram_token)

        # Spotify
        self.spotify_client_id = QLineEdit(os.getenv("SPOTIPY_CLIENT_ID", ""))
        self.spotify_client_id.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("Spotify Client ID:", self.spotify_client_id)

        self.spotify_client_secret = QLineEdit(os.getenv("SPOTIPY_CLIENT_SECRET", ""))
        self.spotify_client_secret.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("Spotify Client Secret:", self.spotify_client_secret)

        # Google Calendar
        self.calendar_enabled = QCheckBox("Enable Google Calendar Integration")
        self.calendar_enabled.setChecked(os.getenv("CALENDAR_ENABLED", "0") == "1")
        form.addRow("", self.calendar_enabled)

        # Note about restart
        note = QLabel("<i>Note: Some changes require restarting Makima.</i>")
        note.setStyleSheet("color: #888888; font-size: 11px;")
        form.addRow("", note)

        tab.setLayout(form)
        return tab

    # ── Save ──────────────────────────────────────────────────────────────────

    def _update_env_file(self, updates: dict):
        """Update the local .env file maintaining comments and ordering."""
        env_path = ".env"
        if not os.path.exists(env_path):
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("")
        
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        updated_keys = set()
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
                
        # Add any net-new keys
        for key, val in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")
                
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _save_all(self):
        """Persist all settings and close."""
        try:
            # Apply persona
            persona = self.persona_combo.currentText()
            if hasattr(self.makima, "ai"):
                self.makima.ai.set_persona(persona)

            # Apply auto-DJ — BUG-08: guard against missing manager/music/dj
            try:
                manager = getattr(self.makima, 'manager', None)
                music_sys = getattr(manager, 'music', None) if manager else None
                dj = getattr(music_sys, '_dj', None) if music_sys else None
                if dj is None:
                    # Try common alternative attribute names
                    dj = getattr(self.makima, '_dj', None) or getattr(self.makima, 'dj', None)
                if dj:
                    dj.auto_dj_enabled = self.auto_dj_cb.isChecked()
                    for mood, slider in self._vol_sliders.items():
                        dj.config.setdefault("volume_overrides", {})[mood] = slider.value()
                    if hasattr(dj, '_save_config'):
                        dj._save_config()
            except Exception as e:
                logger.warning(f"DJ settings save skipped: {e}")

            # Save API configs to .env
            env_updates = {
                "USER_NAME": self.user_name_input.text().strip(),
                "GEMINI_API_KEY": self.gemini_api_key.text().strip(),
                "WEATHER_API_KEY": self.weather_api_key.text().strip(),
                "TELEGRAM_BOT_TOKEN": self.telegram_token.text().strip(),
                "SPOTIPY_CLIENT_ID": self.spotify_client_id.text().strip(),
                "SPOTIPY_CLIENT_SECRET": self.spotify_client_secret.text().strip(),
                "CALENDAR_ENABLED": "1" if self.calendar_enabled.isChecked() else "0",
            }
            self._update_env_file(env_updates)
            
            # Also apply runtime environment variables for immediate effect
            for k, v in env_updates.items():
                os.environ[k] = v

            logger.info("Settings saved.")
        except Exception as e:
            logger.warning(f"Settings save error: {e}")

        self.accept()
