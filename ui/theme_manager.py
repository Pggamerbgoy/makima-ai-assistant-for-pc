"""
ui/theme_manager.py

Theme Manager — 8 built-in themes + custom theme creator
──────────────────────────────────────────────────────────
Themes:  dark_cyber, light, nord, dracula, matrix, sunset, ocean, forest
Each theme is a JSON file with named color tokens.
The manager generates a full QSS stylesheet from a theme's color dict.
"""

import json
import os
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame,
    QColorDialog, QMessageBox, QFormLayout,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

logger = logging.getLogger("Makima.ThemeManager")

THEMES_DIR = Path(__file__).parent / "themes"


class ThemeManager:
    """Manage UI themes — load, generate QSS, preview, custom create."""

    def __init__(self):
        self.themes_dir = THEMES_DIR
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self.current_theme = "dark_cyber"
        self.custom_themes: dict = {}

        self.create_default_themes()
        self.load_custom_themes()

    # ─── Default theme definitions ────────────────────────────────────────────

    @staticmethod
    def get_dark_cyber_theme():
        return {
            "name": "Dark Cyber",
            "colors": {
                "background":          "#0a0a0a",
                "surface":             "#0f0f0f",
                "surface_elevated":    "#1a1a1a",
                "primary":             "#00d9ff",
                "primary_dark":        "#0099ff",
                "secondary":           "#1a1a2e",
                "secondary_dark":      "#16213e",
                "accent":              "#00ff88",
                "text":                "#ffffff",
                "text_secondary":      "#aaaaaa",
                "text_dim":            "#666666",
                "border":              "#2a2a2a",
                "border_light":        "#3a3a3a",
                "user_bubble":         "#00d9ff",
                "user_bubble_end":     "#0099ff",
                "makima_bubble":       "#1e1e2e",
                "makima_bubble_border":"#2a2a3e",
                "input_bg":            "#2a2a2a",
                "button_hover":        "#3a3a3a",
                "error":               "#ff3366",
                "warning":             "#FFA500",
                "success":             "#00ff88",
            },
        }

    @staticmethod
    def get_light_theme():
        return {
            "name": "Light",
            "colors": {
                "background":          "#ffffff",
                "surface":             "#f5f5f5",
                "surface_elevated":    "#eeeeee",
                "primary":             "#2196F3",
                "primary_dark":        "#1976D2",
                "secondary":           "#e3f2fd",
                "secondary_dark":      "#bbdefb",
                "accent":              "#4CAF50",
                "text":                "#000000",
                "text_secondary":      "#666666",
                "text_dim":            "#999999",
                "border":              "#dddddd",
                "border_light":        "#eeeeee",
                "user_bubble":         "#2196F3",
                "user_bubble_end":     "#1976D2",
                "makima_bubble":       "#e3f2fd",
                "makima_bubble_border":"#bbdefb",
                "input_bg":            "#ffffff",
                "button_hover":        "#e3f2fd",
                "error":               "#f44336",
                "warning":             "#ff9800",
                "success":             "#4CAF50",
            },
        }

    @staticmethod
    def get_nord_theme():
        return {
            "name": "Nord",
            "colors": {
                "background":          "#2E3440",
                "surface":             "#3B4252",
                "surface_elevated":    "#434C5E",
                "primary":             "#88C0D0",
                "primary_dark":        "#5E81AC",
                "secondary":           "#4C566A",
                "secondary_dark":      "#434C5E",
                "accent":              "#A3BE8C",
                "text":                "#ECEFF4",
                "text_secondary":      "#D8DEE9",
                "text_dim":            "#4C566A",
                "border":              "#4C566A",
                "border_light":        "#5E81AC",
                "user_bubble":         "#88C0D0",
                "user_bubble_end":     "#5E81AC",
                "makima_bubble":       "#3B4252",
                "makima_bubble_border":"#4C566A",
                "input_bg":            "#3B4252",
                "button_hover":        "#434C5E",
                "error":               "#BF616A",
                "warning":             "#EBCB8B",
                "success":             "#A3BE8C",
            },
        }

    @staticmethod
    def get_dracula_theme():
        return {
            "name": "Dracula",
            "colors": {
                "background":          "#282a36",
                "surface":             "#21222c",
                "surface_elevated":    "#343746",
                "primary":             "#bd93f9",
                "primary_dark":        "#9580ff",
                "secondary":           "#44475a",
                "secondary_dark":      "#383a59",
                "accent":              "#50fa7b",
                "text":                "#f8f8f2",
                "text_secondary":      "#6272a4",
                "text_dim":            "#44475a",
                "border":              "#44475a",
                "border_light":        "#6272a4",
                "user_bubble":         "#bd93f9",
                "user_bubble_end":     "#9580ff",
                "makima_bubble":       "#343746",
                "makima_bubble_border":"#44475a",
                "input_bg":            "#343746",
                "button_hover":        "#44475a",
                "error":               "#ff5555",
                "warning":             "#ffb86c",
                "success":             "#50fa7b",
            },
        }

    @staticmethod
    def get_matrix_theme():
        return {
            "name": "Matrix",
            "colors": {
                "background":          "#000000",
                "surface":             "#001a00",
                "surface_elevated":    "#003300",
                "primary":             "#00ff00",
                "primary_dark":        "#00cc00",
                "secondary":           "#003300",
                "secondary_dark":      "#002200",
                "accent":              "#00ff00",
                "text":                "#00ff00",
                "text_secondary":      "#00cc00",
                "text_dim":            "#006600",
                "border":              "#003300",
                "border_light":        "#00ff00",
                "user_bubble":         "#00ff00",
                "user_bubble_end":     "#00cc00",
                "makima_bubble":       "#001a00",
                "makima_bubble_border":"#003300",
                "input_bg":            "#001a00",
                "button_hover":        "#003300",
                "error":               "#ff0000",
                "warning":             "#ffff00",
                "success":             "#00ff00",
            },
        }

    @staticmethod
    def get_sunset_theme():
        return {
            "name": "Sunset",
            "colors": {
                "background":          "#1a0e0e",
                "surface":             "#2d1515",
                "surface_elevated":    "#3d1f1f",
                "primary":             "#ff6b6b",
                "primary_dark":        "#ee5a52",
                "secondary":           "#4a2020",
                "secondary_dark":      "#3d1818",
                "accent":              "#ffa07a",
                "text":                "#fff5f5",
                "text_secondary":      "#ffcccc",
                "text_dim":            "#996666",
                "border":              "#4a2020",
                "border_light":        "#663333",
                "user_bubble":         "#ff6b6b",
                "user_bubble_end":     "#ee5a52",
                "makima_bubble":       "#2d1515",
                "makima_bubble_border":"#4a2020",
                "input_bg":            "#2d1515",
                "button_hover":        "#3d1f1f",
                "error":               "#ff3860",
                "warning":             "#ffc048",
                "success":             "#48c774",
            },
        }

    @staticmethod
    def get_ocean_theme():
        return {
            "name": "Ocean",
            "colors": {
                "background":          "#0a1628",
                "surface":             "#132f4c",
                "surface_elevated":    "#1e4976",
                "primary":             "#00b4d8",
                "primary_dark":        "#0096c7",
                "secondary":           "#1a3a52",
                "secondary_dark":      "#14304a",
                "accent":              "#90e0ef",
                "text":                "#caf0f8",
                "text_secondary":      "#90e0ef",
                "text_dim":            "#48cae4",
                "border":              "#1a3a52",
                "border_light":        "#2a5a82",
                "user_bubble":         "#00b4d8",
                "user_bubble_end":     "#0096c7",
                "makima_bubble":       "#132f4c",
                "makima_bubble_border":"#1a3a52",
                "input_bg":            "#132f4c",
                "button_hover":        "#1e4976",
                "error":               "#ef476f",
                "warning":             "#ffd166",
                "success":             "#06ffa5",
            },
        }

    @staticmethod
    def get_forest_theme():
        return {
            "name": "Forest",
            "colors": {
                "background":          "#0d1b0d",
                "surface":             "#1a331a",
                "surface_elevated":    "#2d4d2d",
                "primary":             "#52b788",
                "primary_dark":        "#40916c",
                "secondary":           "#233623",
                "secondary_dark":      "#1a2e1a",
                "accent":              "#95d5b2",
                "text":                "#d8f3dc",
                "text_secondary":      "#b7e4c7",
                "text_dim":            "#74c69d",
                "border":              "#233623",
                "border_light":        "#2d4b2d",
                "user_bubble":         "#52b788",
                "user_bubble_end":     "#40916c",
                "makima_bubble":       "#1a331a",
                "makima_bubble_border":"#233623",
                "input_bg":            "#1a331a",
                "button_hover":        "#2d4d2d",
                "error":               "#e63946",
                "warning":             "#f4a261",
                "success":             "#2a9d8f",
            },
        }

    # ─── Theme file management ────────────────────────────────────────────────

    def create_default_themes(self):
        """Write default theme JSONs if they don't already exist."""
        defaults = {
            "dark_cyber": self.get_dark_cyber_theme(),
            "light":      self.get_light_theme(),
            "nord":       self.get_nord_theme(),
            "dracula":    self.get_dracula_theme(),
            "matrix":     self.get_matrix_theme(),
            "sunset":     self.get_sunset_theme(),
            "ocean":      self.get_ocean_theme(),
            "forest":     self.get_forest_theme(),
        }
        for name, data in defaults.items():
            path = self.themes_dir / f"{name}.json"
            if not path.exists():
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"Could not write theme {name}: {e}")

    def get_available_themes(self) -> list[str]:
        """Return sorted list of theme file stems."""
        return sorted(p.stem for p in self.themes_dir.glob("*.json"))

    def load_theme(self, theme_name: str) -> str:
        """Load a theme's JSON and return the compiled QSS string."""
        path = self.themes_dir / f"{theme_name}.json"
        if not path.exists():
            logger.warning(f"Theme '{theme_name}' not found — falling back to dark_cyber")
            theme_name = "dark_cyber"
            path = self.themes_dir / f"{theme_name}.json"

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = self.get_dark_cyber_theme()

        self.current_theme = theme_name
        return self.generate_stylesheet(data)

    # ─── Custom themes ────────────────────────────────────────────────────────

    def save_custom_theme(self, name: str, theme_data: dict):
        path = self.themes_dir / f"custom_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(theme_data, f, indent=4, ensure_ascii=False)
        self.custom_themes[name] = theme_data

    def load_custom_themes(self):
        for path in self.themes_dir.glob("custom_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.custom_themes[path.stem.replace("custom_", "")] = data
            except Exception:
                pass

    # ─── Preview widget ───────────────────────────────────────────────────────

    def create_theme_preview(self, theme_name: str) -> QWidget:
        """Build a small color-swatch preview card for a theme."""
        path = self.themes_dir / f"{theme_name}.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = self.get_dark_cyber_theme()

        colors = data["colors"]

        preview = QWidget()
        preview.setFixedSize(200, 100)
        preview.setStyleSheet(
            f"background-color: {colors['background']};"
            f"border: 2px solid {colors['primary']};"
            "border-radius: 8px;"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)

        swatches = QHBoxLayout()
        for key in ("primary", "secondary", "accent"):
            box = QLabel()
            box.setFixedSize(50, 36)
            box.setStyleSheet(
                f"background-color: {colors[key]}; border-radius: 4px;"
            )
            swatches.addWidget(box)
        layout.addLayout(swatches)

        label = QLabel(data.get("name", theme_name))
        label.setStyleSheet(
            f"color: {colors['text']}; font-size: 14px; font-weight: bold;"
        )
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        preview.setLayout(layout)
        return preview

    # ═══════════════════════════════════════════════════════════════════════════
    # QSS Generator — produces a complete stylesheet from color tokens
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def generate_stylesheet(theme_data: dict) -> str:
        c = theme_data["colors"]
        return f"""
        /* ═══════ MAIN WINDOW ═══════ */
        QMainWindow {{
            background-color: {c['background']};
        }}
        QWidget {{
            font-family: "Segoe UI", Arial, sans-serif;
        }}

        /* ═══════ CHAT CONTAINER ═══════ */
        #chatContainer {{
            background-color: {c['surface']};
        }}

        /* ═══════ HEADER ═══════ */
        #header {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['secondary']}, stop:1 {c['secondary_dark']});
            border-bottom: 2px solid {c['primary']};
        }}
        #avatar {{ font-size: 36px; padding: 5px; }}
        #headerName {{
            color: {c['text']}; font-size: 22px;
            font-weight: bold; letter-spacing: 1px;
        }}
        #statusLabel {{ color: {c['accent']}; font-size: 12px; }}
        #headerButton {{
            background-color: transparent; color: {c['primary']};
            font-size: 20px; border: none; padding: 10px;
            border-radius: 8px; min-width: 40px; min-height: 40px;
        }}
        #headerButton:hover {{
            background-color: rgba(255,255,255,0.1);
            border: 1px solid {c['primary']};
        }}
        #headerButton:pressed {{
            background-color: {c['primary']}; color: {c['background']};
        }}

        /* ═══════ CHAT SCROLL ═══════ */
        #chatScroll {{
            border: none; background-color: {c['surface']};
        }}
        QScrollBar:vertical {{
            background-color: {c['surface_elevated']};
            width: 12px; border-radius: 6px; margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {c['primary']};
            border-radius: 6px; min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {c['primary_dark']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        /* ═══════ CHAT BUBBLES ═══════ */
        #userBubble {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['user_bubble']}, stop:1 {c['user_bubble_end']});
            border-radius: 18px; padding: 14px 18px; max-width: 450px;
        }}
        #makimaBubble {{
            background-color: {c['makima_bubble']};
            border: 1px solid {c['makima_bubble_border']};
            border-radius: 18px; padding: 14px 18px; max-width: 450px;
        }}
        #messageText {{
            color: {c['text']}; font-size: 14px; line-height: 1.6;
        }}
        #timestamp {{
            color: {c['text_dim']}; font-size: 10px; margin-top: 6px;
        }}

        /* ═══════ FILE ATTACHMENTS ═══════ */
        #fileAttachment {{
            background-color: {c['surface_elevated']};
            color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 8px; padding: 8px 12px; font-size: 12px;
        }}
        #fileAttachment:hover {{
            background-color: {c['button_hover']};
            border: 1px solid {c['primary']};
        }}
        #attachmentChip {{
            background-color: {c['surface_elevated']};
            border: 1px solid {c['border']};
            border-radius: 16px; padding: 4px 8px;
        }}
        #attachmentLabel {{ color: {c['text']}; font-size: 12px; }}
        #removeAttachmentButton {{
            background-color: transparent; color: {c['error']};
            border: none; font-size: 14px; padding: 2px 6px;
        }}
        #removeAttachmentButton:hover {{
            background-color: {c['error']}; color: {c['text']};
            border-radius: 4px;
        }}

        /* ═══════ INPUT CONTAINER ═══════ */
        #inputContainer {{
            background-color: {c['surface_elevated']};
            border-top: 2px solid {c['border']};
        }}
        #messageInput {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 2px solid {c['border']}; border-radius: 12px;
            padding: 12px; font-size: 14px;
            selection-background-color: {c['primary']};
        }}
        #messageInput:focus {{ border: 2px solid {c['primary']}; }}
        #attachButton {{
            background-color: {c['surface_elevated']};
            color: {c['text_secondary']}; border: 2px solid {c['border']};
            border-radius: 12px; font-size: 20px;
        }}
        #attachButton:hover {{
            background-color: {c['button_hover']};
            border: 2px solid {c['primary']};
        }}
        #sendButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['primary']}, stop:1 {c['primary_dark']});
            color: {c['text']}; border: none; border-radius: 12px;
            font-size: 15px; font-weight: bold;
        }}
        #sendButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['primary_dark']}, stop:1 {c['primary']});
        }}
        #sendButton:pressed {{ background-color: {c['primary_dark']}; }}
        #voiceButton {{
            background-color: {c['input_bg']}; color: {c['primary']};
            border: 2px solid {c['border']}; border-radius: 12px;
            font-size: 22px;
        }}
        #voiceButton:hover {{
            background-color: {c['button_hover']};
            border: 2px solid {c['primary']};
        }}
        #voiceButtonActive {{
            background-color: {c['error']}; color: {c['text']};
            border: 2px solid {c['error']}; border-radius: 12px;
            font-size: 22px;
        }}

        /* ═══════ MUSIC PANEL ═══════ */
        #musicPanel {{
            background-color: {c['background']};
            border-left: 2px solid {c['border']};
        }}
        #albumArt {{
            border: 2px solid {c['primary']}; border-radius: 12px;
        }}
        #nowPlayingFrame {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['secondary']}, stop:1 {c['secondary_dark']});
            border-radius: 12px; padding: 16px; margin: 10px;
            border: 1px solid {c['border']};
        }}
        #sectionTitle {{
            color: {c['primary']}; font-size: 16px;
            font-weight: bold; margin-bottom: 10px; letter-spacing: 1px;
        }}
        #trackLabel {{
            color: {c['text']}; font-size: 16px; font-weight: bold;
        }}
        #artistLabel {{ color: {c['text_secondary']}; font-size: 13px; }}
        #timeLabel {{ color: {c['text_dim']}; font-size: 11px; }}

        /* ═══════ PROGRESS BAR ═══════ */
        #progressBar {{ background: transparent; }}
        #progressBar::groove:horizontal {{
            background: {c['border']}; height: 4px; border-radius: 2px;
        }}
        #progressBar::chunk:horizontal {{
            background: {c['primary']}; border-radius: 2px;
        }}

        /* ═══════ CONTROL BUTTONS ═══════ */
        #controlButton {{
            background-color: {c['input_bg']}; color: {c['primary']};
            border: 1px solid {c['border']}; border-radius: 10px;
            font-size: 20px; min-width: 50px; min-height: 50px;
        }}
        #controlButton:hover {{
            background-color: {c['button_hover']};
            border: 1px solid {c['primary']};
        }}
        #controlButton:pressed {{
            background-color: {c['primary']}; color: {c['background']};
        }}
        #playButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['primary']}, stop:1 {c['primary_dark']});
            color: {c['text']}; border: none; border-radius: 10px;
            font-size: 22px; min-width: 60px; min-height: 50px;
        }}
        #playButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['primary_dark']}, stop:1 {c['primary']});
        }}
        #muteButton {{
            background-color: {c['input_bg']}; color: {c['primary']};
            border: 1px solid {c['border']}; border-radius: 8px;
            font-size: 18px; min-width: 40px; min-height: 30px;
        }}
        #muteButton:hover {{ background-color: {c['button_hover']}; }}

        /* ═══════ VOLUME SLIDER ═══════ */
        #volumeSlider {{ background: transparent; }}
        #volumeSlider::groove:horizontal {{
            background: {c['border']}; height: 6px; border-radius: 3px;
        }}
        #volumeSlider::handle:horizontal {{
            background: {c['primary']}; width: 18px; height: 18px;
            margin: -6px 0; border-radius: 9px;
        }}
        #volumeSlider::handle:horizontal:hover {{
            background: {c['primary_dark']}; width: 20px; height: 20px;
        }}
        #volumeLabel {{
            color: {c['primary']}; font-size: 12px;
            min-width: 45px; font-weight: bold;
        }}

        /* ═══════ MOOD BUTTONS ═══════ */
        #moodButton {{
            background-color: {c['secondary']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 10px;
            padding: 14px; font-size: 13px; min-height: 48px; font-weight: 500;
        }}
        #moodButton:hover {{
            background-color: {c['secondary_dark']};
            border: 1px solid {c['primary']};
        }}
        #moodButton:pressed {{
            background-color: {c['primary']}; color: {c['background']};
        }}

        /* ═══════ PLAYLIST ═══════ */
        #playlistWidget {{
            background-color: {c['input_bg']}; border: 1px solid {c['border']};
            border-radius: 8px; padding: 5px; color: {c['text']};
        }}
        #playlistWidget::item {{ padding: 8px; border-radius: 6px; }}
        #playlistWidget::item:hover {{ background-color: {c['button_hover']}; }}
        #playlistWidget::item:selected {{
            background-color: {c['primary']}; color: {c['background']};
        }}

        /* ═══════ DIALOGS / LABELS ═══════ */
        QDialog {{ background-color: {c['surface']}; }}
        QLabel {{ color: {c['text']}; }}
        QPushButton {{
            background-color: {c['primary']}; color: {c['text']};
            border: none; border-radius: 8px; padding: 10px 20px;
            font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {c['primary_dark']}; }}
        QPushButton:pressed {{ background-color: {c['secondary']}; }}
        QLineEdit {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 6px;
            padding: 8px; font-size: 14px;
        }}
        QLineEdit:focus {{ border: 2px solid {c['primary']}; }}
        QTextEdit {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 6px;
            padding: 8px; font-size: 14px;
        }}
        QTextEdit:focus {{ border: 2px solid {c['primary']}; }}
        QListWidget {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 6px;
        }}
        QListWidget::item:hover {{ background-color: {c['button_hover']}; }}
        QListWidget::item:selected {{ background-color: {c['primary']}; }}
        QComboBox {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 6px; padding: 8px;
        }}
        QComboBox:hover {{ border: 1px solid {c['primary']}; }}
        QComboBox::drop-down {{ border: none; }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {c['primary']};
        }}

        /* ═══════ TOOLTIPS ═══════ */
        QToolTip {{
            background-color: {c['surface_elevated']}; color: {c['text']};
            border: 1px solid {c['primary']}; border-radius: 6px;
            padding: 6px; font-size: 12px;
        }}

        /* ═══════ MENU ═══════ */
        QMenu {{
            background-color: {c['surface_elevated']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 8px; padding: 5px;
        }}
        QMenu::item {{ padding: 8px 25px; border-radius: 6px; }}
        QMenu::item:selected {{
            background-color: {c['primary']}; color: {c['background']};
        }}

        /* ═══════ CODE BLOCKS ═══════ */
        #codeBlock {{
            background-color: {c['background']}; color: {c['accent']};
            border: 1px solid {c['border']};
            border-left: 4px solid {c['primary']};
            border-radius: 6px; padding: 12px;
            font-family: "Consolas", "Monaco", monospace; font-size: 13px;
        }}

        /* ═══════ TABS ═══════ */
        QTabWidget::pane {{
            border: 1px solid {c['border']}; border-radius: 6px;
            background-color: {c['surface']};
        }}
        QTabBar::tab {{
            background-color: {c['surface_elevated']}; color: {c['text_secondary']};
            border: 1px solid {c['border']}; padding: 8px 16px;
            border-top-left-radius: 6px; border-top-right-radius: 6px;
        }}
        QTabBar::tab:selected {{
            background-color: {c['secondary']}; color: {c['primary']};
            border-bottom-color: {c['primary']};
        }}

        /* ═══════ SLIDERS (generic) ═══════ */
        QSlider::groove:horizontal {{
            background: {c['border']}; height: 6px; border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {c['primary']}; width: 16px; height: 16px;
            margin: -5px 0; border-radius: 8px;
        }}
        QSlider::sub-page:horizontal {{
            background: {c['primary']}; border-radius: 3px;
        }}

        /* ═══════ CHECKBOXES ═══════ */
        QCheckBox {{ color: {c['text']}; spacing: 8px; }}
        QCheckBox::indicator {{
            width: 18px; height: 18px; border-radius: 4px;
            border: 2px solid {c['border']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c['primary']}; border-color: {c['primary']};
        }}

        /* ═══════ GROUPBOX — BUG-11 ═══════ */
        QGroupBox {{
            color: {c['text']}; font-size: 13px; font-weight: bold;
            border: 1px solid {c['border']}; border-radius: 8px;
            margin-top: 16px; padding-top: 12px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 0 8px; color: {c['primary']}; left: 12px;
        }}

        /* ═══════ SIDEBAR ═══════ */
        #sidebar {{
            background-color: {c['secondary']};
            border-right: 1px solid {c['border']};
        }}
        #sidebarButton {{
            background-color: transparent; color: {c['primary']};
            border: 1px solid transparent; border-radius: 12px;
            font-size: 20px;
        }}
        #sidebarButton:hover {{
            background-color: {c['surface_elevated']};
            border: 1px solid {c['border']};
        }}
        #sidebarButton:pressed {{
            background-color: {c['primary']}; color: {c['background']};
        }}

        /* ═══════ SEARCH BAR ═══════ */
        #searchBar {{
            background-color: {c['surface']};
            border-bottom: 1px solid {c['border']};
        }}
        #searchInput {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 16px;
            padding: 4px 14px; font-size: 13px;
        }}
        #searchInput:focus {{ border: 1px solid {c['primary']}; }}

        /* ═══════ MOOD BADGE ═══════ */
        #moodBadge {{ background: transparent; border: none; }}

        /* ═══════ REACT BUTTON ═══════ */
        #reactButton {{
            background: rgba(255,255,255,0.05); color: {c['text_dim']};
            border: 1px solid {c['border']}; border-radius: 9px;
            font-size: 10px; padding: 0;
        }}
        #reactionLabel {{ font-size: 15px; }}

        /* ═══════ SPINBOXES ═══════ */
        QSpinBox {{
            background-color: {c['input_bg']}; color: {c['text']};
            border: 1px solid {c['border']}; border-radius: 6px;
            padding: 4px 8px;
        }}
        """


# ═══════════════════════════════════════════════════════════════════════════════
# ThemeCreatorDialog — design your own theme
# ═══════════════════════════════════════════════════════════════════════════════

class ThemeCreatorDialog(QDialog):
    """Dialog with colour pickers for every token — live preview + save."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.color_inputs: dict[str, QLineEdit] = {}
        self._build()

    def _build(self):
        self.setWindowTitle("🎨 Create Custom Theme")
        self.setFixedSize(620, 720)

        layout = QVBoxLayout()

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Theme Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Awesome Theme")
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # Scrollable colour pickers
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout()

        groups = {
            "Background":  ["background", "surface", "surface_elevated"],
            "Primary":     ["primary", "primary_dark", "accent"],
            "Secondary":   ["secondary", "secondary_dark"],
            "Text":        ["text", "text_secondary", "text_dim"],
            "Borders":     ["border", "border_light"],
            "Bubbles":     ["user_bubble", "user_bubble_end",
                            "makima_bubble", "makima_bubble_border"],
            "Input":       ["input_bg", "button_hover"],
            "Status":      ["error", "warning", "success"],
        }

        for group_name, keys in groups.items():
            lbl = QLabel(f"📌 {group_name}")
            lbl.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
            inner_layout.addWidget(lbl)
            for key in keys:
                row = QHBoxLayout()
                kl = QLabel(key.replace("_", " ").title() + ":")
                kl.setFixedWidth(180)
                row.addWidget(kl)

                inp = QLineEdit("#000000")
                inp.setFixedWidth(100)
                self.color_inputs[key] = inp
                row.addWidget(inp)

                pick = QPushButton("Pick")
                pick.setFixedWidth(60)
                pick.clicked.connect(lambda _, k=key: self._pick(k))
                row.addWidget(pick)

                swatch = QLabel()
                swatch.setFixedSize(36, 28)
                swatch.setStyleSheet(
                    "background-color: #000; border: 1px solid #666; border-radius: 4px;"
                )
                inp.textChanged.connect(
                    lambda _, s=swatch, k=key: self._update_swatch(k, s)
                )
                row.addWidget(swatch)
                row.addStretch()
                inner_layout.addLayout(row)

        inner.setLayout(inner_layout)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._preview)
        save_btn = QPushButton("Save Theme")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _pick(self, key: str):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.color_inputs[key].setText(color.name())

    def _update_swatch(self, key: str, swatch: QLabel):
        val = self.color_inputs[key].text()
        try:
            swatch.setStyleSheet(
                f"background-color: {val}; border: 1px solid #666; border-radius: 4px;"
            )
        except Exception:
            pass

    def _get_data(self) -> dict:
        return {
            "name": self.name_input.text() or "Custom Theme",
            "colors": {k: v.text() for k, v in self.color_inputs.items()},
        }

    def _preview(self):
        data = self._get_data()
        qss = self.theme_manager.generate_stylesheet(data)
        if self.parent():
            self.parent().setStyleSheet(qss)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a theme name!")
            return
        self.theme_manager.save_custom_theme(name, self._get_data())
        QMessageBox.information(self, "Success", f"Theme '{name}' saved!")
        self.accept()
