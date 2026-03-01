"""
core/claude_coder.py

Claude Code Editor — Anthropic API Integration
───────────────────────────────────────────────
Routes write_code / debug / explain-code tasks to Claude (claude-haiku-4-5 by default).
Stays completely invisible to the rest of Makima — just returns a plain string reply
that slots in wherever the AI would have answered.

HOW TO ACTIVATE
───────────────
1. Get a free API key:   https://console.anthropic.com
2. Add to your .env:     ANTHROPIC_API_KEY=sk-ant-...
3. (Optional) model:     CLAUDE_CODE_MODEL=claude-haiku-4-5-20251001
   Default is claude-haiku-4-5 (fast + cheap).
   Upgrade to claude-sonnet-4-6 for harder problems.

That's it. Makima auto-detects the key on startup and routes code tasks here.

WHAT IT HANDLES
───────────────
Intent type "write_code" triggers when user says things like:
  "write a function to…"        "code a class that…"
  "create a script to…"         "implement a …"
  "fix this code: …"            "debug: …"
  "explain this code: …"        "refactor: …"
  "what does this code do?"     "add docstrings to: …"

FALLBACK CHAIN
──────────────
Claude (Anthropic) → Gemini → Ollama → Error message
If ANTHROPIC_API_KEY is not set, this module does nothing and
the write_code intent falls through to the normal agent pipeline.
"""

import os
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("Makima.ClaudeCoder")

# ── Anthropic client (optional) ───────────────────────────────────────────────

try:
    import anthropic as _anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    _anthropic = None
    ANTHROPIC_AVAILABLE = False
    logger.debug("anthropic package not installed. Run: pip install anthropic")


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MODEL   = "claude-haiku-4-5-20251001"     # fast + very cheap
SMART_MODEL     = "claude-sonnet-4-6"              # stronger, for complex tasks
MAX_TOKENS      = 4096
TIMEOUT_SECONDS = 45

# Tasks above this complexity threshold are routed to the smarter model
COMPLEXITY_THRESHOLD = 100   # character count of user message


# ── System prompt injected for every code request ─────────────────────────────

CODE_SYSTEM_PROMPT = """You are Makima's code editor — a sharp, precise coding assistant
integrated into a personal AI assistant called Makima.

RULES:
1. Reply ONLY with code + brief explanations. No fluff, no greetings.
2. Always use code blocks with the correct language tag (```python, ```js, etc.)
3. If asked to fix/debug code, explain the bug in one sentence then show the fix.
4. If asked to explain code, be concise — bullet points over paragraphs.
5. Include type hints and docstrings for Python functions.
6. If the task is ambiguous, implement the most reasonable interpretation and
   add a comment noting what you assumed.
7. Never refuse a coding task — if something is risky, add a safety comment in code.

OUTPUT FORMAT:
- For write/create tasks:   working code block, then 1-2 sentence summary
- For debug/fix tasks:      bug description, then fixed code block
- For explain tasks:        bullet-point breakdown, no code block needed unless example helps
- For refactor tasks:       refactored code, then diff summary (what changed and why)
"""


# ── Main class ────────────────────────────────────────────────────────────────

class ClaudeCoder:
    """
    Specialized Claude backend for code generation, debugging, and explanation.
    Drop-in for any code-related task in Makima.
    """

    def __init__(self):
        self._client: Optional[object] = None
        self._api_key: str = ""
        self._model: str = os.getenv("CLAUDE_CODE_MODEL", DEFAULT_MODEL)
        self._fail_count: int = 0
        self._last_fail_time: float = 0.0
        self._cooldown_seconds: int = 60
        self._request_count: int = 0

        self._init_client()

    # ── Initialization ────────────────────────────────────────────────────────

    def _init_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            logger.info("ANTHROPIC_API_KEY not set — Claude Coder inactive.")
            return

        if not ANTHROPIC_AVAILABLE:
            logger.warning(
                "anthropic package not installed.\n"
                "Run:  pip install anthropic\n"
                "Then restart Makima."
            )
            return

        try:
            self._client = _anthropic.Anthropic(api_key=api_key)
            self._api_key = api_key
            logger.info(f"✅ Claude Coder ready  (model: {self._model})")
        except Exception as e:
            logger.warning(f"Claude Coder init failed: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if the API key is set and client initialized."""
        return self._client is not None

    def handle_code_task(self, task: str, context: str = "") -> Optional[str]:
        """
        Main entry point. Call this for any write_code / debug / explain task.

        Args:
            task:    The user's request ("write a function to sort by date")
            context: Optional extra context (file content, error message, etc.)

        Returns:
            Claude's response as a plain string, or None if unavailable.
        """
        if not self.available:
            return None

        # Cooldown: if we've failed recently, don't hammer the API
        if self._fail_count >= 3:
            if time.time() - self._last_fail_time < self._cooldown_seconds:
                logger.warning("Claude Coder in cooldown after repeated failures.")
                return None
            else:
                self._fail_count = 0   # reset after cooldown

        # Choose model based on task complexity
        model = self._pick_model(task)

        # Build the message list
        messages = self._build_messages(task, context)

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=CODE_SYSTEM_PROMPT,
                messages=messages,
            )
            self._request_count += 1
            self._fail_count = 0
            result = response.content[0].text.strip()
            logger.debug(f"Claude Coder ✅  ({model}, {response.usage.input_tokens} in / {response.usage.output_tokens} out tokens)")
            return result

        except Exception as e:
            self._fail_count += 1
            self._last_fail_time = time.time()
            logger.warning(f"Claude Coder error ({type(e).__name__}): {e}")
            return None

    def handle_with_file(self, task: str, file_content: str, filename: str = "") -> Optional[str]:
        """
        Code task that includes a file to work on.
        e.g. "fix the bugs in this file" + file content

        Args:
            task:         What to do with the file
            file_content: The actual file content as a string
            filename:     Optional filename hint (helps with language detection)
        """
        context = f"File: {filename}\n\n```\n{file_content}\n```" if filename else f"```\n{file_content}\n```"
        full_task = f"{task}\n\nHere is the code:\n\n{context}"
        return self.handle_code_task(full_task)

    def debug(self, code: str, error: str = "") -> Optional[str]:
        """Shortcut: debug a specific piece of code."""
        task = "Debug this code and fix all errors."
        if error:
            task += f"\n\nError message:\n```\n{error}\n```"
        task += f"\n\nCode:\n```\n{code}\n```"
        return self.handle_code_task(task)

    def explain(self, code: str) -> Optional[str]:
        """Shortcut: explain what a piece of code does."""
        return self.handle_code_task(f"Explain what this code does, step by step:\n```\n{code}\n```")

    def refactor(self, code: str, instructions: str = "") -> Optional[str]:
        """Shortcut: refactor/improve code."""
        task = f"Refactor this code to improve readability and performance."
        if instructions:
            task += f" Specifically: {instructions}"
        task += f"\n```\n{code}\n```"
        return self.handle_code_task(task)

    def get_status(self) -> dict:
        return {
            "available": self.available,
            "model": self._model,
            "requests_made": self._request_count,
            "fail_count": self._fail_count,
            "package_installed": ANTHROPIC_AVAILABLE,
            "api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _pick_model(self, task: str) -> str:
        """Use the smarter model for longer / more complex tasks."""
        if len(task) > COMPLEXITY_THRESHOLD:
            return SMART_MODEL
        # Keywords that suggest harder tasks
        complex_keywords = [
            "architecture", "design pattern", "async", "concurrent",
            "optimize", "performance", "algorithm", "entire", "full project",
            "from scratch", "class hierarchy", "database", "api endpoint",
        ]
        if any(kw in task.lower() for kw in complex_keywords):
            return SMART_MODEL
        return self._model

    def _build_messages(self, task: str, context: str) -> list:
        messages = []
        if context:
            # Context as a preceding "user" turn with assistant acknowledgment
            messages.append({"role": "user",      "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "Got it. What do you need?"})
        messages.append({"role": "user", "content": task})
        return messages


# ── Module-level singleton (lazy init) ───────────────────────────────────────

_instance: Optional[ClaudeCoder] = None

def get_claude_coder() -> ClaudeCoder:
    """Get or create the shared ClaudeCoder instance."""
    global _instance
    if _instance is None:
        _instance = ClaudeCoder()
    return _instance


def handle_code_task(task: str, context: str = "") -> Optional[str]:
    """Convenience function — call this from anywhere in Makima."""
    return get_claude_coder().handle_code_task(task, context)
