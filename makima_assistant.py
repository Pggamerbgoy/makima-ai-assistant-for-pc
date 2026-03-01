"""
Makima AI Assistant - Main Entry Point
Bilingual (English/Hindi) voice assistant with self-learning, memory, and multi-backend AI.
"""

import os
import sys
import time
import threading
import queue
import logging
from datetime import datetime

# Load .env before anything else reads os.getenv()
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

from core.tts_engine import get_tts
from core.mishearing import correct_mishearings

# Setup logging
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('makima.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Makima")

# Attempt optional imports gracefully
try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False
    logger.warning("speech_recognition not installed. Voice input disabled.")

from core.ai_handler import AIHandler
from core.eternal_memory import EternalMemory
from core.command_router import CommandRouter
from agents.skill_teacher import SkillTeacher
from agents.app_learner import AppLearner
from systems.media_observer import MediaObserver
from systems.battery_monitor import BatteryMonitor
from systems.clipboard_monitor import ClipboardMonitor
from systems.overlay import Overlay
from remote.web_dashboard import WebDashboard
try:
    from makima_tools.tool_registry import ToolRegistry
except ImportError:
    ToolRegistry = None

try:
    from ui.hud import MakimaHUD
    HUD_AVAILABLE = True
except Exception:
    HUD_AVAILABLE = False
    logger.warning("HUD unavailable (tkinter missing?). Running headless.")


# Mishearing corrections are handled by core.mishearing — imported above.

WAKE_WORDS = ["hey makima", "makima", "hey ma kima"]


class MakimaAssistant:
    """Core class orchestrating all Makima subsystems."""

    def __init__(self, text_mode: bool = False, ui_mode: bool = False):
        self.text_mode = text_mode
        self.ui_mode = ui_mode
        self.running = False
        self.command_queue = queue.Queue()

        logger.info("🌸 Initializing Makima...")

        from core.makima_manager import MakimaManager

        # 1. Central Manager
        self.manager = MakimaManager(speak_fn=self.speak, text_mode=text_mode)
        self.manager.on("on_response", lambda response, **kw: self._hud("speaking", "neutral", response))
        self.manager.on("on_command",  lambda command, **kw: self._hud("thinking", "focused", command))
        
        # Keep aliased references for backward compatibility
        self.memory = self.manager._memory
        self.ai = self.manager._ai
        self.v4 = self.manager.agents._v4
        self.router = self.manager.agents._router
        self.tools = self.manager.tools._registry
        
        # App learner — auto-teaches Makima about newly opened apps
        try:
            from agents.app_learner import AppLearner
            self.app_learner = AppLearner(ai=self.ai, speak_callback=self.speak)
            self.router.app_learner = self.app_learner
        except Exception as e:
            logger.warning(f"AppLearner init failed: {e}")
            self.app_learner = None

        # Start manager
        self.manager.start()

        # TTS engine — Edge Neural (or pyttsx3 fallback)
        self.tts_engine = get_tts()

        # Speech recognizer
        self.recognizer = None
        self.microphone = None
        if SPEECH_AVAILABLE and not text_mode:
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    logger.info("🎙️ Calibrating microphone for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=2)
                logger.info("✅ Microphone ready.")
            except Exception as e:
                logger.warning(f"Microphone unavailable: {e}")
                self.microphone = None

        # Background monitors (non-blocking)
        self.monitors = []
        self._start_monitors()

        # HUD — animated avatar overlay
        self.hud = None
        if HUD_AVAILABLE:
            try:
                self.hud = MakimaHUD()
                logger.info("🖥️  HUD started.")
            except Exception as e:
                logger.warning(f"HUD init failed: {e}")

        # React/Web Dashboard
        try:
            self.dashboard = WebDashboard(self)
            self.dashboard.start_in_thread()
        except Exception as e:
            logger.warning(f"Failed to start Web Dashboard: {e}")

        # Music DJ — lazy init, available for Chat UI
        self._music_dj = None

        logger.info("✅ Makima is ready!")
        self._hud("idle", "neutral", "")
        if not ui_mode:
            self.speak("Hey! Makima here. How can I help you?")

    # ─── HUD Helper ───────────────────────────────────────────────────────────

    def _hud(self, status: str = None, emotion: str = None, text: str = None):
        """Thread-safe HUD update — silently no-ops if HUD is unavailable."""
        if self.hud:
            try:
                self.hud.update_all(status=status, emotion=emotion, text=text)
            except Exception:
                pass

    # ─── TTS ──────────────────────────────────────────────────────────────────

    def speak(self, text: str, lang: str = "en", emotion: str = "neutral"):
        """Convert text to speech via the active TTS engine."""
        print(f"\n🌸 Makima: {text}")
        self._hud("speaking", emotion, text)
        if self.tts_engine:
            self.tts_engine.speak(text, lang=lang)
        self._hud("idle")

    # ─── Voice Recognition ────────────────────────────────────────────────────

    def _correct_mishearing(self, text: str) -> str:
        """Fix common speech recognition errors via the mishearing module."""
        return correct_mishearings(text)

    def _contains_wake_word(self, text: str) -> bool:
        return any(ww in text.lower() for ww in WAKE_WORDS)

    def listen_once(self) -> str | None:
        """Listen for a single utterance and return text."""
        if not self.recognizer or not self.microphone:
            return None
        self._hud("listening")
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            self._hud("thinking")
            text = self.recognizer.recognize_google(audio, language='en-IN')
            return self._correct_mishearing(text)
        except sr.WaitTimeoutError:
            self._hud("idle")
            return None
        except sr.UnknownValueError:
            self._hud("idle")
            return None
        except sr.RequestError as e:
            logger.warning(f"Speech API error: {e}")
            self._hud("error")
            return None

    # ─── Command Processing ───────────────────────────────────────────────────

    def is_complex_command(self, command: str) -> bool:
        """Determines if the command should be passed to the V4 Agent Swarm."""
        complex_keywords = ['and then', 'also', 'research', 'write', 'analyze', 'compare']
        return any(kw in command.lower() for kw in complex_keywords)

    def process_input(self, user_input: str):
        """Route user input through the central MakimaManager."""
        user_input = user_input.strip()
        if not user_input:
            return

        response = self.manager.handle(user_input, source="voice" if not self.text_mode else "text")

        if response:
            if getattr(self, "memory", None):
                self.memory.save_conversation("makima", response)
            
            # Detect language hint from Devanagari characters
            lang = "hi" if any("\u0900" <= ch <= "\u097f" for ch in response) else "en"
            self.speak(response, lang=lang)
            return response
        return None

    # ─── Background Monitors ──────────────────────────────────────────────────

    def _start_monitors(self):
        """Start all background monitoring threads."""
        
        # Wrap callbacks to inject context back into manager
        def battery_cb(msg, percent=None):
            self.speak(msg)
            if percent is not None:
                self.manager.update_context(battery_percent=percent)
                
        def media_cb(app):
            self.manager.update_context(active_app=app)
            
        monitors = [
            BatteryMonitor(callback=battery_cb),
            ClipboardMonitor(callback=self.speak),
            MediaObserver(callback=media_cb),
        ]
        for monitor in monitors:
            t = threading.Thread(target=monitor.run, daemon=True)
            t.start()
            self.monitors.append(monitor)
        logger.info(f"🔄 Started {len(monitors)} background monitors.")

    # ─── Main Loop ────────────────────────────────────────────────────────────

    def run_voice_loop(self):
        """Continuous voice listening loop with wake word detection."""
        self.running = True
        logger.info("🎙️ Voice loop started. Listening for wake word...")
        print("\n👂 Say 'Hey Makima' to activate...\n")

        while self.running:
            text = self.listen_once()
            if not text:
                continue

            if self._contains_wake_word(text):
                self.speak("Yes?")
                # Listen for the actual command (extended timeout after wake word)
                command = self.listen_once()
                if command:
                    self.process_input(command)
                else:
                    self.speak("I'm listening — say your command.")
            else:
                # If already a full command without wake word (e.g., in active session)
                pass

    def run_text_loop(self):
        """Text-based interaction loop for testing without microphone."""
        self.running = True
        print("\n💬 Text mode active. Type your commands (or 'quit' to exit).\n")

        while self.running:
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ("quit", "exit", "bye"):
                    self.speak("Goodbye!")
                    self.running = False
                    break
                self.process_input(user_input)
            except (KeyboardInterrupt, EOFError):
                self.speak("Shutting down. Bye!")
                self.running = False
                break

    def run_ui(self):
        """Launch the full PyQt5 Chat Interface."""
        try:
            from ui.chat_interface import launch_ui
            logger.info("🖥️  Launching Chat Interface UI...")
            launch_ui(self)  # blocks until window is closed
        except ImportError as e:
            logger.error(f"Could not launch UI: {e}")
            print(f"\n❌ UI requires PyQt5. Install with: pip install PyQt5")
            print("Falling back to text mode...\n")
            self.run_text_loop()

    def run(self):
        """Start Makima in UI, voice, or text mode."""
        if self.ui_mode:
            self.run_ui()
        elif self.text_mode or not self.microphone:
            self.run_text_loop()
        else:
            # Run voice loop in main thread, keep monitors alive
            try:
                self.run_voice_loop()
            except KeyboardInterrupt:
                self.speak("Shutting down. Bye!")
                self.running = False


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Makima AI Assistant")
    parser.add_argument("--text", action="store_true",
                        help="Run in text mode (no microphone)")
    parser.add_argument("--ui", action="store_true",
                        help="Launch the PyQt5 desktop Chat Interface")
    args = parser.parse_args()

    makima = MakimaAssistant(text_mode=args.text, ui_mode=args.ui)
    makima.run()
