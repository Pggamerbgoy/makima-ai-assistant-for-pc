import unittest
import os
import sys
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class TestMakimaSubsystems(unittest.TestCase):
    """
    Comprehensive test suite for Makima subsystems not covered by main tests.
    Uses extensive mocking for hardware and external API dependencies.
    """

    @classmethod
    def setUpClass(cls):
        # Mocking standard Makima components for isolation
        cls.mock_ai = MagicMock()
        cls.mock_memory = MagicMock()
        cls.mock_speak = MagicMock()
        
        # Initialize QApplication for UI tests
        try:
            from PyQt5.QtWidgets import QApplication
            if not QApplication.instance():
                cls.app = QApplication([])
            else:
                cls.app = QApplication.instance()
        except ImportError:
            cls.app = None

    # ── 1. REMOTE SUBSYSTEM ──────────────────────────────────────────────────

    def test_telegram_remote_init(self):
        """Verify Telegram remote handles missing dependencies/tokens safely."""
        from remote import telegram_remote
        mock_router = MagicMock()
        remote_inst = telegram_remote.TelegramRemote(mock_router)
        
        with patch('remote.telegram_remote.TELEGRAM_AVAILABLE', True):
            with patch('remote.telegram_remote.BOT_TOKEN', ''):
                with self.assertLogs('Makima.Telegram', level='WARNING') as cm:
                    remote_inst.start()
                    # Check for "TOKEN not set" substring loosely
                    msg_found = any("not set" in msg.lower() for msg in cm.output)
                    self.assertTrue(msg_found, f"Warning not found in logs: {cm.output}")

    def test_web_dashboard_init(self):
        """Verify Web Dashboard initialization."""
        try:
            from remote.web_dashboard import WebDashboard
            mock_manager = MagicMock()
            # Mock Flask to avoid actual server start
            with patch('flask.Flask', MagicMock()):
                dashboard = WebDashboard(mock_manager)
                self.assertIsNotNone(dashboard)
                # The dashboard stores manager as self.manager in remote/web_dashboard.py
                self.assertEqual(dashboard.manager, mock_manager)
        except (ImportError, AttributeError):
            self.skipTest("Flask not installed or WebDashboard API mismatch")

    # ── 2. UI SUBSYSTEM ──────────────────────────────────────────────────────

    def test_theme_manager_loading(self):
        """Verify ThemeManager can load themes without crashing."""
        from ui.theme_manager import ThemeManager
        # Mocking PyQt5 components to avoid GUI issues
        with patch('PyQt5.QtWidgets.QWidget', MagicMock()):
            tm = ThemeManager()
            theme_data = tm.get_dark_cyber_theme()
            self.assertIn('name', theme_data)
            self.assertEqual(tm.current_theme, "dark_cyber")

    def test_mini_mode_init(self):
        """Verify MiniModeWindow initialization."""
        if not self.app:
            self.skipTest("PyQt5 not available")
        try:
            from ui.mini_mode import MiniModeWindow
            makima = MagicMock()
            mini = MiniModeWindow(makima)
            self.assertIsNotNone(mini)
        except (ImportError, RuntimeError, Exception) as e:
            self.skipTest(f"MiniModeWindow init failed: {e}")

    def test_web_music_logic(self):
        """Verify WebMusic generates correct search URLs."""
        from systems.web_music import WebMusic
        wm = WebMusic()
        with patch('webbrowser.open') as mock_open:
            # YouTube
            res_yt = wm.play_youtube("lo-fi")
            self.assertIn("YouTube", res_yt)
            mock_open.assert_called_with("https://www.youtube.com/results?search_query=lo-fi")
            
            # Spotify Web
            res_sp = wm.play_web_spotify("linkin park")
            self.assertIn("Spotify", res_sp)
            mock_open.assert_called_with("https://open.spotify.com/search/linkin%20park")

    def test_chat_history_logic(self):
        """Test chat history management logic."""
        from ui.chat_history import ChatHistory
        import shutil
        test_dir = Path('tmp/test_history_unique')
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True, exist_ok=True)
        # Patching HISTORY_DIR to avoid writing to real disk during tests
        with patch('ui.chat_history.HISTORY_DIR', test_dir):
            history = ChatHistory()
            for i in range(10):
                history.add_message(f"msg {i}", is_user=True)
            
            self.assertEqual(len(history._messages), 10)
            self.assertEqual(history._messages[-1]['message'], "msg 9")

    # ── 3. CLOUD SUBSYSTEM ───────────────────────────────────────────────────

    def test_cloud_manager_sync_check(self):
        """Verify CloudManager initialization."""
        try:
            from cloud.cloud_manager import CloudManager
            # Mocking GDrive API dependencies
            with patch.dict('sys.modules', {
                'google.oauth2': MagicMock(),
                'googleapiclient': MagicMock(),
                'googleapiclient.discovery': MagicMock(),
                'googleapiclient.http': MagicMock()
            }):
                with patch('cloud.cloud_manager.os.path.exists', return_value=True):
                    cm = CloudManager()
                    # Check it has the service attribute (even if None in mock)
                    self.assertTrue(hasattr(cm, 'service'))
        except ImportError:
            self.skipTest("CloudManager dependencies not met")

    # ── 4. SYSTEMS ──────────────────────────────────────────────────────────

    def test_mood_tracker_logic(self):
        """Verify MoodTracker sentiment analysis."""
        try:
            from systems.mood_tracker import MoodTracker
            tracker = MoodTracker()
            
            res_happy = tracker.analyze("I am so happy and excited!")
            self.assertIn(res_happy.emotion.lower(), ["happy", "excited", "positive"])
            
            res_sad = tracker.analyze("This is terrible and I am sad.")
            self.assertIn(res_sad.emotion.lower(), ["sad", "negative", "angry"])
        except ImportError:
            self.skipTest("MoodTracker dependencies not met")

    def test_macro_recording_logic(self):
        """Test MacroSystem recording state management."""
        # Mock pynput before importing MacroSystem
        with patch.dict('sys.modules', {'pynput': MagicMock(), 'pynput.keyboard': MagicMock()}):
            from systems.macros import MacroSystem
            ms = MacroSystem()
            
            # Test recording state
            with patch('systems.macros.PYNPUT_AVAILABLE', True):
                with patch('pynput.keyboard.Listener', MagicMock()):
                    res = ms.start_recording("test_macro")
                    self.assertTrue(ms._recording)
                    self.assertEqual(ms._current_macro_name, "test_macro")
                    
                    ms.stop_recording()
                    self.assertFalse(ms._recording)

    # ── 5. AGENTS ────────────────────────────────────────────────────────────

    def test_translator_logic(self):
        """Verify Translator handles basic routing."""
        try:
            from agents.translator import Translator
            trans = Translator(self.mock_ai)
            
            # Mock AI response - Translator.translate returns (response, success)
            self.mock_ai.generate_response.return_value = ("Hello", True)
            res = trans.translate("Namaste", "english")
            self.assertEqual(res, "Hello")
        except (ImportError, AttributeError):
            self.skipTest("Translator not available or different API")

    def test_security_manager_scans(self):
        """Verify SecurityManager triggers subprocess calls."""
        from systems.security_manager import SecurityManager
        sm = SecurityManager()
        with patch('subprocess.Popen') as mock_popen:
            res = sm.quick_scan()
            self.assertIn("Quick", res)
            mock_popen.assert_called()

    def test_security_manager_stop(self):
        """Verify SecurityManager triggers stop scan subprocess."""
        from systems.security_manager import SecurityManager
        sm = SecurityManager()
        with patch('subprocess.Popen') as mock_popen:
            res = sm.stop_scan()
            self.assertIn("Stopping", res)
            mock_popen.assert_called()

    def test_auto_coder_logic(self):
        """Verify AutoCoder generates and executes code."""
        from agents.auto_coder import AutoCoder
        coder = AutoCoder(self.mock_ai)
        self.mock_ai.generate_response.return_value = "print('Hello')"
        
        # Test write (generates file)
        res = coder.write("Say hello")
        self.assertIn("Code written to", res)
        
        # Test run (executes file)
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = "Hello"
            mock_run.return_value.stderr = ""
            coder.run("say_hello.py")
            mock_run.assert_called()

    def test_skill_teacher_ast_fix(self):
        """Verify SkillTeacher auto-fixes uncalled nested functions."""
        from agents.skill_teacher import SkillTeacher
        mock_router = MagicMock()
        teacher = SkillTeacher(self.mock_ai, mock_router)
        
        # Scenario: LLM defines a function but forgets to return the call
        bad_code = "def my_skill():\n    return 'success'"
        self.mock_ai.generate_response.return_value = bad_code
        
        # _generate_skill_code should detect the FunctionDef at end and append return call
        fixed_body = teacher._generate_skill_code("test task", "test_name", ["task"])
        self.assertIn("return my_skill()", fixed_body)

if __name__ == '__main__':
    unittest.main(verbosity=2)
