"""
core/command_router.py
Routes user input to the correct handler/system based on intent matching.
Falls back to the AI for open-ended conversation.
"""

import re
import logging
from typing import Optional, Callable

logger = logging.getLogger("Makima.Router")


class CommandRouter:
    """
    Intent-based command router.
    Priority order: built-in patterns → learned skills → AI chat
    """

    def __init__(self, ai, memory):
        self.ai = ai
        self.memory = memory
        self.skill_teacher = None  # Injected after init to avoid circular dep































































































































        # System attributes (placeholders for extension logic)
        self._services = None
        self._calendar = None
        self._prefs = None
        self._email = None
        self._music_dj = None
        self._quantum_simulator = None

        # Lazy-load system handlers to avoid import errors if deps missing
        self._handlers: dict[str, Callable] = {}
        self._build_handlers()

    # ─── Handler Registration ─────────────────────────────────────────────────

    def _build_handlers(self):
        """Register all built-in command handlers."""
        # Import here to allow graceful failures
        try:
            from systems.app_control import AppControl
            self._app = AppControl()
        except Exception as e:
            logger.warning(f"AppControl unavailable: {e}")
            self._app = None

        try:
            from systems.spotify_control import SpotifyControl
            self._spotify = SpotifyControl()
        except Exception as e:
            logger.warning(f"SpotifyControl unavailable: {e}")
            self._spotify = None

        try:
            from systems.system_commands import SystemCommands
            self._sys = SystemCommands()
        except Exception as e:
            logger.warning(f"SystemCommands unavailable: {e}")
            self._sys = None

        try:
            from systems.focus_mode import FocusMode
            self._focus = FocusMode()
        except Exception as e:
            logger.warning(f"FocusMode unavailable: {e}")
            self._focus = None

        try:
            from systems.macros import MacroSystem
            self._macros = MacroSystem()
        except Exception as e:
            logger.warning(f"MacroSystem unavailable: {e}")
            self._macros = None

        try:
            from systems.reminder import ReminderSystem
            self._reminders = ReminderSystem(callback=None)  # callback set later
        except Exception as e:
            logger.warning(f"ReminderSystem unavailable: {e}")
            self._reminders = None

        try:
            from agents.web_agent import WebAgent
            self._web = WebAgent(ai=self.ai)
        except Exception as e:
            logger.warning(f"WebAgent unavailable: {e}")
            self._web = None

        try:
            from agents.auto_coder import AutoCoder
            self._coder = AutoCoder(ai=self.ai)
        except Exception as e:
            logger.warning(f"AutoCoder unavailable: {e}")
            self._coder = None

        try:
            from cloud.cloud_manager import CloudManager
            self._cloud = CloudManager()
        except Exception as e:
            logger.warning(f"CloudManager unavailable: {e}")
            self._cloud = None

        try:
            from systems.security_manager import SecurityManager
            self._security = SecurityManager()
        except Exception as e:
            logger.warning(f"SecurityManager unavailable: {e}")
            self._security = None

        try:
            from systems.media_observer import MediaObserver
            self._media_obs = MediaObserver()
        except Exception as e:
            logger.warning(f"MediaObserver unavailable: {e}")
            self._media_obs = None
        # Self-updater (optional — lets Makima modify her own code in a controlled way)
        try:
            from systems.self_updater import SelfUpdater
            self._self_updater = SelfUpdater(ai_handler=self.ai)
        except Exception as e:
            logger.warning(f"SelfUpdater unavailable: {e}")
            self._self_updater = None

    # ─── Intent Patterns ──────────────────────────────────────────────────────

    # Pattern → (handler_method, needs_match_groups)
    PATTERNS = [
        # P3 FIX: YouTube patterns MUST come before open_app and generic play
        (r"play (.+?) on youtube",                      "_handle_yt_play_inline"),
        (r"play (.+?) youtube",                         "_handle_yt_play_inline"),
        (r"youtube (?:play|search for|search) (.+)",    "_handle_yt_play_inline"),
        (r"(?:pause|stop) youtube",                     "_handle_yt_pause_inline"),
        (r"(?:resume|continue) youtube",                "_handle_yt_resume_inline"),
        (r"(?:skip|next) (?:youtube|on youtube)",       "_handle_yt_skip_inline"),
        (r"what(?:'s| is) playing (?:on )?youtube",     "_handle_yt_now_inline"),

        # --- Advanced Features (V4) ---
        (r"quantum simulate investment of \$?([\d,]+) in (.+)", "_handle_qs_invest"),
        (r"quantum simulate job change", "_handle_qs_job"),
        (r"play (?:focus|lofi|chill|hype) (?:music|songs?)", "_handle_dj_play_mood"),
        (r"learn (?:the )?app (.+)", "_handle_learn_app"),
        (r"how (?:do i|to) (.+?) in (.+)", "_handle_howto_in_app"),
        (r"check (?:new )?emails?", "_handle_email_summary"),
        (r"set (?:my )?(?:default )?([a-zA-Z0-9_\-]+) to (.+)", "_handle_pref_set"),
        (r"(?:show|list) (?:my )?preferences", "_handle_pref_list"),
        (r"use (?:ollama|offline)", "_handle_use_ollama"),
        (r"use (?:gemini|online)", "_handle_use_gemini"),
        (r"(?:which|what) ai (?:are you using)?", "_handle_which_ai"),
        (r"background activity|what happened", "_handle_bg_activity"),

        # --- Classic Patterns ---
        # Memory
        (r"remember that (.+)", "_handle_remember"),
        (r"yaad rakh (.+)", "_handle_remember"),
        (r"do you remember (.+)", "_handle_recall"),
        (r"yaad hai (.+)", "_handle_recall"),
        (r"memory stats|kitni yaadein", "_handle_memory_stats"),

        # Persona
        (r"switch to (makima|normal|date) mode", "_handle_persona"),

        # Learning
        (r"learn how to (.+)", "_handle_learn"),
        (r"seekh (.+)", "_handle_learn"),

        # App control
        (r"(?:open|launch|start|kholo) (.+)", "_handle_open_app"),
        (r"(?:close|kill|band karo) (.+)", "_handle_close_app"),
        (r"scan apps", "_handle_scan_apps"),

        # Spotify / Media
        (r"play (?:music|song|spotify)", "_handle_spotify_play"),
        (r"pause (?:music|song|spotify)?", "_handle_spotify_pause"),
        (r"next (?:song|track)?", "_handle_spotify_next"),
        (r"previous (?:song|track)?", "_handle_spotify_prev"),
        (r"what was i listening to|last song", "_handle_last_media"),

        # Volume
        (r"\bvolume to (\d+)", "_handle_volume_set"),
        (r"\bvolume up", "_handle_volume_up"),
        (r"\bvolume down", "_handle_volume_down"),
        (r"\bunmute", "_handle_unmute"),
        (r"(?<!un)\bmute\b", "_handle_mute"),

        # System
        (r"lock (?:pc|computer|screen)?", "_handle_lock"),
        (r"screenshot|take screenshot", "_handle_screenshot"),
        (r"empty (?:recycle bin|trash)", "_handle_empty_trash"),
        (r"(?:maximize|maximise) window", "_handle_maximize"),
        (r"(?:minimize|minimise) window", "_handle_minimize"),
        (r"close window", "_handle_close_window"),
        (r"cpu usage", "_handle_cpu"),
        (r"ram usage|memory usage", "_handle_ram"),
        (r"battery (?:status|level)?", "_handle_battery"),

        # Focus mode
        (r"start focus|focus mode on", "_handle_focus_start"),
        (r"stop focus|focus mode off|end focus", "_handle_focus_stop"),

        # Macros
        (r"start recording macro (.+)", "_handle_macro_record"),
        (r"stop recording", "_handle_macro_stop"),
        (r"run macro (.+)", "_handle_macro_run"),

        # Reminders
        (r"remind me to (.+) at (.+)", "_handle_reminder"),

        # Security
        (r"quick scan", "_handle_quick_scan"),
        (r"full scan|deep scan", "_handle_full_scan"),
        (r"scan (?:my )?downloads", "_handle_scan_downloads"),

        # Cloud
        (r"sync (?:memory|brain) to cloud", "_handle_cloud_sync"),
        (r"upload (.+) to cloud", "_handle_cloud_upload"),

        # Web
        (r"search(?: for)? (.+)", "_handle_web_search"),
        (r"google (.+)", "_handle_web_search"),

        # Code
        (r"write code (?:to|for|that) (.+)", "_handle_write_code"),
        (r"run code (.+)", "_handle_run_code"),

        # Utilities
        (r"what time is it|time|samay", "_handle_time"),
        (r"what(?:'s| is) (?:today'?s? )?date|date today|aaj ki tarikh", "_handle_date"),
        (r"what day is it|day today", "_handle_day"),
        (r"good morning|good evening|good night", "_handle_greeting"),
        (r"how (?:am i|are you)|learning report", "_handle_report"),
        (r"clear (?:history|chat)", "_handle_clear_history"),
        (r"status|system status", "_handle_status"),
        # Self-update (explicit, file-scoped)
        (r"(?:update|modify|change) your code in ([\w\/\\\.\-]+) to (.+)", "_handle_self_update"),
    ]

    # ─── Route ────────────────────────────────────────────────────────────────

    def route(self, user_input: str) -> tuple[str, Optional[str]]:
        """Match input to a handler or fall back to AI chat."""
        text = user_input.lower().strip()

        for pattern, handler_name in self.PATTERNS:
            m = re.search(pattern, text)
            if m:
                handler = getattr(self, handler_name, None)
                if handler:
                    try:
                        res = handler(m)
                        return (str(res) if res else ""), handler_name
                    except Exception as e:
                        logger.error(f"Handler {handler_name} error: {e}")
                        return f"Something went wrong with that command.", handler_name

        # Check learned skills
        if self.skill_teacher:
            result = self.skill_teacher.try_run_skill(user_input)
            if result:
                return str(result), "learned_skill"

        # 3. Final Fallback: AI Chat
        if self.ai:
            try:
                # Check memory for a specific answer first
                memory_ctx = self.memory.build_memory_context(user_input)
                resp, _ = self.ai.chat(user_input, context=memory_ctx)
                return resp, "ai_chat"
            except Exception as e:
                logger.error(f"AI Chat error: {e}")
                resp, _ = self.ai.chat(user_input)
                return resp, "ai_chat"

        return "Command not recognized.", None

    # ─── Memory Handlers ──────────────────────────────────────────────────────

    def _handle_remember(self, m):
        text = m.group(1)
        # Use first 5 words as key
        key = " ".join(text.split()[:5])
        self.memory.remember(key, text)
        return f"Got it! I'll remember: {text}"

    def _handle_recall(self, m):
        query = m.group(1)
        note = self.memory.recall_note(query)
        if note:
            return f"Yes! I remember: {note}"
        results = self.memory.search_memories(query, top_k=2)
        if results:
            return "I found something related in my memory: " + results[0]
        return "Hmm, I don't seem to have any memory of that."

    def _handle_memory_stats(self, m):
        return self.memory.format_stats()

    # ─── Persona ──────────────────────────────────────────────────────────────

    def _handle_persona(self, m):
        return self.ai.set_persona(m.group(1))

    # ─── Skill Learning ───────────────────────────────────────────────────────

    def _handle_learn(self, m):
        if self.skill_teacher:
            task = m.group(1)
            return self.skill_teacher.teach(task)
        return "Skill teacher is not available right now."

    # ─── App Control ──────────────────────────────────────────────────────────

    def _handle_open_app(self, m):
        if self._app:
            return self._app.open(m.group(1))
        return "App control is not available."

    def _handle_close_app(self, m):
        if self._app:
            return self._app.close(m.group(1))
        return "App control is not available."

    def _handle_scan_apps(self, m):
        if self._app:
            return self._app.scan()
        return "App control is not available."

    # ─── Spotify ──────────────────────────────────────────────────────────────

    def _handle_spotify_play(self, m):
        if self._spotify:
            return self._spotify.play()
        return "Spotify control is not available."

    def _handle_spotify_pause(self, m):
        if self._spotify:
            return self._spotify.pause()
        return "Spotify control is not available."

    def _handle_spotify_next(self, m):
        if self._spotify:
            return self._spotify.next_track()
        return "Spotify control is not available."

    def _handle_spotify_prev(self, m):
        if self._spotify:
            return self._spotify.prev_track()
        return "Spotify control is not available."

    def _handle_last_media(self, m):
        if self._media_obs:
            return self._media_obs.get_last()
        return "Media observer is not available."

    # ─── Volume ───────────────────────────────────────────────────────────────

    def _handle_volume_set(self, m):
        if self._sys:
            return self._sys.set_volume(int(m.group(1)))
        return "System commands not available."

    def _handle_volume_up(self, m):
        if self._sys:
            return self._sys.volume_up()
        return "System commands not available."

    def _handle_volume_down(self, m):
        if self._sys:
            return self._sys.volume_down()
        return "System commands not available."

    def _handle_mute(self, m):
        if self._sys:
            return self._sys.mute()
        return "System commands not available."

    def _handle_unmute(self, m):
        if self._sys:
            return self._sys.unmute()
        return "System commands not available."

    # ─── System ───────────────────────────────────────────────────────────────

    def _handle_lock(self, m):
        if self._sys:
            return self._sys.lock_pc()
        return "System commands not available."

    def _handle_screenshot(self, m):
        if self._sys:
            return self._sys.screenshot()
        return "System commands not available."

    def _handle_empty_trash(self, m):
        if self._sys:
            return self._sys.empty_recycle_bin()
        return "System commands not available."

    def _handle_maximize(self, m):
        if self._sys:
            return self._sys.maximize_window()
        return "System commands not available."

    def _handle_minimize(self, m):
        if self._sys:
            return self._sys.minimize_window()
        return "System commands not available."

    def _handle_close_window(self, m):
        if self._sys:
            return self._sys.close_window()
        return "System commands not available."

    def _handle_cpu(self, m):
        if self._sys:
            return self._sys.cpu_usage()
        return "System commands not available."

    def _handle_ram(self, m):
        if self._sys:
            return self._sys.ram_usage()
        return "System commands not available."

    def _handle_battery(self, m):
        if self._sys:
            return self._sys.battery_status()
        return "System commands not available."

    # ─── Focus ────────────────────────────────────────────────────────────────

    def _handle_focus_start(self, m):
        if self._focus:
            return self._focus.start()
        return "Focus mode not available."

    def _handle_focus_stop(self, m):
        if self._focus:
            return self._focus.stop()
        return "Focus mode not available."

    # ─── Macros ───────────────────────────────────────────────────────────────

    def _handle_macro_record(self, m):
        if self._macros:
            return self._macros.start_recording(m.group(1))
        return "Macro system not available."

    def _handle_macro_stop(self, m):
        if self._macros:
            return self._macros.stop_recording()
        return "Macro system not available."

    def _handle_macro_run(self, m):
        if self._macros:
            return self._macros.run_macro(m.group(1))
        return "Macro system not available."

    # ─── Reminder ─────────────────────────────────────────────────────────────

    def _handle_reminder(self, m):
        if self._reminders:
            return self._reminders.add(task=m.group(1), time_str=m.group(2))
        return "Reminder system not available."

    # ─── Security ─────────────────────────────────────────────────────────────

    def _handle_quick_scan(self, m):
        if self._security:
            return self._security.quick_scan()
        return "Security manager not available."

    def _handle_full_scan(self, m):
        if self._security:
            return self._security.full_scan()
        return "Security manager not available."

    def _handle_scan_downloads(self, m):
        if self._security:
            return self._security.scan_downloads()
        return "Security manager not available."

    # ─── Cloud ────────────────────────────────────────────────────────────────

    def _handle_cloud_sync(self, m):
        if self._cloud:
            return self._cloud.sync_now()
        return "Cloud sync not available."

    def _handle_cloud_upload(self, m):
        if self._cloud:
            return self._cloud.upload(m.group(1))
        return "Cloud sync not available."

    # ─── Web ──────────────────────────────────────────────────────────────────

    def _handle_web_search(self, m):
        if self._web:
            return self._web.search(m.group(1))
        return self.ai.chat(f"Search the web for: {m.group(1)}")

    # ─── Code ─────────────────────────────────────────────────────────────────

    def _handle_write_code(self, m):
        if self._coder:
            return self._coder.write(m.group(1))
        return self.ai.chat(f"Write Python code to: {m.group(1)}")

    def _handle_run_code(self, m):
        if self._coder:
            return self._coder.run(m.group(1))
        return "Auto coder not available."

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _handle_time(self, m):
        from datetime import datetime
        return f"It's {datetime.now().strftime('%I:%M %p')}."

    def _handle_date(self, m):
        from datetime import datetime
        return f"Today is {datetime.now().strftime('%B %d, %Y')}."

    def _handle_day(self, m):
        from datetime import datetime
        return f"Today is {datetime.now().strftime('%A')}."

    def _handle_greeting(self, m):
        """P5 FIX: Morning → try briefing first, evening/night → direct reply."""
        greeting = m.group(0).lower()
        if "morning" in greeting:
            # Try to get a real daily briefing from MakimaManager if available
            try:
                from core.makima_manager import MakimaManager
                mgr = getattr(self, "_manager", None)
                if mgr and mgr.briefing:
                    return mgr.briefing.deliver(style="quick")
            except Exception:
                pass
            status = ""
            if self._sys:
                try:
                    status = f" Battery: {self._sys.battery_status()}."
                except Exception:
                    pass
            return f"Good morning! {status} Ready when you are.".strip()
        elif "evening" in greeting:
            return "Good evening. How was your day?"
        else:
            return "Good night. Rest well."

    def _handle_report(self, m):
        stats = self.memory.get_stats()
        return (
            f"You've had {stats['total_entries']} interactions with me, "
            f"and I have {stats['notes_count']} saved notes about you. "
            f"Keep it up!"
        )

    def _handle_clear_history(self, m):
        self.ai.clear_history()
        return "Conversation history cleared."

    def _handle_status(self, m):
        ai_status = self.ai.get_status()
        return (
            f"AI: {'Gemini' if ai_status['gemini_available'] else 'Ollama (offline)'}, "
            f"Persona: {ai_status['persona']}, "
            f"Memory: {self.memory.get_stats()['total_entries']} entries."
        )

    # ─── Self-update (Makima modifying her own code) ─────────────────────────

    def _handle_self_update(self, m):
        """
        Allow Makima to update one of her own files in a controlled way.

        Usage examples:
            "update your code in core/ai_handler.py to change the default model"
            "modify your code in systems/web_music.py to open playlists"

        The path is treated as relative to the project root, and a .bak
        backup is written before overwriting.
        """
        if not getattr(self, "_self_updater", None):
            return "Self-updater is not available on this install."

        file_path = m.group(1).strip()
        instruction = m.group(2).strip()
        if not file_path or not instruction:
            return "Tell me which file and what change you want. For example: 'update your code in core/ai_handler.py to change the default model.'"

        return self._self_updater.update_file(file_path, instruction)

    # ─── Advanced Handlers (Added from V4) ──────────────────────────────────

    # P3 FIX: YouTube inline handlers (delegated to YouTubePlayer)
    def _get_yt(self):
        if not hasattr(self, "_yt_player") or self._yt_player is None:
            try:
                from systems.youtube_player import get_youtube_player
                self._yt_player = get_youtube_player()
            except Exception:
                self._yt_player = None
        return self._yt_player

    def _handle_yt_play_inline(self, m):
        query = m.group(1).strip() if m.lastindex else ""
        if not query:
            return "What do you want me to play on YouTube?"
        yt = self._get_yt()
        if not yt or not yt.available:
            return "YouTube player needs yt-dlp. Run: pip install yt-dlp python-vlc"
        import threading
        result = [None]
        def _go(): result[0] = yt.play(query)
        t = threading.Thread(target=_go, daemon=True)
        t.start(); t.join(timeout=15)
        return result[0] or f"🎵 Loading '{query}' from YouTube..."

    def _handle_yt_pause_inline(self, m):
        yt = self._get_yt()
        return yt.pause() if yt else "YouTube player not available."

    def _handle_yt_resume_inline(self, m):
        yt = self._get_yt()
        return yt.resume() if yt else "YouTube player not available."

    def _handle_yt_skip_inline(self, m):
        yt = self._get_yt()
        return yt.skip() if yt else "YouTube player not available."

    def _handle_yt_now_inline(self, m):
        yt = self._get_yt()
        return yt.now_playing() if yt else "YouTube player not available."

    def _get_dj(self):
        if self._music_dj: return self._music_dj
        try:
            from systems.music_dj import MusicDJ
            self._music_dj = MusicDJ(speak_callback=None, preferences_manager=self._prefs)
            return self._music_dj
        except Exception: return None

    def _handle_dj_play_mood(self, m):
        """P6 FIX: Extract the mood keyword, not the full sentence."""
        dj = self._get_dj()
        if not dj:
            return "Music DJ is not available."
        text = m.group(0).lower()
        # Try to detect mood from the full text using MusicDJ's own detector
        mood = dj.detect_mood(text)
        return dj.play_mood(mood)

    def _get_qs(self):
        if self._quantum_simulator: return self._quantum_simulator
        try:
            from systems.quantum_simulator import QuantumSimulator
            self._quantum_simulator = QuantumSimulator(verbose=False)
            return self._quantum_simulator
        except Exception: return None

    def _handle_qs_invest(self, m):
        qs = self._get_qs()
        if not qs: return "Quantum Simulator is not available."
        return qs.analyze_investment_decision(amount=float(m.group(1).replace(',','')), asset=m.group(2).strip())

    def _handle_qs_job(self, m):
        qs = self._get_qs()
        if not qs: return "Quantum Simulator is not available."
        return qs.analyze_job_change(current_salary=80000, new_salary=100000)['recommendation']

    def _handle_bg_activity(self, m):
        return self._services.what_did_you_do() if self._services else "Background services not running."

    def _handle_email_summary(self, m):
        return self._services.email_summary() if self._services else "Email check requires background services."

    def _handle_bg_status(self, m):
        return self._services.full_status() if self._services else "Services down."

    def _handle_pref_set(self, m):
        cat, val = m.group(1), m.group(2)
        if not self._prefs:
            try: from core.preferences_manager import PreferencesManager; self._prefs = PreferencesManager()
            except: return "Prefs manager unavailable."
        return self._prefs.set_explicit_preference(cat, val)

    def _handle_pref_list(self, m):
        if not self._prefs:
            try: from core.preferences_manager import PreferencesManager; self._prefs = PreferencesManager()
            except: return "Prefs manager unavailable."
        return self._prefs.list_preferences()

    def _handle_pref_get(self, m):
        if not self._prefs:
            try: from core.preferences_manager import PreferencesManager; self._prefs = PreferencesManager()
            except: return "Prefs manager unavailable."
        val = self._prefs.get_preference(m.group(1))
        return f"Your {m.group(1)} is set to {val}." if val else f"No {m.group(1)} preference set."

    def _handle_use_ollama(self, m):
        self.ai.gemini_enabled = False
        return "Switched to local mode (Ollama)."

    def _handle_use_gemini(self, m):
        self.ai._init_gemini()
        return "Switched to online mode (Gemini)." if self.ai.gemini_enabled else "Gemini API failed."

    def _handle_which_ai(self, m):
        mode = "Gemini" if self.ai._is_gemini_available() else "Ollama (Local)"
        return f"I'm currently using {mode} as my brain."

    def _handle_learn_app(self, m):
        al = getattr(self, "app_learner", None)
        return al.force_learn(m.group(1)) if al else "App Learner unavailable."

    def _handle_howto_in_app(self, m):
        al = getattr(self, "app_learner", None)
        return al.start_workflow(m.group(2), m.group(1)) if al else "App Learner unavailable."

    def _handle_next_step(self, m):
        al = getattr(self, "app_learner", None)
        return al.next_step() if al else "No active workflow."
