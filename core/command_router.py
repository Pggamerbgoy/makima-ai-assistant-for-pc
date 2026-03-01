from core.command_router_v1_backup import CommandRouter
import logging

logger = logging.getLogger("Makima.CommandRouter.Extra")

# ─── Background Service Handlers (appended) ───────────────────────────────────

BACKGROUND_PATTERNS = [
    (r"what did you do(?: in background)?|background activity|what happened", "_handle_bg_activity"),
    (r"(?:check|any|what|read) (?:new )?emails?(?:come in| came in)?", "_handle_email_summary"),
    (r"background status|service status", "_handle_bg_status"),
    (r"enable whatsapp auto.?reply(?: with message (.+))?", "_handle_wa_bg_enable"),
    (r"disable whatsapp auto.?reply", "_handle_wa_bg_disable"),
    (r"add vip(?: contact)? (.+)", "_handle_add_vip"),
    (r"watch folder (.+)", "_handle_watch_folder"),
    (r"auto organize (?:on|enable)", "_handle_auto_org_on"),
    (r"auto organize (?:off|disable)", "_handle_auto_org_off"),
]

def _handle_bg_activity(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.what_did_you_do()
    return "Background services not initialized."

def _handle_email_summary(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.email_summary()
    if self._email:
        return self._email.check_inbox()
    return "Email not configured."

def _handle_bg_status(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.full_status()
    return "Background services not running."

def _handle_wa_bg_enable(self, m):
    msg = m.group(1) or "" if m.lastindex else ""
    if hasattr(self, '_services') and self._services:
        return self._services.enable_whatsapp_autoreply(msg)
    return "Background services not initialized."

def _handle_wa_bg_disable(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.disable_whatsapp_autoreply()
    return "Background services not initialized."

def _handle_add_vip(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.add_vip_contact(m.group(1))
    return "Background services not initialized."

def _handle_watch_folder(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.watch_folder(m.group(1))
    return "Background services not initialized."

def _handle_auto_org_on(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.toggle_auto_organize(True)
    return "Background services not initialized."

def _handle_auto_org_off(self, m):
    if hasattr(self, '_services') and self._services:
        return self._services.toggle_auto_organize(False)
    return "Background services not initialized."

# Monkey-patch the extra handlers and patterns into CommandRouter
import types
for pattern, handler_name in BACKGROUND_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (pattern, handler_name))

for name, fn in [
    ("_handle_bg_activity", _handle_bg_activity),
    ("_handle_email_summary", _handle_email_summary),
    ("_handle_bg_status", _handle_bg_status),
    ("_handle_wa_bg_enable", _handle_wa_bg_enable),
    ("_handle_wa_bg_disable", _handle_wa_bg_disable),
    ("_handle_add_vip", _handle_add_vip),
    ("_handle_watch_folder", _handle_watch_folder),
    ("_handle_auto_org_on", _handle_auto_org_on),
    ("_handle_auto_org_off", _handle_auto_org_off),
]:
    setattr(CommandRouter, name, fn)

# ─── Calendar + Preferences ──────────────────────────────────────────────────

CALENDAR_PREF_PATTERNS = [
    (r"(?:my )?(?:today'?s? )?schedule(?: today)?", "_handle_calendar_today"),
    (r"(?:what'?s? on )?my calendar|upcoming events?", "_handle_calendar_upcoming"),
    (r"set (?:my )?(?:default )([a-zA-Z0-9_\-]+) (?:app |platform )?to (.+)", "_handle_pref_set"),
    (r"set (?:my )?([a-zA-Z0-9_\-]+) preference to (.+)", "_handle_pref_set"),
    (r"what(?:\'s| is) my (?:default )?([a-zA-Z0-9_\\-]+(?:\\s+[a-zA-Z0-9_\\-]+)*)(?:\\s+preference)?[?]?", "_handle_pref_get"),
    (r"what(?:\'s| is) my ([a-zA-Z0-9_\\-]+(?:\\s+[a-zA-Z0-9_\\-]+)*) preference[?]?", "_handle_pref_get"),
    (r"(?:show|list) (?:my )?preferences", "_handle_pref_list"),
    (r"clear (?:my )?(.+?) preference", "_handle_pref_clear"),
]

def _handle_calendar_today(self, m):
    if not self._calendar:
        try:
            from systems.calendar_manager import CalendarManager
            self._calendar = CalendarManager()
        except Exception: return "Calendar manager unavailable."
    return self._calendar.get_todays_events()

def _handle_calendar_upcoming(self, m):
    if not self._calendar:
        try:
            from systems.calendar_manager import CalendarManager
            self._calendar = CalendarManager()
        except Exception: return "Calendar manager unavailable."
    return self._calendar.get_upcoming_events()

def _handle_pref_set(self, m):
    if not self._prefs:
        try:
            from core.preferences_manager import PreferencesManager
            self._prefs = PreferencesManager()
        except Exception: return "Preferences manager unavailable."
    return self._prefs.set_explicit_preference(m.group(1), m.group(2))

def _handle_pref_get(self, m):
    if not self._prefs:
        try:
            from core.preferences_manager import PreferencesManager
            self._prefs = PreferencesManager()
        except Exception: return "Preferences manager unavailable."
    val = self._prefs.get_preference(m.group(1))
    cat = m.group(1)
    return f"Your preferred {cat} is {val}." if val else f"No preference set for {cat} yet."

def _handle_pref_list(self, m):
    if not self._prefs:
        try:
            from core.preferences_manager import PreferencesManager
            self._prefs = PreferencesManager()
        except Exception: return "Preferences manager unavailable."
    return self._prefs.list_preferences()

def _handle_pref_clear(self, m):
    if not self._prefs:
        try:
            from core.preferences_manager import PreferencesManager
            self._prefs = PreferencesManager()
        except Exception: return "Preferences manager unavailable."
    return self._prefs.clear_preference(m.group(1))

# Patch Calendar/Prefs
for _pattern, _handler_name in CALENDAR_PREF_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_calendar_today",    _handle_calendar_today),
    ("_handle_calendar_upcoming", _handle_calendar_upcoming),
    ("_handle_pref_set",          _handle_pref_set),
    ("_handle_pref_get",          _handle_pref_get),
    ("_handle_pref_list",         _handle_pref_list),
    ("_handle_pref_clear",        _handle_pref_clear),
]:
    setattr(CommandRouter, _name, _fn)

# ─── AI Backend Switching ───────────────────────────────────────────────────

def _handle_use_ollama(self, m):
    self.ai.gemini_enabled = False
    model = self.ai.ollama_model
    return f"Switched to offline mode. Using local model: {model}."

def _handle_use_gemini(self, m):
    self.ai._init_gemini()
    if self.ai.gemini_enabled:
        return f"Switched to Gemini ({self.ai.gemini_model}). Online AI active."
    return "Gemini unavailable — check your API key in .env."

def _handle_which_ai(self, m):
    if self.ai._is_gemini_available():
        return f"Using Gemini ({self.ai.gemini_model}) — online, high quality."
    return f"Using Ollama local model ({self.ai.ollama_model}) — offline mode."

BACKEND_PATTERNS = [
    (r"use (?:ollama|local|offline)(?:\s+mode)?",        "_handle_use_ollama"),
    (r"use (?:gemini|online|cloud)(?:\s+mode)?",         "_handle_use_gemini"),
    (r"(?:which|what) (?:ai|model|brain)(?: are you using)?", "_handle_which_ai"),
]

for _pattern, _handler_name in BACKEND_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_use_ollama", _handle_use_ollama),
    ("_handle_use_gemini", _handle_use_gemini),
    ("_handle_which_ai",   _handle_which_ai),
]:
    setattr(CommandRouter, _name, _fn)

# ─── Skill Teaching ─────────────────────────────────────────────────────────

def _handle_learn(self, m):
    task = m.group(1).strip()
    if hasattr(self, "skill_teacher") and self.skill_teacher:
        return self.skill_teacher.teach(task)
    return "Skill teacher not available."

def _handle_run_skill(self, m):
    user_input = m.group(0)
    if hasattr(self, "skill_teacher") and self.skill_teacher:
        result = self.skill_teacher.try_run_skill(user_input)
        if result: return result
    return None

def _handle_list_skills(self, m):
    if hasattr(self, "skill_teacher") and self.skill_teacher:
        return self.skill_teacher.list_skills()
    return "Skill teacher not available."

SKILL_PATTERNS = [
    (r"(?:learn|teach yourself|teach me) (?:how )?(?:to )?(.*)", "_handle_learn"),
    (r"what skills (?:do you (?:have|know)|have you learned)|list skills",  "_handle_list_skills"),
]

for _pattern, _handler_name in SKILL_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_learn",       _handle_learn),
    ("_handle_list_skills", _handle_list_skills),
]:
    setattr(CommandRouter, _name, _fn)

# ─── App Learner ──────────────────────────────────────────────────────────

def _handle_learn_app(self, m):
    app = m.group(1).strip()
    al = getattr(self, "app_learner", None)
    if al: return al.force_learn(app)
    return "App learner not available."

def _handle_howto_in_app(self, m):
    task, app = m.group(1).strip(), m.group(2).strip()
    al = getattr(self, "app_learner", None)
    if al: return al.start_workflow(app, task)
    return "App learner not available."

def _handle_howto(self, m):
    task = m.group(1).strip()
    al = getattr(self, "app_learner", None)
    if al and al._current_app:
        return al.start_workflow(al._current_app, task)
    return None

def _handle_next_step(self, m):
    al = getattr(self, "app_learner", None)
    if al: return al.next_step()
    return "No active workflow."

def _handle_stop_guide(self, m):
    al = getattr(self, "app_learner", None)
    if al: return al.stop_workflow()
    return "No active guide."

def _handle_app_overview(self, m):
    app = m.group(1).strip()
    al = getattr(self, "app_learner", None)
    if al: return al.get_app_overview(app)
    return "App learner not available."

APP_LEARNER_PATTERNS = [
    (r"learn (?:the )?app (.+)",                              "_handle_learn_app"),
    (r"how (?:do i|to) (.+?) in (.+)",                       "_handle_howto_in_app"),
    (r"how (?:do i|to) (.+)",                                "_handle_howto"),
    (r"next step",                                            "_handle_next_step"),
    (r"(?:stop|exit|cancel) (?:guide|workflow|walkthrough)",  "_handle_stop_guide"),
    (r"(?:tell me about|what is|describe) (?:the )?app (.+)","_handle_app_overview"),
]

for _pattern, _handler_name in APP_LEARNER_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_learn_app",   _handle_learn_app),
    ("_handle_howto_in_app",_handle_howto_in_app),
    ("_handle_howto",       _handle_howto),
    ("_handle_next_step",   _handle_next_step),
    ("_handle_stop_guide",  _handle_stop_guide),
    ("_handle_app_overview",_handle_app_overview),
]:
    setattr(CommandRouter, _name, _fn)

# ─── Music DJ ───────────────────────────────────────────────────────────────

def _get_dj(self):
    if getattr(self, '_music_dj', None): return self._music_dj
    try:
        from systems.music_dj import MusicDJ
        self._music_dj = MusicDJ(speak_callback=getattr(self, "_speak_callback", None),
                                  preferences_manager=getattr(self, '_prefs', None))
        return self._music_dj
    except Exception: return None

def _handle_dj_play_mood(self, m):
    dj = self._get_dj()
    if not dj: return "Music DJ is not available."
    return dj.play_mood(dj.detect_mood(m.group(0)))

def _handle_dj_pause(self, m):
    dj = self._get_dj()
    return dj.pause() if dj else "Music DJ not available."

def _handle_dj_resume(self, m):
    dj = self._get_dj()
    return dj.resume() if dj else "Music DJ not available."

def _handle_dj_skip(self, m):
    dj = self._get_dj()
    return dj.skip() if dj else "Music DJ not available."

def _handle_dj_now_playing(self, m):
    dj = self._get_dj()
    return dj.now_playing() if dj else "Music DJ not available."

DJ_PATTERNS = [
    (r"play (?:some |me )?(?:focus|study|lofi|chill|hype|workout|gym|energy|party) (?:music|songs?|vibes?)", "_handle_dj_play_mood"),
    (r"play something (\w+)",                                "_handle_dj_play_mood"),
    (r"(?:music|dj) (?:pause|stop)",                        "_handle_dj_pause"),
    (r"(?:music|dj) (?:resume|continue|unpause)",           "_handle_dj_resume"),
    (r"(?:music|dj) (?:skip|next)",                         "_handle_dj_skip"),
    (r"what(?:'s| is) (?:currently )?playing",               "_handle_dj_now_playing"),
]

for _pattern, _handler_name in DJ_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_get_dj",                _get_dj),
    ("_handle_dj_play_mood",   _handle_dj_play_mood),
    ("_handle_dj_pause",       _handle_dj_pause),
    ("_handle_dj_resume",      _handle_dj_resume),
    ("_handle_dj_skip",        _handle_dj_skip),
    ("_handle_dj_now_playing", _handle_dj_now_playing),
]:
    setattr(CommandRouter, _name, _fn)

# ─── Quantum Simulator ──────────────────────────────────────────────────────

def _get_qs(self):
    if getattr(self, '_quantum_simulator', None): return self._quantum_simulator
    try:
        from systems.quantum_simulator import QuantumSimulator
        self._quantum_simulator = QuantumSimulator(verbose=False)
        return self._quantum_simulator
    except Exception: return None

def _handle_qs_invest(self, m):
    qs = self._get_qs()
    if not qs: return "Quantum Simulator is not available."
    amount = float(m.group(1).replace(',', ''))
    asset = m.group(2).strip().title()
    res = qs.analyze_investment_decision(amount=amount, asset=asset, expected_return=0.10, volatility=0.20)
    return f"Quantum Simulation complete for {asset}.\n\n{res['recommendation']}"

def _handle_qs_job(self, m):
    qs = self._get_qs()
    if not qs: return "Quantum Simulator is not available."
    res = qs.analyze_job_change(current_salary=80000, new_salary=100000)
    return f"Quantum Simulation complete.\n\n{res['recommendation']}"

QS_PATTERNS = [
    (r"(?:quantum )?simulate (?:an )?investment of \$?([\d,]+) in (.+)", "_handle_qs_invest"),
    (r"(?:quantum )?simulate (?:a )?job change", "_handle_qs_job"),
]

for _pattern, _handler_name in QS_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_get_qs", _get_qs),
    ("_handle_qs_invest", _handle_qs_invest),
    ("_handle_qs_job", _handle_qs_job),
]:
    setattr(CommandRouter, _name, _fn)

# ─── Mood Tracker ────────────────────────────────────────────────────────────

def _handle_my_mood(self, m):
    mgr = getattr(self, '_mood', None)
    if not mgr:
        try:
            from systems.mood_tracker import MoodTracker
            self._mood = MoodTracker()
            mgr = self._mood
        except Exception:
            return "Mood tracker not available."
    return mgr.get_session_summary()

def _handle_mood_history(self, m):
    mgr = getattr(self, '_mood', None)
    if not mgr:
        try:
            from systems.mood_tracker import MoodTracker
            self._mood = MoodTracker()
            mgr = self._mood
        except Exception:
            return "Mood tracker not available."
    return mgr.get_history_summary()

def _handle_set_mood(self, m):
    emotion = m.group(1).strip()
    mgr = getattr(self, '_mood', None)
    if not mgr:
        try:
            from systems.mood_tracker import MoodTracker
            self._mood = MoodTracker()
            mgr = self._mood
        except Exception:
            return f"Got it, noted you're feeling {emotion}."
    return mgr.set_emotion(emotion)

MOOD_PATTERNS = [
    (r"how am i (?:feeling|doing)[?]?|my (?:mood|vibe)[?]?",   "_handle_my_mood"),
    (r"mood (?:history|trends?|log)",                           "_handle_mood_history"),
    (r"i(?:'m| am) feeling (.+)",                              "_handle_set_mood"),
    (r"i feel (.+)",                                            "_handle_set_mood"),
]

for _pattern, _handler_name in MOOD_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_my_mood",    _handle_my_mood),
    ("_handle_mood_history", _handle_mood_history),
    ("_handle_set_mood",   _handle_set_mood),
]:
    setattr(CommandRouter, _name, _fn)


# ─── Session Summarizer ──────────────────────────────────────────────────────

def _handle_summarize_session(self, m):
    if self.ai and hasattr(self.ai, "_summarizer") and self.ai._summarizer:
        history = getattr(self.ai, "conversation_history", [])
        if not history:
            return "Nothing to summarize yet — we haven't talked much this session."
        return self.ai._summarizer.summarize_session(history)
    return "Session summarizer not available."

def _handle_list_sessions(self, m):
    if self.ai and hasattr(self.ai, "_summarizer") and self.ai._summarizer:
        return self.ai._summarizer.format_session_list()
    return "Session archive not available."

SESSION_PATTERNS = [
    (r"summarize (?:this )?(?:session|conversation|chat)",   "_handle_summarize_session"),
    (r"(?:show|list) (?:past|old|archived|previous) sessions?", "_handle_list_sessions"),
    (r"what did we (?:talk|discuss|cover) (?:about )?(?:today|this session)?", "_handle_summarize_session"),
]

for _pattern, _handler_name in SESSION_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_summarize_session", _handle_summarize_session),
    ("_handle_list_sessions",     _handle_list_sessions),
]:
    setattr(CommandRouter, _name, _fn)


# ─── Claude Coder Commands ────────────────────────────────────────────────────

def _handle_claude_status(self, m):
    try:
        from core.claude_coder import get_claude_coder
        s = get_claude_coder().get_status()
        if not s["package_installed"]:
            return "Claude package not installed. Run: pip install anthropic"
        if not s["api_key_set"]:
            return (
                "Claude Coder is ready to activate!\n"
                "Add your API key to .env:\n  ANTHROPIC_API_KEY=sk-ant-...\n"
                "Get one free at: console.anthropic.com"
            )
        status = "✅ Active" if s["available"] else "❌ Inactive"
        return (
            f"Claude Coder: {status}\n"
            f"Model: {s['model']}\n"
            f"Requests made: {s['requests_made']}\n"
            f"Failures: {s['fail_count']}"
        )
    except Exception as e:
        return f"Claude Coder unavailable: {e}"

def _handle_claude_model(self, m):
    model = m.group(1).strip()
    valid = {
        "haiku":  "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-6",
    }
    import os
    chosen = valid.get(model.lower(), model)
    os.environ["CLAUDE_CODE_MODEL"] = chosen
    try:
        from core.claude_coder import get_claude_coder
        get_claude_coder()._model = chosen
    except Exception:
        pass
    return f"Claude Coder model set to: {chosen}"

def _handle_claude_debug(self, m):
    code = m.group(1).strip()
    # Try Claude API first, fall back to coder persona on Gemini/Ollama
    try:
        from core.claude_coder import get_claude_coder
        coder = get_claude_coder()
        if coder.available:
            result = coder.debug(code)
            if result:
                return result
    except Exception:
        pass
    # Fallback: use coder persona
    if self.ai:
        return self.ai.code_chat(f"Debug this code and fix all errors:\n```\n{code}\n```")
    return "AI backend not available."

def _handle_claude_explain(self, m):
    code = m.group(1).strip()
    # Try Claude API first, fall back to coder persona
    try:
        from core.claude_coder import get_claude_coder
        coder = get_claude_coder()
        if coder.available:
            result = coder.explain(code)
            if result:
                return result
    except Exception:
        pass
    if self.ai:
        return self.ai.code_chat(f"Explain what this code does, step by step:\n```\n{code}\n```")
    return "AI backend not available."

CLAUDE_CODER_PATTERNS = [
    (r"claude (?:coder )?status|how is claude|is claude (?:coder )?(?:active|working|on)",
     "_handle_claude_status"),
    (r"(?:use|switch to|set) claude (?:model to )?(haiku|sonnet|claude-\S+)",
     "_handle_claude_model"),
    (r"debug(?:: | this: | )(.+)",
     "_handle_claude_debug"),
    (r"explain (?:this )?code[: ](.+)",
     "_handle_claude_explain"),
]

for _pattern, _handler_name in CLAUDE_CODER_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pattern, _handler_name))

for _name, _fn in [
    ("_handle_claude_status",  _handle_claude_status),
    ("_handle_claude_model",   _handle_claude_model),
    ("_handle_claude_debug",   _handle_claude_debug),
    ("_handle_claude_explain", _handle_claude_explain),
]:
    setattr(CommandRouter, _name, _fn)


# ══════════════════════════════════════════════════════════════════════════════
# YouTube Player Commands
# ══════════════════════════════════════════════════════════════════════════════

def _yt_player(self):
    """Get or create the YouTubePlayer instance."""
    if not hasattr(self, '_yt') or self._yt is None:
        try:
            from systems.youtube_player import get_youtube_player
            speak_cb = getattr(self, '_speak', None)
            self._yt = get_youtube_player(speak_callback=speak_cb)
        except Exception as e:
            self._yt = None
            logger.warning(f"YouTubePlayer unavailable: {e}")
    return self._yt

def _handle_yt_play(self, m):
    """Play a song on YouTube — actual audio, no browser."""
    query = m.group(1).strip() if m.lastindex and m.group(1) else ""
    if not query:
        return "What do you want me to play on YouTube?"
    yt = _yt_player(self)
    if not yt:
        return "YouTube player not available. Run: pip install yt-dlp python-vlc"
    if not yt.available:
        return (
            "yt-dlp is not installed.\n"
            "Run this and restart Makima:\n"
            "  pip install yt-dlp python-vlc"
        )
    # Play in background so UI doesn't freeze
    import threading
    result_box = [None]
    def _do():
        result_box[0] = yt.play(query)
    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=15)   # wait up to 15s for search + stream URL
    return result_box[0] or f"🎵 Looking up '{query}' on YouTube..."

def _handle_yt_pause(self, m):
    yt = _yt_player(self)
    return yt.pause() if yt else "YouTube player not available."

def _handle_yt_resume(self, m):
    yt = _yt_player(self)
    return yt.resume() if yt else "YouTube player not available."

def _handle_yt_stop(self, m):
    yt = _yt_player(self)
    return yt.stop() if yt else "YouTube player not available."

def _handle_yt_skip(self, m):
    yt = _yt_player(self)
    return yt.skip() if yt else "YouTube player not available."

def _handle_yt_queue(self, m):
    query = m.group(1).strip() if m.lastindex and m.group(1) else ""
    if not query:
        return "What do you want to queue?"
    yt = _yt_player(self)
    return yt.queue(query) if yt else "YouTube player not available."

def _handle_yt_volume(self, m):
    yt = _yt_player(self)
    if not yt:
        return "YouTube player not available."
    nums = [int(x) for x in __import__('re').findall(r'\d+', m.group(0))]
    if nums:
        return yt.set_volume(nums[0])
    return "Tell me a volume 0–100, e.g. 'youtube volume 70'."

def _handle_yt_now_playing(self, m):
    yt = _yt_player(self)
    return yt.now_playing() if yt else "YouTube player not available."

def _handle_yt_install_help(self, m):
    return (
        "To play YouTube audio in Makima, install these:\n\n"
        "  pip install yt-dlp\n"
        "  pip install python-vlc\n\n"
        "Also install VLC media player: https://www.videolan.org/vlc/\n\n"
        "Then say: 'play [song name] on youtube'"
    )

# ── Patterns (inserted at HIGH priority so they match before generic handlers) ─

YOUTUBE_PATTERNS = [
    # Play — catch "play X on youtube" and "play X youtube"
    (r"play (.+?) on youtube",                          "_handle_yt_play"),
    (r"play (.+?) youtube",                             "_handle_yt_play"),
    (r"youtube (?:play|search for|search) (.+)",        "_handle_yt_play"),
    (r"(?:put on|start|play) (.+) (?:from|on) yt",     "_handle_yt_play"),

    # Controls
    (r"(?:pause|stop) youtube",                         "_handle_yt_pause"),
    (r"(?:resume|continue|unpause) youtube",            "_handle_yt_resume"),
    (r"stop youtube|youtube stop",                      "_handle_yt_stop"),
    (r"(?:skip|next) (?:youtube|song|track)",           "_handle_yt_skip"),
    (r"queue (.+?) (?:on )?youtube",                    "_handle_yt_queue"),
    (r"youtube (?:volume|vol) (?:to )?(\d+)",           "_handle_yt_volume"),
    (r"(?:what(?:'s| is) playing|now playing) (?:on )?youtube", "_handle_yt_now_playing"),

    # Help
    (r"how (?:do i |to )?(?:install|setup|set up) youtube (?:player|audio)?",
                                                        "_handle_yt_install_help"),
]

for _pat, _hname in YOUTUBE_PATTERNS:
    CommandRouter.PATTERNS.insert(0, (_pat, _hname))

for _name, _fn in [
    ("_yt_player",              _yt_player),
    ("_handle_yt_play",         _handle_yt_play),
    ("_handle_yt_pause",        _handle_yt_pause),
    ("_handle_yt_resume",       _handle_yt_resume),
    ("_handle_yt_stop",         _handle_yt_stop),
    ("_handle_yt_skip",         _handle_yt_skip),
    ("_handle_yt_queue",        _handle_yt_queue),
    ("_handle_yt_volume",       _handle_yt_volume),
    ("_handle_yt_now_playing",  _handle_yt_now_playing),
    ("_handle_yt_install_help", _handle_yt_install_help),
]:
    setattr(CommandRouter, _name, _fn)

logger.debug("YouTube Player commands registered.")
