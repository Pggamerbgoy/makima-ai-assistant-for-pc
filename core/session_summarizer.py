"""
core/session_summarizer.py

Session Summarizer — Keeps Makima Coherent Long-Term
──────────────────────────────────────────────────────
As conversations grow long, AI context windows fill up. This module:

  1. Detects when conversation history is getting too long
  2. Uses the AI to generate a compact summary of older turns
  3. Replaces the verbose history with: [SUMMARY] + recent turns
  4. Stores full session archives to disk

Result: Makima "remembers" arbitrarily long conversations without
token limit issues. She can reference things said hours ago.

Usage:
    from core.session_summarizer import SessionSummarizer

    summarizer = SessionSummarizer(ai_handler)
    compressed = summarizer.maybe_compress(conversation_history)
    # compressed is either the original list (if short enough)
    # or [{"role": "system", "content": "[SESSION SUMMARY]..."}, ...recent_turns]
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("Makima.SessionSummarizer")

SESSIONS_DIR = "makima_memory/sessions"
COMPRESS_THRESHOLD = 20   # compress when history exceeds this many messages
KEEP_RECENT = 8           # always keep the last N messages verbatim
SUMMARY_MAX_TOKENS = 400  # approximate target length for the summary


SUMMARY_SYSTEM_PROMPT = """You are summarizing a conversation between a user and Makima, 
their AI assistant. Create a compact but complete summary that captures:
- Key facts the user shared about themselves
- Important decisions or conclusions reached
- Tasks completed or in progress
- The overall emotional tone of the conversation
- Any explicit preferences or instructions the user gave

Keep the summary under 200 words. Write in third person from Makima's perspective.
Example: "User is a Python developer working on a web scraper. They prefer concise responses.
They asked about async programming and we covered asyncio basics. They seem focused and slightly tired."
"""


class SessionSummarizer:
    """Compresses conversation history while preserving Makima's context awareness."""

    def __init__(self, ai_handler=None):
        self.ai = ai_handler
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._compression_count = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def maybe_compress(self, history: list) -> list:
        """
        Check if history needs compression. If so, compress and return.
        Otherwise return history unchanged.

        Args:
            history: list of {"role": str, "content": str} dicts

        Returns:
            Possibly-compressed history list
        """
        if len(history) <= COMPRESS_THRESHOLD:
            return history

        logger.info(f"History has {len(history)} turns — compressing...")
        return self._compress(history)

    def summarize_session(self, history: list) -> str:
        """Generate a standalone summary of the given conversation history."""
        return self._call_ai_for_summary(history)

    def archive_session(self, history: list, session_id: str = None):
        """Save full session to disk for later reference."""
        sid = session_id or self._current_session_id
        path = os.path.join(SESSIONS_DIR, f"session_{sid}.json")
        try:
            archive = {
                "session_id": sid,
                "date": datetime.now().isoformat(),
                "turn_count": len(history),
                "history": history,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(archive, f, ensure_ascii=False, indent=2)
            logger.info(f"Session archived: {path}")
        except Exception as e:
            logger.warning(f"Archive failed: {e}")

    def load_session(self, session_id: str) -> Optional[list]:
        """Load a previously archived session."""
        path = os.path.join(SESSIONS_DIR, f"session_{session_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("history", [])
        except Exception as e:
            logger.warning(f"Session load failed: {e}")
            return None

    def list_sessions(self) -> list[dict]:
        """List available archived sessions."""
        sessions = []
        for fname in sorted(os.listdir(SESSIONS_DIR), reverse=True)[:10]:
            if fname.startswith("session_") and fname.endswith(".json"):
                path = os.path.join(SESSIONS_DIR, fname)
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "id": data.get("session_id"),
                        "date": data.get("date"),
                        "turns": data.get("turn_count"),
                    })
                except Exception:
                    pass
        return sessions

    def format_session_list(self) -> str:
        sessions = self.list_sessions()
        if not sessions:
            return "No archived sessions found."
        lines = ["Recent sessions:"]
        for s in sessions:
            lines.append(f"  • {s['date'][:10]}  ({s['turns']} turns)  ID: {s['id']}")
        return "\n".join(lines)

    # ── Core compression ──────────────────────────────────────────────────────

    def _compress(self, history: list) -> list:
        """
        Compress history:
        1. Archive the full history
        2. Summarize the older turns via AI
        3. Return [summary_system_msg] + last KEEP_RECENT turns
        """
        # Archive full history before compressing
        self.archive_session(history)

        # Split: old turns to summarize, recent turns to keep verbatim
        old_turns = history[:-KEEP_RECENT]
        recent_turns = history[-KEEP_RECENT:]

        # Generate summary of old turns
        summary_text = self._call_ai_for_summary(old_turns)
        self._compression_count += 1

        logger.info(f"Compressed {len(old_turns)} old turns into summary #{self._compression_count}.")

        # Build compressed history: summary block + recent verbatim turns
        compressed = [
            {
                "role": "system",
                "content": (
                    f"[SESSION CONTEXT — Compression #{self._compression_count}]\n"
                    f"{summary_text}\n"
                    f"[End of summary. The following are the most recent messages.]"
                )
            }
        ] + recent_turns

        return compressed

    def _call_ai_for_summary(self, history: list) -> str:
        """Call AI to summarize the given history. Returns plain text summary."""
        if not history:
            return "No conversation history to summarize."

        # Format history as readable text for the AI
        convo_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in history
            if isinstance(msg.get("content"), str)
        )

        if not self.ai:
            # Fallback: basic extractive summary
            user_msgs = [m["content"] for m in history if m.get("role") == "user"]
            topics = user_msgs[:5]
            return "User discussed: " + "; ".join(topics[:3]) + "."

        try:
            summary = self.ai.generate_response(
                system_prompt=SUMMARY_SYSTEM_PROMPT,
                user_message=f"Summarize this conversation:\n\n{convo_text}",
                temperature=0.3,
            )
            return summary.strip() if summary else self._fallback_summary(history)
        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")
            return self._fallback_summary(history)

    def _fallback_summary(self, history: list) -> str:
        """Simple extractive summary if AI is unavailable."""
        user_msgs = [m["content"] for m in history if m.get("role") == "user"]
        if not user_msgs:
            return "Earlier conversation context."
        topics = user_msgs[:5]
        return (
            f"Earlier in this session ({len(history)} messages), "
            f"the user asked about: {'; '.join(t[:80] for t in topics)}."
        )
