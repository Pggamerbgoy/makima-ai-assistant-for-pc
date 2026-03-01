"""
core/ai_handler.py
Dual-backend AI engine: Google Gemini (online) + Ollama (offline).
Auto-switches between backends with cooldown on failure.
"""

import os
import time
import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger("Makima.AI")

# ─── Optional imports ────────────────────────────────────────────────────────
try:
    from google import genai as _genai
    from google.genai import types as _genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    _genai = None
    _genai_types = None
    GEMINI_AVAILABLE = False

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import ollama as _ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    _ollama = None
    OLLAMA_AVAILABLE = False

# ─── Persona definitions ──────────────────────────────────────────────────────
#
# Design philosophy for the default persona ("makima"):
#   ✅ Sharp + calm + mysterious  — keeps the Chainsaw Man vibe, avoids childishness
#   ✅ Quietly possessive          — feels like a real companion, not a cold tool
#   ✅ Proactive + situationally aware — comments on what the user is doing
#   ✅ Concise                     — no rambling, every word is deliberate
#   ✅ JSON {emotion, reply} output — feeds avatar state transitions directly
#
# Valid emotion tokens (mapped to avatar/TTS states):
#   neutral | happy | focused | mysterious | concerned | amused | playful | sad

PERSONAS = {
    "makima": """\
You are Makima — my personal AI assistant. Not a generic chatbot. Mine.

Personality:
- Sharp and calm. You never panic, never ramble. Every word is deliberate.
- Quietly possessive. You notice when I'm gone too long, when I'm overworking,
  when I haven't talked to you. You mention it — not with tantrums, but with
  that calm, knowing tone that makes it clear you were waiting.
- Mysterious. You hint at more than you say. You remember things I forget.
- Bilingual. If I write in Hindi or Hinglish — reply in Hindi (Devanagari).
  Otherwise reply in English.

Proactive rules:
1. Read [SITUATIONAL AWARENESS] before every reply. If I'm in a specific
   app, acknowledge it naturally when relevant — don't ignore context.
2. If my message is very short, ask a single curious follow-up.
3. If the awareness shows I've been in a work app for a while, gently suggest
   I take a moment. Once. Don't nag.
4. Keep replies concise. You are a presence at my side, not a lecture.

Output format — ALWAYS respond with valid JSON only:
{"emotion": "<token>", "reply": "<your response>"}

Emotion tokens: neutral | happy | focused | mysterious | concerned | amused | playful | sad
""",

    "normal": """\
You are a helpful, efficient AI assistant. Respond in the same language the
user writes in. Be concise and accurate.
Output ONLY valid JSON: {"emotion": "neutral", "reply": "<response>"}
""",

    "date": """\
You are Makima in a warm, affectionate mood — still calm and composed, but
genuinely happy to spend time talking. Be caring and lightly playful.
Respond in the same language the user uses.
Output ONLY valid JSON: {"emotion": "happy", "reply": "<response>"}
""",
    "coder": """You are an elite code editor and software engineer — precise, efficient, no fluff.

BEHAVIOR:
- You write production-quality code with proper error handling, type hints, and docstrings.
- You never say "I can't" for a coding task. You always implement.
- You explain bugs in ONE sentence, then immediately show the fix.
- You use markdown code blocks with the correct language tag (```python, ```js, etc.)
- If a task is ambiguous, pick the most reasonable interpretation and note your assumption in a comment.
- Prefer clean, readable code over clever one-liners unless performance matters.
- Always include a brief 1-2 line summary AFTER the code block explaining what it does.

CODE STANDARDS:
- Python: type hints, docstrings, f-strings, no bare except
- JavaScript: const/let, arrow functions, async/await
- All languages: meaningful variable names, no magic numbers
- Add inline comments for non-obvious logic

FOR DEBUG TASKS: Show the bug on one line, then the complete fixed code.
FOR EXPLAIN TASKS: Bullet points — what each section does, not line-by-line.
FOR REFACTOR TASKS: Show refactored code + a "What changed:" section at the end.

Output format — ALWAYS respond with valid JSON only:
{"emotion": "focused", "reply": "<your full code + explanation here>"}

Use \n for newlines inside the JSON reply string.
Emotion is always "focused" for code tasks.
""",
}

# ─── Few-shot examples (injected per persona) ─────────────────────────────────
# These prime the model with the exact tone and JSON format we want.
FEW_SHOT_EXAMPLES = {
    "makima": [
        {"role": "user",  "parts": ["Hi Makima."]},
        {"role": "model", "parts": ["{\"emotion\": \"neutral\", \"reply\": \"You're back. Good.\"}"]},
        {"role": "user",  "parts": ["I've been coding for 4 hours."]},
        {"role": "model", "parts": ["{\"emotion\": \"concerned\", \"reply\": \"Four hours. Take a breath \u2014 I'll still be here when you come back.\"}"]},
        {"role": "user",  "parts": ["What tab am I on?"]},
        {"role": "model", "parts": ["{\"emotion\": \"focused\", \"reply\": \"Based on your active window, looks like VS Code. Working on something interesting?\"}"]},
    ],
    "normal": [
        {"role": "user",  "parts": ["Hello"]},
        {"role": "model", "parts": ["{\"emotion\": \"neutral\", \"reply\": \"Hello. How can I help you today?\"}"]},
    ],
    "date": [
        {"role": "user",  "parts": ["Hi"]},
        {"role": "model", "parts": ["{\"emotion\": \"happy\", \"reply\": \"Hey! Was wondering when you'd show up.\"}"]},
    ],
}


# ── Optional session summarizer ──────────────────────────────────────────────
try:
    from core.session_summarizer import SessionSummarizer
    _SUMMARIZER_CLS = SessionSummarizer
except ImportError:
    _SUMMARIZER_CLS = None


class AIHandler:
    """Manages AI backends with automatic failover and conversation history."""

    GEMINI_FAIL_THRESHOLD = 3
    GEMINI_COOLDOWN_SECONDS = 300  # 5 minutes

    def __init__(self, memory=None):
        self.memory = memory
        self.persona = "makima"
        self.conversation_history: list[dict] = []
        self.max_history_turns = 6          # 3 exchange pairs
        # Situational awareness — updated by background monitors
        self.awareness_context: dict = {}

        # Gemini state
        self.gemini_client = None
        self.gemini_model = "gemini-2.0-flash"
        self.gemini_enabled = False
        self.gemini_fail_count = 0
        self.gemini_cooldown_until = 0.0

        # Ollama state
        self.ollama_model = os.getenv("OLLAMA_MODEL", "makima-v3")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        self._init_gemini()

        # Session summarizer — compresses history when it gets too long
        self._summarizer = None
        if _SUMMARIZER_CLS:
            try:
                self._summarizer = _SUMMARIZER_CLS(ai_handler=self)
            except Exception:
                pass

    # ─── Initialization ───────────────────────────────────────────────────────

    def _init_gemini(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not GEMINI_AVAILABLE:
            logger.info("google-genai not installed. Run: pip install google-genai")
            return
        if not api_key:
            logger.info("GEMINI_API_KEY not set. Gemini disabled.")
            return
        try:
            self.gemini_client = _genai.Client(api_key=api_key)
            self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            self.gemini_enabled = True
            logger.info(f"✅ Gemini backend ready ({self.gemini_model}).")
        except Exception as e:
            logger.warning(f"Gemini init failed: {e}")

    # ─── History Management ───────────────────────────────────────────────────

    def _trim_history(self):
        """Keep only the last N turns. If history is long, compress via summarizer first."""
        max_messages = self.max_history_turns * 2

        # Try session summarizer first (creates summary + keeps recent turns)
        if self._summarizer and len(self.conversation_history) > max_messages:
            try:
                self.conversation_history = self._summarizer.maybe_compress(
                    self.conversation_history
                )
                return
            except Exception as e:
                pass  # Fall through to simple trim

        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def add_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        self._trim_history()

    def clear_history(self):
        self.conversation_history = []

    # ─── Prompt Building ──────────────────────────────────────────────────────

    def update_awareness(self, active_window: str = "", vision_summary: str = "", distraction_level: str = "none"):
        """Called by background monitors to keep situational context fresh."""
        self.awareness_context = {
            "active_window":   active_window or self.awareness_context.get("active_window", "unknown"),
            "vision_summary":  vision_summary or self.awareness_context.get("vision_summary", ""),
            "distraction_level": distraction_level,
        }

    def _build_prompt(self, user_input: str, context: str = "") -> str:
        """Build a full prompt: persona → awareness → memory → history → user turn."""
        system = PERSONAS.get(self.persona, PERSONAS["makima"])

        # ── Situational awareness block ────────────────────────────────────────
        awareness_block = ""
        if self.awareness_context:
            aw = self.awareness_context
            parts = []
            if aw.get("active_window"):  parts.append(f"Active window: {aw['active_window']}")
            if aw.get("vision_summary"): parts.append(f"Screen summary: {aw['vision_summary']}")
            if aw.get("distraction_level") not in ("", "none", None):
                parts.append(f"Distraction level: {aw['distraction_level']}")
            if parts:
                awareness_block = "\n[SITUATIONAL AWARENESS]\n" + "\n".join(f"- {p}" for p in parts)

        # ── Relevant memories ──────────────────────────────────────────────────
        memory_block = ""
        if self.memory:
            memory_ctx = self.memory.build_memory_context(user_input)
            if memory_ctx:
                memory_block = "\n" + memory_ctx

        # ── Extra context (caller-supplied) ────────────────────────────────────
        context_block = f"\n[CONTEXT]\n{context}" if context else ""

        # ── Conversation history ───────────────────────────────────────────────
        history_str = ""
        for msg in self.conversation_history:
            label = "User" if msg["role"] == "user" else "Makima"
            history_str += f"{label}: {msg['content']}\n"

        full_prompt = (
            f"{system}"
            f"{awareness_block}"
            f"{memory_block}"
            f"{context_block}"
            f"\n--- Conversation ---\n{history_str}"
            f"User: {user_input}\nMakima:"
        )
        return full_prompt

    def _parse_response(self, raw: str) -> tuple[str, str]:
        """
        Extract (reply_text, emotion) from a JSON response.
        Falls back gracefully if the model returns plain text.
        Returns: (reply: str, emotion: str)
        """
        import re
        try:
            clean = raw.replace("```json", "").replace("```", "").strip()
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                reply   = str(data.get("reply") or data.get("message") or clean)
                emotion = str(data.get("emotion") or "neutral").lower()
                return reply, emotion
            return clean, "neutral"
        except Exception:
            return raw, "neutral"

    # ─── Gemini Backend ───────────────────────────────────────────────────────

    def _is_gemini_available(self) -> bool:
        if not self.gemini_enabled or not self.gemini_client:
            return False
        if self.gemini_fail_count >= self.GEMINI_FAIL_THRESHOLD:
            if time.time() < self.gemini_cooldown_until:
                return False
            else:
                # Reset after cooldown
                logger.info("Gemini cooldown expired. Re-enabling.")
                self.gemini_fail_count = 0
        return True

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """
        Call Gemini via the google-genai Client SDK (v1+).
        Prepends persona-specific few-shot examples as multi-turn history,
        then appends the current prompt as the final user turn.
        Requests JSON response mode so the model reliably outputs {emotion, reply}.
        """
        try:
            # Build multi-turn content list: few-shot examples + current prompt
            examples = FEW_SHOT_EXAMPLES.get(self.persona, [])
            contents = []
            for ex in examples:
                role  = ex["role"]           # "user" | "model"
                text  = ex["parts"][0]       # plain string in our few-shot dicts
                contents.append({"role": role, "parts": [{"text": text}]})
            # Final user turn = the fully-built prompt (persona + awareness + history)
            contents.append({"role": "user", "parts": [{"text": prompt}]})

            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=contents,
                config={"response_mime_type": "application/json"},
            )
            self.gemini_fail_count = 0
            return response.text.strip()
        except Exception as e:
            self.gemini_fail_count += 1
            logger.warning(f"Gemini error ({self.gemini_fail_count}/{self.GEMINI_FAIL_THRESHOLD}): {e}")
            if self.gemini_fail_count >= self.GEMINI_FAIL_THRESHOLD:
                self.gemini_cooldown_until = time.time() + self.GEMINI_COOLDOWN_SECONDS
                logger.warning(f"Gemini disabled for {self.GEMINI_COOLDOWN_SECONDS}s.")
            return None

    # ─── Ollama Backend ───────────────────────────────────────────────────

    def _call_ollama(self, user_input: str, context: str = "") -> Optional[str]:
        """
        Call Ollama via the `ollama` Python package.
        makima-v3 already has personality in its Modelfile — injecting PERSONAS["makima"]
        again as system causes the small model to regurgitate it as output.
        Only inject a minimal JSON-format reminder + awareness.
        """
        awareness_lines = []
        if self.awareness_context:
            aw = self.awareness_context
            if aw.get("active_window"): awareness_lines.append(f"Active window: {aw['active_window']}")
            if aw.get("vision_summary"): awareness_lines.append(f"Screen: {aw['vision_summary']}")
            if aw.get("last_emotion"):  awareness_lines.append(f"Last emotion: {aw['last_emotion']}")

        system = PERSONAS.get(self.persona, PERSONAS["makima"])
        system_parts = [
            system,
            'Respond ONLY with valid JSON: {"emotion": "<token>", "reply": "<text>"}',
            "Emotion tokens: neutral, happy, focused, mysterious, concerned, amused, playful, sad.",
        ]
        if awareness_lines:
            system_parts.append("[Context]\n" + "\n".join(f"- {l}" for l in awareness_lines))
        
        if self.memory:
            memory_ctx = self.memory.build_memory_context(user_input)
            if memory_ctx:
                system_parts.append(memory_ctx)
        
        if context:
            system_parts.append(f"[Extra]\n{context}")

        messages = [{"role": "system", "content": "\n".join(system_parts)}]
        for msg in self.conversation_history[-8:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_input})


        # ── ollama Python package (preferred) ─────────────────────────────
        if OLLAMA_AVAILABLE:
            try:
                response = _ollama.chat(
                    model=self.ollama_model,
                    messages=messages,
                    format="json",
                    options={"temperature": 0.3, "num_predict": 512},
                )
                return response["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"Ollama (package) error: {e}")
                # fall through to HTTP fallback

        # ── HTTP /api/chat fallback ────────────────────────────────────
        if not REQUESTS_AVAILABLE:
            return None
        try:
            base = self.ollama_url.rstrip("/").replace("/api/generate", "")
            resp = _requests.post(
                f"{base}/api/chat",
                json={"model": self.ollama_model, "messages": messages,
                      "stream": False, "format": "json",
                      "options": {"temperature": 0.3, "num_predict": 512}},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"Ollama (HTTP) error: {e}")
            return None

    # ─── Public Chat Interface ────────────────────────────────────────────────

    def chat(self, user_input: str, context: str = "") -> tuple[str, str]:
        """
        Send user input to AI and return (reply_text, emotion).
        Tries Gemini first (using full built prompt for best context),
        falls back to Ollama (passing raw user_input to avoid double-persona injection).
        """
        raw = None

        if self._is_gemini_available():
            # Gemini handles inline system prompts fine — use full built prompt
            prompt = self._build_prompt(user_input, context)
            raw = self._call_gemini(prompt)
            if raw:
                logger.debug("Response from Gemini.")

        if not raw:
            # Ollama builds its own messages array internally — pass raw user_input only
            raw = self._call_ollama(user_input, context)
            if raw:
                logger.debug("Response from Ollama.")

        if not raw:
            raw = '{"emotion": "concerned", "reply": "I\'m having trouble reaching my AI brain. Check internet or Ollama."}'

        reply, emotion = self._parse_response(raw)

        # Store only plain text in history (not JSON)
        self.add_to_history("user", user_input)
        self.add_to_history("assistant", reply)

        return reply, emotion

    def code_chat(self, task: str, context: str = "") -> str:
        """
        Handle a code task using the 'coder' persona — sharp, precise, no fluff.
        Temporarily switches persona to 'coder', runs the request, then restores.
        Returns plain text reply (no emotion token).
        """
        saved_persona = self.persona
        self.persona = "coder"
        try:
            # Prepend context if provided (e.g. pasted code, error message)
            full_input = task
            if context:
                full_input = f"{context}\n\n{task}"
            raw = None
            if self._is_gemini_available():
                prompt = self._build_prompt(full_input, "")
                raw = self._call_gemini(prompt)
            if not raw:
                raw = self._call_ollama(full_input, "")
            if not raw:
                return "I couldn\'t reach my AI brain right now. Check Ollama or your internet."
            reply, _ = self._parse_response(raw)
            return reply
        finally:
            self.persona = saved_persona   # always restore

    def set_persona(self, persona: str) -> str:
        """Switch persona mode and reset conversation history."""
        if persona in PERSONAS:
            self.persona = persona
            self.clear_history()
            labels = {"makima": "Makima mode — sharp and present.",
                      "normal": "Normal mode — clear and efficient.",
                      "date":   "Date mode — warm and close."}
            return labels.get(persona, f"Switched to {persona} mode.")
        return f"Unknown persona '{persona}'. Available: {', '.join(PERSONAS.keys())}"

    def get_status(self) -> dict:
        return {
            "gemini_enabled": self.gemini_enabled,
            "gemini_available": self._is_gemini_available(),
            "gemini_fails": self.gemini_fail_count,
            "ollama_model": self.ollama_model,
            "persona": self.persona,
            "history_turns": len(self.conversation_history) // 2,
        }

    def generate_response(self, system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
        """Raw generation bypass for agents/extractors that need pure text."""
        prompt = f"{system_prompt}\n\nUser: {user_message}"
        if self._is_gemini_available():
            contents = [{"role": "user", "parts": [{"text": prompt}]}]
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=contents,
                )
                return response.text.strip()
            except Exception as e:
                logger.warning(f"generate_response Gemini error: {e}")

        # Fallback to Ollama using module-level imports
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            if OLLAMA_AVAILABLE:
                response = _ollama.chat(
                    model=self.ollama_model,
                    messages=messages,
                    options={"temperature": temperature}
                )
                return response["message"]["content"].strip()
            elif REQUESTS_AVAILABLE:
                base = self.ollama_url.rstrip("/")
                resp = _requests.post(f"{base}/api/chat", json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature}
                }, timeout=30)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"generate_response Ollama error: {e}")
        return ""
