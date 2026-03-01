"""
core/makima_manager.py
──────────────────────────────────────────────────────────────────
MakimaManager — Central Nervous System

Single entry point for every Makima capability.
Decoupled from voice/UI loops entirely.

REPLACES the god-object pattern in MakimaAssistant.__init__
The front-end (voice loop, UI, web dashboard) just calls manager methods.

USAGE:
    from core.makima_manager import MakimaManager

    manager = MakimaManager()
    manager.start()

    # Then from anywhere — voice loop, UI, web dashboard, scripts:
    manager.handle("play something chill")
    manager.handle("open vscode")
    manager.handle("should I invest $5000 in bitcoin?")
    manager.music.play("lo-fi beats")
    manager.system.screenshot()
    manager.agents.run("summarize my last 5 emails")
    manager.status()
"""

import logging
import threading
import queue
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("Makima.Manager")

# ── Optional feature imports ─────────────────────────────────────────────
try:
    from core.claude_coder import get_claude_coder
    _claude_coder = get_claude_coder()
    CLAUDE_CODER_AVAILABLE = _claude_coder.available
except Exception:
    _claude_coder = None
    CLAUDE_CODER_AVAILABLE = False

try:
    from systems.mood_tracker import MoodTracker
    MOOD_AVAILABLE = True
except ImportError:
    MOOD_AVAILABLE = False

try:
    from core.session_summarizer import SessionSummarizer
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False

try:
    from systems.daily_briefing import DailyBriefing
    BRIEFING_AVAILABLE = True
except ImportError:
    BRIEFING_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# SUB-MANAGERS  (each owns one domain)
# ══════════════════════════════════════════════════════════════════════════════

class MusicManager:
    """Owns everything music/Spotify."""

    def __init__(self, speak_fn: Callable = None):
        self.speak = speak_fn or print
        self._dj = None
        self._spotify = None
        self._ready = False
        self._init()

    def _init(self):
        try:
            from systems.music_dj import MusicDJ
            self._dj = MusicDJ()
            self._ready = True
            logger.info("🎵 MusicManager ready (MusicDJ)")
        except Exception as e:
            logger.warning(f"MusicDJ unavailable: {e}")

        try:
            from systems.spotify_control import SpotifyControl
            self._spotify = SpotifyControl()
            self._ready = True
            logger.info("🎵 MusicManager ready (Spotify)")
        except Exception as e:
            logger.warning(f"Spotify unavailable: {e}")

        try:
            from systems.web_music import WebMusic
            self._web_music = WebMusic()
            self._ready = True
            logger.info("🎵 MusicManager ready (WebMusic)")
        except Exception as e:
            logger.warning(f"WebMusic unavailable: {e}")
            self._web_music = None

    # ── Public API ────────────────────────────────────────────────────────────

    def play(self, query: str = None) -> str:
        """P10 FIX: Play with clear fallback chain + WebMusic fallback."""
        errors = []

        # 1. Try MusicDJ (Mood-based)
        if self._dj and query:
            try:
                mood = self._dj.detect_mood(query)
                result = self._dj.play_mood(mood)
                if result and "unavailable" not in result.lower() and "failed" not in result.lower():
                    return result
                errors.append("MusicDJ: " + str(result))
            except Exception as e:
                errors.append("MusicDJ: " + str(e))

        # 2. Try SpotifyControl (Direct Search)
        if self._spotify:
            try:
                result = self._spotify.play(query or "")
                if "unavailable" not in result.lower() and "not set" not in result.lower():
                    return "Playing " + str(query or "your music") + " on Spotify."
                errors.append("Spotify: " + str(result))
            except Exception as e:
                errors.append("Spotify: " + str(e))

        # 3. Fallback to WebMusic (Browser)
        if self._web_music and query:
            try:
                logger.info(f"Falling back to WebMusic for: {query}")
                return self._web_music.play_any(query)
            except Exception as e:
                errors.append("WebMusic: " + str(e))

        if query:
            return (
                f"Couldn't play {repr(query)} on Spotify. "
                "I've attempted to open it in your browser as a fallback."
            )
        return "Music unavailable. Tell me what you'd like to hear."


    def next(self) -> str:
        if self._spotify:
            try: self._spotify.next_track(); return "Skipped."
            except: pass
        return "Skipped. (simulated)"

    def previous(self) -> str:
        if self._spotify:
            try: self._spotify.previous_track(); return "Previous track."
            except: pass
        return "Previous. (simulated)"

    def set_volume(self, level: int) -> str:
        """level: 0-100"""
        level = max(0, min(100, level))
        if self._spotify:
            try: self._spotify.set_volume(level); return f"Spotify volume set to {level}%."
            except: pass
        return f"Volume set to {level}%. (simulated)"

    def now_playing(self) -> str:
        if self._spotify:
            try:
                info = self._spotify.current_track()
                if info:
                    return f"Now playing: {info.get('name','?')} by {info.get('artist','?')}"
            except: pass
        return "Nothing playing."

    @property
    def ready(self) -> bool:
        return self._ready


# ─────────────────────────────────────────────────────────────────────────────

class AppManager:
    """Owns app open/close/toggle."""

    def __init__(self):
        self._controller = None
        self._init()

    def _init(self):
        try:
            from systems.app_control import AppControl
            self._controller = AppControl()
            logger.info("📱 AppManager ready")
        except Exception as e:
            logger.warning(f"AppControl unavailable: {e}")

    def open(self, app_name: str) -> str:
        if self._controller:
            result = self._controller.open(app_name)
            return result.get("message", f"Opening {app_name}.")
        return f"Opening {app_name}. (simulated — AppControl not loaded)"

    def close(self, app_name: str) -> str:
        if self._controller:
            result = self._controller.close(app_name)
            return result.get("message", f"Closing {app_name}.")
        return f"Closing {app_name}. (simulated)"

    def toggle(self, app_name: str) -> str:
        if self._controller:
            result = self._controller.toggle(app_name)
            return result.get("message", f"Toggled {app_name}.")
        return f"Toggled {app_name}. (simulated)"

    def is_running(self, app_name: str) -> bool:
        if self._controller:
            return self._controller.is_running(app_name)
        return False

    def list_running(self):
        if self._controller:
            return self._controller.list_running()
        return []


# ─────────────────────────────────────────────────────────────────────────────

class SystemManager:
    """Owns volume, brightness, screenshot, lock, focus mode."""

    def __init__(self):
        self._ctrl = None
        # Keep backward-compat aliases for older call sites
        self._init()

    def _init(self):
        try:
            from systems.system_commands import SystemCommands
            self._ctrl = SystemCommands()
            logger.info("⚙️  SystemManager ready")
        except Exception as e:
            logger.warning(f"SystemCommands unavailable: {e}")

    def _call(self, method: str, *args, fallback: str = "Done. (simulated)") -> str:
        if self._ctrl and hasattr(self._ctrl, method):
            try:
                result = getattr(self._ctrl, method)(*args)
                return str(result) if result else fallback
            except Exception as e:
                logger.warning(f"SystemManager.{method} failed: {e}")
        return fallback

    def volume_up(self, amount: int = 10) -> str:
        return self._call("volume_up", amount, fallback=f"Volume up {amount}%. (simulated)")

    def volume_down(self, amount: int = 10) -> str:
        return self._call("volume_down", amount, fallback=f"Volume down {amount}%. (simulated)")

    def set_volume(self, level: int) -> str:
        return self._call("set_volume", level, fallback=f"Volume set to {level}%. (simulated)")

    def mute(self) -> str:
        return self._call("mute", fallback="Muted. (simulated)")

    def set_brightness(self, level: int) -> str:
        return self._call("set_brightness", level, fallback=f"Brightness set to {level}%. (simulated)")

    def screenshot(self, save_path: str = None) -> str:
        return self._call("screenshot", fallback="Screenshot taken. (simulated)")

    def lock_screen(self) -> str:
        # SystemCommands historically exposed lock_pc(); prefer that when available.
        if self._ctrl and hasattr(self._ctrl, "lock_pc"):
            try:
                result = self._ctrl.lock_pc()
                return str(result) if result else "Screen locked."
            except Exception as e:
                logger.warning(f"SystemManager.lock_screen failed via lock_pc: {e}")
        return self._call("lock_screen", fallback="Screen locked. (simulated)")

    def focus_mode(self, enable: bool = True) -> str:
        method = "enable_focus_mode" if enable else "disable_focus_mode"
        label = "enabled" if enable else "disabled"
        return self._call(method, fallback=f"Focus mode {label}. (simulated)")

    def shutdown(self, delay: int = 0) -> str:
        return self._call("shutdown", delay, fallback="Shutdown scheduled. (simulated)")

    def restart(self) -> str:
        return self._call("restart", fallback="Restarting. (simulated)")


# ─────────────────────────────────────────────────────────────────────────────

class AgentManager:
    """Owns the V4 agent swarm — Commander, Research, Code, Creative, Executor."""

    def __init__(self, ai_handler=None, memory=None):
        self._v4 = None
        self._router = None
        self._ai = ai_handler
        self._memory = memory
        self._init()

    def _init(self):
        try:
            from Makima_v4.main import MakimaV4
            self._v4 = MakimaV4(ai_handler=self._ai)
            logger.info("🤖 AgentManager ready (V4 swarm)")
        except Exception as e:
            logger.warning(f"MakimaV4 unavailable: {e}")

        try:
            from core.command_router import CommandRouter
            self._router = CommandRouter(ai=self._ai, memory=self._memory)
            logger.info("🤖 AgentManager ready (CommandRouter)")
        except Exception as e:
            logger.warning(f"CommandRouter unavailable: {e}")

    def run(self, task: str, use_swarm: bool = True) -> str:
        """
        Run a task through the agent swarm (V4) or router.
        use_swarm=True → complex multi-agent tasks
        use_swarm=False → simple single-agent route
        """
        # 1. ALWAYS check rigorous explicit router commands first
        if self._router:
            import re
            text = task.lower().strip()
            # Check hardcoded patterns
            for pattern, _ in self._router.PATTERNS:
                if re.search(pattern, text):
                    try:
                        resp, _ = self._router.route(task)
                        return resp
                    except Exception as e:
                        logger.warning(f"Router failed on strict match: {e}")
                        break
            
            # Check dynamic learned skills
            if getattr(self._router, "skill_teacher", None):
                if self._router.skill_teacher.try_run_skill(task):
                    resp, _ = self._router.route(task)
                    return resp

        # 2. Open-ended reasoning goes to V4 Swarm
        if use_swarm and self._v4:
            try:
                result = self._v4.process(task)
                return result if isinstance(result, str) else str(result)
            except Exception as e:
                logger.warning(f"V4 swarm failed: {e}, falling back to basic AI")

        # 3. Final fallback to basic AI (handled implicitly by route() catch-all)
        if self._router:
            try:
                resp, _ = self._router.route(task)
                return resp
            except Exception as e:
                logger.warning(f"Router fallback failed: {e}")

        return f"Agent unavailable. Task received: {task}"

    def research(self, query: str) -> str:
        """Specifically invoke the Research agent."""
        return self.run(f"[RESEARCH] {query}")

    def write_code(self, task: str) -> str:
        """Specifically invoke the Code agent."""
        return self.run(f"[CODE] {task}")

    def creative(self, task: str) -> str:
        """Specifically invoke the Creative agent."""
        return self.run(f"[CREATIVE] {task}")


# ─────────────────────────────────────────────────────────────────────────────

class PreferencesDecisionManager:
    """Owns preferences + autonomous decision engine."""

    def __init__(self):
        self._prefs = None
        self._engine = None
        self._init()

    def _init(self):
        try:
            from core.preferences_manager import PreferencesManager
            self._prefs = PreferencesManager()
            logger.info("🧠 PreferencesManager ready")
        except Exception as e:
            logger.warning(f"PreferencesManager unavailable: {e}")

        try:
            from tools.decision_engine import DecisionEngine
            self._engine = DecisionEngine(self._prefs)
            logger.info("🧠 DecisionEngine ready")
        except Exception as e:
            logger.warning(f"DecisionEngine unavailable: {e}")

    def decide(self, category: str, context: Dict = None) -> Optional[str]:
        """Return Makima's autonomous choice for a category."""
        if self._engine:
            decision = self._engine.decide(category, context or {})
            if decision.confidence > 0.3:
                return decision.value
        if self._prefs:
            return self._prefs.get_preference(category)
        return None

    def handle_command(self, command: str) -> Optional[str]:
        """Try to resolve a vague command autonomously. Returns None if can't."""
        if self._engine:
            reply = self._engine.handle(command)
            if reply and "?" not in reply:
                return reply
        return None

    def set(self, category: str, value: str) -> str:
        if self._prefs:
            return self._prefs.set_explicit_preference(category, value)
        return f"Preference saved: {category} → {value} (simulated)"

    def get(self, category: str) -> Optional[str]:
        if self._prefs:
            return self._prefs.get_preference(category)
        return None

    def record(self, category: str, value: str):
        if self._prefs:
            self._prefs.record_usage(category, value)

    def learn_correction(self, category: str, correct_value: str):
        if self._engine:
            self._engine.learn_from_correction(category, correct_value)

    def explain(self, category: str) -> str:
        if self._engine:
            return self._engine.explain(category)
        return f"No data for {category} yet."

    def list_all(self) -> str:
        if self._prefs:
            return self._prefs.list_preferences()
        return "No preferences loaded."


# ─────────────────────────────────────────────────────────────────────────────

class ToolsManager:
    """Owns intent detector, response cache, file finder, shortcuts."""

    def __init__(self, makima_ref=None):
        self._registry = None
        self._init(makima_ref)

    def _init(self, makima_ref):
        try:
            from makima_tools.tool_registry import ToolRegistry
            self._registry = ToolRegistry(makima_ref)
            self._registry.initialize_all()
            logger.info("🛠️  ToolsManager ready")
        except Exception as e:
            logger.warning(f"ToolRegistry unavailable: {e}")

    def process(self, raw_input: str) -> str:
        """Run input through cache → shortcuts → intent detection.
        Returns cached response (if cache hit) OR cleaned/expanded command string.
        """
        if self._registry:
            result = self._registry.process_command(raw_input)
            # process_command returns (is_cached: bool, value: str)
            if isinstance(result, tuple):
                _is_cached, value = result
                return value
            return result
        return raw_input

    def cache_response(self, query: str, response: str):
        if self._registry:
            self._registry.wrap_response(query, response)

    def find_file(self, query: str):
        if self._registry and self._registry.finder:
            return self._registry.finder.find(query)
        return []

    def detect_intent(self, text: str):
        if self._registry and self._registry.intent:
            return self._registry.intent.detect(text)
        return None

    def stats(self) -> Dict:
        if self._registry:
            return self._registry.get_stats()
        return {}


# ─────────────────────────────────────────────────────────────────────────────

class DecisionSimulator:
    """Owns the Quantum Decision Simulator."""

    def __init__(self):
        self._qs = None
        self._init()

    def _init(self):
        try:
            from systems.quantum_simulator import QuantumSimulator
            self._qs = QuantumSimulator(verbose=False)
            logger.info("🎲 DecisionSimulator ready")
        except Exception as e:
            logger.warning(f"QuantumSimulator unavailable: {e}")

    def analyze(self, question: str, context: Dict = None) -> str:
        """
        Analyze a decision question and return Makima's recommendation.
        question: "Should I invest $5000 in Bitcoin?"
        context:  {"amount": 5000, "investment_type": "bitcoin", ...}
        """
        if not self._qs:
            return "Decision simulator not available."

        context = context or {}
        q_lower = question.lower()

        try:
            # Route to correct analysis type
            if any(w in q_lower for w in ["invest", "bitcoin", "stock", "crypto", "etf"]):
                amount = context.get("amount", 5000)
                asset = context.get("asset", "investment")
                vol = 0.60 if any(w in q_lower for w in ["bitcoin", "crypto"]) else 0.20
                ret = context.get("expected_return", 0.15)
                result = self._qs.analyze_investment_decision(
                    amount=amount, asset=asset,
                    expected_return=ret, volatility=vol,
                    num_simulations=10000
                )

            elif any(w in q_lower for w in ["job", "salary", "career", "work"]):
                result = self._qs.analyze_job_change(
                    current_salary=context.get("current_salary", 80000),
                    new_salary=context.get("new_salary", 95000),
                    num_simulations=10000
                )

            elif any(w in q_lower for w in ["business", "startup", "venture"]):
                result = self._qs.analyze_business_venture(
                    investment=context.get("investment", 50000),
                    success_rate=context.get("success_rate", 0.40),
                    success_return=context.get("success_return", 5.0),
                    num_simulations=10000
                )
            else:
                return f"I can analyze investment, job change, or business decisions. Which type is '{question}'?"

            # Extract clean recommendation
            rec = result.get("recommendation", "")
            stats = result.get("statistics", {})
            ev = stats.get("mean", 0)
            sr = stats.get("outcomes", {}).get("success_rate", 0)
            return f"{rec.strip()}\n\nExpected value: ${ev:,.0f} | Success rate: {sr:.1f}%"

        except Exception as e:
            logger.error(f"DecisionSimulator.analyze failed: {e}")
            return f"Analysis failed: {e}"


# ─────────────────────────────────────────────────────────────────────────────

class WebSearchManager:
    """Owns web search capability."""

    def __init__(self, ai_handler=None):
        self._agent = None
        self._ai = ai_handler
        self._init()

    def _init(self):
        try:
            from agents.web_agent import WebAgent
            self._agent = WebAgent(ai=self._ai)
            logger.info("🌐 WebSearchManager ready")
        except Exception as e:
            logger.warning(f"WebAgent unavailable: {e}")

    def search(self, query: str) -> str:
        if self._agent:
            try:
                return self._agent.search(query)
            except Exception as e:
                logger.warning(f"Web search failed: {e}")
        return f"Web search unavailable. Query was: {query}"

    def fetch(self, url: str) -> str:
        """
        Fetch and summarize a URL using the web agent.

        Normalizes across legacy WebAgent APIs:
          - prefer fetch_summary(url) when available
          - fall back to open_url(url) on failure
        """
        if not self._agent:
            return f"Could not fetch {url}"

        # Prefer rich summary if supported
        if hasattr(self._agent, "fetch_summary"):
            try:
                return self._agent.fetch_summary(url)
            except Exception as e:
                logger.warning(f"Web fetch_summary failed: {e}")

        # Fallback: just open the URL
        if hasattr(self._agent, "open_url"):
            try:
                return self._agent.open_url(url)
            except Exception as e:
                logger.warning(f"Web open_url failed: {e}")

        return f"Could not fetch {url}"


# ══════════════════════════════════════════════════════════════════════════════
# MAKIMA MANAGER — The one class to rule them all
# ══════════════════════════════════════════════════════════════════════════════

class MakimaManager:
    """
    Central nervous system for Makima.

    Owns every sub-system. Front-ends (voice, UI, web dashboard, scripts)
    only talk to this — never directly to subsystems.

    Architecture:
        MakimaManager
        ├── music       → MusicManager       (Spotify, MusicDJ)
        ├── apps        → AppManager         (open/close/toggle apps)
        ├── system      → SystemManager      (volume, brightness, screenshot)
        ├── agents      → AgentManager       (V4 swarm, CommandRouter)
        ├── prefs       → PreferencesDecisionManager (preferences + autonomous decisions)
        ├── tools       → ToolsManager       (cache, intent, file finder, shortcuts)
        ├── simulator   → DecisionSimulator  (Quantum Monte Carlo)
        └── web         → WebSearchManager   (web search + fetch)
    """

    def __init__(self, speak_fn: Callable = None, text_mode: bool = False):
        """
        speak_fn: your existing self.speak / TTS function
        text_mode: True = no microphone/TTS init
        """
        self._speak_fn = speak_fn or self._default_speak
        self._text_mode = text_mode
        self._running = False
        self._command_queue = queue.Queue()
        self._event_hooks: Dict[str, list] = {}    # event → [callbacks]
        self._start_time = None

        logger.info("🌸 MakimaManager initializing...")
        self._init_subsystems()
        logger.info("✅ MakimaManager ready.")

    # ── Initialization ────────────────────────────────────────────────────────

    def _init_subsystems(self):
        """Initialize every sub-manager. Each handles its own failures."""

        # AI + Memory (needed by agents + web)
        self._ai = None
        self._memory = None
        try:
            from core.eternal_memory import EternalMemory
            self._memory = EternalMemory()
        except Exception as e:
            logger.warning(f"EternalMemory unavailable: {e}")

        try:
            from core.ai_handler import AIHandler
            self._ai = AIHandler(memory=self._memory)
        except Exception as e:
            logger.warning(f"AIHandler unavailable: {e}")

        # Sub-managers — order matters (agents needs ai+memory)
        self.music     = MusicManager(speak_fn=self._speak_fn)
        self.apps      = AppManager()
        self.system    = SystemManager()
        self.agents    = AgentManager(ai_handler=self._ai, memory=self._memory)
        self.prefs     = PreferencesDecisionManager()
        self.tools     = ToolsManager(makima_ref=self)
        self.simulator = DecisionSimulator()
        self.web       = WebSearchManager(ai_handler=self._ai)

        # ── Mood Tracker ──────────────────────────────────────────────────────────
        self.mood = None
        if MOOD_AVAILABLE:
            try:
                self.mood = MoodTracker()
                logger.info("🎭 MoodTracker ready")
            except Exception as e:
                logger.warning(f"MoodTracker unavailable: {e}")

        # ── Session Summarizer ────────────────────────────────────────────────
        self.summarizer = None
        if SUMMARIZER_AVAILABLE:
            try:
                self.summarizer = SessionSummarizer(ai_handler=self._ai)
                logger.info("📝 SessionSummarizer ready")
            except Exception as e:
                logger.warning(f"SessionSummarizer unavailable: {e}")

        # ── Daily Briefing ────────────────────────────────────────────────────
        self.briefing = None
        if BRIEFING_AVAILABLE:
            try:
                self.briefing = DailyBriefing(
                    ai=self._ai,
                    memory=self._memory,
                )
                logger.info("📰 DailyBriefing ready")
            except Exception as e:
                logger.warning(f"DailyBriefing unavailable: {e}")

        # Wire tools to speak for proactive suggestions
        if self.tools._registry and hasattr(self.tools._registry, 'proactive'):
            if self.tools._registry.proactive:
                self.tools._registry.proactive.speak = self._speak_fn
                self.tools._registry.proactive.execute = self.handle

    # ── Main handle() — single entry point for ALL commands ──────────────────

    def handle(self, command: str, source: str = "unknown") -> str:
        """
        THE main method. Every front-end calls this and only this.

        Routes command through:
        1. Tool pipeline (cache → shortcuts → intent)
        2. Autonomous decision (vague commands)
        3. Direct system commands (open X, play X, volume up)
        4. Decision simulator (financial questions)
        5. Web search
        6. Agent swarm (complex/unknown)

        Returns Makima's response string.
        """
        if not command or not command.strip():
            return ""

        logger.debug(f"[{source}] handle: {command!r}")
        self._fire_event("on_command", command=command, source=source)

        # Save user turn to memory
        if self._memory:
            self._memory.save_conversation("user", command)

        # ── Mood analysis (non-blocking, enriches response tone) ──────────────
        mood_result = None
        if self.mood:
            try:
                mood_result = self.mood.analyze(command)
                # Update AI awareness with current emotion
                if self._ai and mood_result.emotion != "neutral":
                    self._ai.update_awareness(
                        active_window=self._ai.awareness_context.get("active_window", ""),
                        vision_summary=self._ai.awareness_context.get("vision_summary", ""),
                        distraction_level=mood_result.emotion,
                    )
                    self._ai.awareness_context["last_emotion"] = mood_result.emotion
            except Exception as e:
                logger.debug(f"Mood analysis failed: {e}")

        # ── Daily briefing shortcut ───────────────────────────────────────────
        briefing_triggers = ["good morning", "morning briefing", "daily briefing",
                              "what's today look like", "full briefing", "quick briefing"]
        if any(t in command.lower() for t in briefing_triggers):
            if self.briefing:
                try:
                    style = "quick" if "quick" in command.lower() else "full"
                    response = self.briefing.deliver(style=style)
                    self._fire_event("on_response", response=response)
                    if self._memory:
                        self._memory.save_conversation("makima", response)
                    return response
                except Exception as e:
                    logger.warning(f"Daily briefing error: {e}")

        # ── Mood check-in (proactive) ────────────────────────────────────────
        if mood_result and mood_result.should_checkin:
            # Speak the check-in as a side-channel (doesn't replace response)
            self._fire_event("on_checkin", message=mood_result.checkin_message)

        # ── Step 1: Router pattern match (fastest path — exact commands) ───────
        # Try CommandRouter PATTERNS first — these are specific, unambiguous.
        # e.g. "play X on youtube", "volume up", "open chrome", "lock screen"
        if self.agents._router:
            try:
                resp, handler = self.agents._router.route(command)
                if handler and handler != "ai_chat" and resp:
                    # P7 FIX: don't cache state-dependent responses
                    if not self._is_stateful_command(command):
                        self.tools.cache_response(command, resp)
                    self._finish_response(resp)
                    return resp
            except Exception as e:
                logger.warning(f"Router step failed: {e}")

        # ── Step 2: Cache lookup (P7 FIX: skip stateful commands) ────────────
        if not self._is_stateful_command(command):
            cached = self.tools.process(command)
            if cached != command and len(cached) > 20:
                self._finish_response(cached)
                return cached

        # ── Step 3: Autonomous decision for vague/preference commands ─────────
        autonomous = self.prefs.handle_command(command)
        if autonomous:
            self._execute_decision(command, autonomous)
            self._finish_response(autonomous)
            return autonomous

        # ── Step 4: Intent routing (P1 FIX: single detection, P4 FIX: 0.55 threshold)
        intent = self.tools.detect_intent(command)
        if intent and intent.confidence > 0.55:
            direct = self._route_by_intent(intent, command)
            if direct:
                if not self._is_stateful_command(command):
                    self.tools.cache_response(command, direct)
                self._finish_response(direct)
                return direct

        # ── Step 5: Decision simulator for financial questions ────────────────
        if self._is_decision_question(command):
            response = self.simulator.analyze(command)
            self.tools.cache_response(command, response)
            self._finish_response(response)
            return response

        # ── Step 6: Web search — P8 FIX: smarter detection ──────────────────
        if self._needs_web_search(command):
            response = self.web.search(command)
            self.tools.cache_response(command, response)
            self._finish_response(response)
            return response

        # ── Step 7: AI chat (final fallback — no re-routing) ─────────────────
        # P2 FIX: don't call agents.run() which re-routes again. Go direct to AI.
        response = self._ai_fallback(command)
        if not self._is_stateful_command(command):
            self.tools.cache_response(command, response)
        self._finish_response(response)
        return response

    # ── Intent router ─────────────────────────────────────────────────────────

    def _route_by_intent(self, intent, command: str) -> Optional[str]:
        """Map detected intent directly to sub-manager calls."""
        t = intent.type
        e = intent.entities

        if t == "play_music":
            query = e.get("song_name") or e.get("artist") or e.get("mood") or \
                    self.prefs.decide("music") or "something good"
            result = self.music.play(query)
            self.prefs.record("music", query)
            return result

        if t == "open_app":
            app = e.get("app_name") or self.prefs.decide("app")
            if app:
                result = self.apps.open(app)
                self.prefs.record("app", app)
                return result

        if t == "close_app":
            app = e.get("app_name")
            if app:
                return self.apps.close(app)

        if t == "system_control":
            action = e.get("action", "").lower()
            if "screenshot" in action:   return self.system.screenshot()
            if "volume up" in action:    return self.system.volume_up()
            if "volume down" in action:  return self.system.volume_down()
            if "mute" in action:         return self.system.mute()
            if "lock" in action:         return self.system.lock_screen()
            if "focus" in action:        return self.system.focus_mode(True)
            if "brightness up" in action:   return self.system.set_brightness(80)
            if "brightness down" in action: return self.system.set_brightness(30)

        if t == "search_web":
            query = e.get("query", command)
            return self.web.search(query)

        if t == "get_info":
            # Simple factual question → light-weight route;
            # complex, multi-part question → V4 swarm.
            use_swarm = self._is_complex_query(command)
            return self.agents.run(command, use_swarm=use_swarm)

        if t == "write_code":
            task_desc = e.get("task_description") or command
            return self._handle_code_task(task_desc, command)

        # P9 FIX: previously missing intents ────────────────────────────────
        if t == "set_volume":
            level = e.get("level") or e.get("value")
            if level is not None:
                return self.system.set_volume(int(level))
            if "up" in command.lower():
                return self.system.volume_up()
            if "down" in command.lower():
                return self.system.volume_down()
            return self.system.mute()

        if t == "set_brightness":
            level = e.get("level") or e.get("value")
            if level is not None:
                return self.system.set_brightness(int(level))
            if "up" in command.lower() or "increase" in command.lower():
                return self.system.set_brightness(80)
            return self.system.set_brightness(30)

        if t in ("take_screenshot", "screenshot"):
            return self.system.screenshot()

        if t in ("lock_screen", "lock"):
            return self.system.lock_screen()

        if t in ("play_youtube", "youtube"):
            query = e.get("query") or e.get("song_name") or command
            # Route through command router which has the YouTube handler
            if self.agents._router:
                resp, _ = self.agents._router.route(f"play {query} on youtube")
                return resp
            return f"YouTube player unavailable."

        if t == "set_reminder":
            task = e.get("task") or e.get("reminder", command)
            time_str = e.get("time") or e.get("at", "")
            if self.agents._router and hasattr(self.agents._router, '_handle_reminder'):
                import re as _re
                m2 = _re.search(r"remind me to (.+) at (.+)", command.lower())
                if m2:
                    return self.agents._router._handle_reminder(m2)
            return f"Reminder set: {task}" + (f" at {time_str}" if time_str else "")

        return None

    def _handle_code_task(self, task: str, original_command: str) -> str:
        """
        Route a code task through the best available backend.
        Priority: Claude API → code_chat() with Coder Persona (Gemini/Ollama)
        """
        # 1. Try Claude API (if key is configured)
        if _claude_coder and _claude_coder.available:
            try:
                result = _claude_coder.handle_code_task(task)
                if result:
                    logger.info("Code task handled by Claude API.")
                    return result
            except Exception as e:
                logger.warning(f"Claude API failed, falling back: {e}")

        # 2. Use code_chat() — switches to the 'coder' persona for this request
        # The coder persona instructs Gemini/Ollama to behave like a sharp code editor
        logger.info("Code task using Coder Persona (Gemini/Ollama).")
        try:
            return self._ai.code_chat(task)
        except Exception as e:
            logger.warning(f"code_chat failed: {e}")
            reply, _ = self._ai.chat(original_command)
            return reply

    def _execute_decision(self, command: str, decision_reply: str):
        """After autonomous decision, actually execute the action."""
        cmd = command.lower()
        if any(w in cmd for w in ["play", "music", "song"]):
            chosen = self.prefs.decide("music")
            if chosen:
                self.music.play(chosen)
        elif any(w in cmd for w in ["open", "browser", "code", "notes"]):
            chosen = self.prefs.decide("browser") or self.prefs.decide("app")
            if chosen:
                self.apps.open(chosen)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _finish_response(self, response: str):
        """Shared response finalization: fire event + save to memory."""
        self._fire_event("on_response", response=response)
        if self._memory:
            self._memory.save_conversation("makima", response)

    def _ai_fallback(self, command: str) -> str:
        """P2 FIX: Direct AI call — no re-routing through agents.run()."""
        if self._ai:
            try:
                memory_ctx = self._memory.build_memory_context(command) if self._memory else ""
                resp, _ = self._ai.chat(command, context=memory_ctx)
                return resp
            except Exception as e:
                logger.warning(f"AI fallback failed: {e}")
        # Last resort: agents swarm (only if AI unavailable)
        if self.agents._v4:
            try:
                return self.agents._v4.process(command)
            except Exception:
                pass
        return "I'm having trouble thinking right now. Try again in a moment."

    # P7 FIX: State-dependent commands should never be cached
    _STATEFUL_COMMANDS = (
        "now playing", "what's playing", "battery", "cpu", "ram", "memory usage",
        "what time", "what date", "what day", "status", "is playing", "playing now",
        "volume", "brightness", "weather", "news", "score", "price",
    )

    def _is_stateful_command(self, command: str) -> bool:
        """Returns True for commands whose answer changes over time — don't cache these."""
        c = command.lower()
        return any(kw in c for kw in self._STATEFUL_COMMANDS)

    def _is_decision_question(self, command: str) -> bool:
        keywords = ["should i invest", "should i buy", "should i change job",
                    "should i start", "is it worth", "monte carlo", "simulate"]
        return any(k in command.lower() for k in keywords)

    def _is_complex_query(self, command: str) -> bool:
        """
        Heuristic: does this look like a multi-step / research-heavy task?
        If so, prefer the V4 agent swarm over a single-shot chat reply.
        """
        c = command.lower()
        keywords = [
            "and then",
            "also",
            "research",
            "analyze",
            "analysis",
            "compare",
            "step by step",
            "plan",
            "strategy",
            "outline",
            "multi-step",
        ]
        return any(k in c for k in keywords) or len(c.split()) > 40

    def _needs_web_search(self, command: str) -> bool:
        """P8 FIX: Only trigger web search when actually needed."""
        c = command.lower()

        # Explicit search requests — always search
        explicit = ["search for", "look up", "google", "find out", "search the web",
                    "browse", "find on internet"]
        if any(k in c for k in explicit):
            return True

        # Real-time info that changes — always search
        realtime = ["latest news", "current news", "news today", "breaking news",
                    "weather today", "weather in", "weather tomorrow",
                    "stock price", "current price", "live score", "score today",
                    "exchange rate", "crypto price"]
        if any(k in c for k in realtime):
            return True

        # "what is X" — only search for external facts, NOT local/system topics
        if "what is" in c or "who is" in c or "what are" in c:
            # Skip web for personal/system/internal questions
            skip_markers = [
                "my ", "your ", "makima", "you ", "i ", "we ", "our ",
                "time", "date", "day", "battery", "cpu", "ram", "volume",
                "focus mode", "the time", "the date", "2+2", "math",
                "status", "running", "installed",
            ]
            if any(m in c for m in skip_markers):
                return False
            # Only search for "who is [person]" or "what is [concept]" that
            # aren't system commands
            return True

        return False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Mark manager as active. Call from your main loop."""
        self._running = True
        self._start_time = time.time()
        self._fire_event("on_start")
        logger.info("🌸 MakimaManager started.")

    def stop(self):
        """Clean shutdown."""
        self._running = False
        self._fire_event("on_stop")
        logger.info("MakimaManager stopped.")

    @property
    def running(self) -> bool:
        return self._running

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> Dict:
        """Return health status of every sub-system."""
        uptime = None
        if self._start_time:
            elapsed = int(time.time() - self._start_time)
            uptime = f"{elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d}"

        return {
            "running":    self._running,
            "uptime":     uptime,
            "timestamp":  datetime.now().isoformat(),
            "subsystems": {
                "music":     self.music.ready,
                "apps":      self.apps._controller is not None,
                "system":    self.system._ctrl is not None,
                "agents":    self.agents._v4 is not None or self.agents._router is not None,
                "prefs":     self.prefs._prefs is not None,
                "tools":     self.tools._registry is not None,
                "simulator": self.simulator._qs is not None,
                "web":       self.web._agent is not None,
                "ai":        self._ai is not None,
                "memory":    self._memory is not None,
            },
            "tools_stats": self.tools.stats(),
        }

    def status_str(self) -> str:
        """Human-readable status string for Makima to speak."""
        s = self.status()
        active = [k for k, v in s["subsystems"].items() if v]
        inactive = [k for k, v in s["subsystems"].items() if not v]
        lines = [f"Running for {s['uptime']}." if s["uptime"] else "Just started."]
        if active:
            lines.append(f"Active: {', '.join(active)}.")
        if inactive:
            lines.append(f"Unavailable: {', '.join(inactive)}.")
        return " ".join(lines)

    # ── Event system ──────────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable):
        """
        Register a callback for an event.
        Events: on_command, on_response, on_start, on_stop

        Example:
            manager.on("on_response", lambda response, **kw: tts.speak(response))
            manager.on("on_command",  lambda command, **kw: hud.update(command))
        """
        self._event_hooks.setdefault(event, []).append(callback)

    def _fire_event(self, event: str, **kwargs):
        for cb in self._event_hooks.get(event, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.warning(f"Event hook {event} failed: {e}")

    # ── Context update (for proactive engine) ────────────────────────────────

    def update_context(self, **kwargs):
        """
        Feed context into the proactive engine.
        Call from your existing monitors.

        Examples:
            manager.update_context(battery_percent=15)
            manager.update_context(active_app="vscode")
            manager.update_context(is_in_call=True)
        """
        if self.tools._registry and hasattr(self.tools._registry, 'proactive'):
            if self.tools._registry.proactive:
                self.tools._registry.proactive.update_context(**kwargs)

    # ── Shorthand convenience methods ─────────────────────────────────────────

    def speak(self, text: str):
        """Speak via TTS — same as calling self._speak_fn directly."""
        self._speak_fn(text)

    def play(self, query: str = None) -> str:
        return self.music.play(query)

    def open(self, app: str) -> str:
        return self.apps.open(app)

    def close(self, app: str) -> str:
        return self.apps.close(app)

    def search(self, query: str) -> str:
        return self.web.search(query)

    def screenshot(self) -> str:
        return self.system.screenshot()

    def decide(self, question: str) -> str:
        return self.simulator.analyze(question)

    # ── Default speak (fallback if no TTS passed) ─────────────────────────────

    @staticmethod
    def _default_speak(text: str):
        print(f"[Makima] {text}")
