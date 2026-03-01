"""
systems/self_updater.py

Self-updating helper for Makima.
Safely applies code changes to local files using the existing AIHandler.

Design:
- Explicitly restricted to files under the project root.
- Always writes a single-step backup `<name>.bak` before overwriting.
- Expects the AI backend to return the FULL updated file content,
  not a diff or explanation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Any


logger = logging.getLogger("Makima.SelfUpdater")


class SelfUpdater:
    """
    Minimal, safe-ish self-update helper.

    Usage (from CommandRouter or MakimaManager):
        updater = SelfUpdater(ai_handler)
        msg = updater.update_file("core/ai_handler.py", "Change default model to gemini-2.0-pro")
    """

    def __init__(self, ai_handler: Any, project_root: Optional[str | Path] = None):
        self.ai = ai_handler
        # Default project root = repo root (parent of this file's directory)
        root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[1]
        self.project_root = root.resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def update_file(self, file_path: str, instruction: str) -> str:
        """
        Apply a high-level change to a file using the AI backend.

        file_path: relative to project root or absolute path inside it.
        instruction: natural language description of the change.
        """
        target = self._resolve_file(file_path)
        if not target:
            return f"I couldn't find a safe file at '{file_path}'."

        try:
            original = target.read_text(encoding="utf-8")
        except Exception as e:
            return f"I couldn't read '{target}': {e}"

        if not hasattr(self.ai, "generate_response"):
            return "My code editor brain isn't available (generate_response missing)."

        system_prompt = (
            "You are Makima's internal code editor.\n"
            "You receive the full contents of ONE source file and a change request.\n"
            "Your job is to return the COMPLETE UPDATED FILE TEXT with the change applied.\n"
            "Rules:\n"
            "- Preserve all existing code and formatting except where needed for the change.\n"
            "- Do NOT add explanations, comments about what you did, or markdown fences.\n"
            "- Output ONLY the raw file text that should be written to disk.\n"
        )

        user_message = (
            f"File path (for context only): {target}\n\n"
            f"Change request:\n{instruction}\n\n"
            "Current file contents:\n"
            f"{original}"
        )

        try:
            updated = self.ai.generate_response(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"SelfUpdater.generate_response failed: {e}")
            return f"I tried to update the file but my AI backend failed: {e}"

        if not isinstance(updated, str) or not updated.strip():
            return "I tried to update the file but got an empty result from my AI backend."

        backup = target.with_suffix(target.suffix + ".bak")
        try:
            if not backup.exists():
                backup.write_text(original, encoding="utf-8")
            target.write_text(updated, encoding="utf-8")
        except Exception as e:
            logger.error(f"SelfUpdater write failed for {target}: {e}")
            return f"I generated an update, but writing to '{target}' failed: {e}"

        rel = target.relative_to(self.project_root)
        return f"I've updated {rel}. A backup was saved as {backup.name}."

    # ── Internals ─────────────────────────────────────────────────────────────

    def _resolve_file(self, path_str: str) -> Optional[Path]:
        """
        Resolve a user-supplied path to a real file under project_root.
        Returns None if the path is invalid or outside the project.
        """
        raw = Path(path_str.strip())
        if not raw.is_absolute():
            raw = self.project_root / raw

        try:
            resolved = raw.resolve()
        except Exception:
            return None

        # Safety: only allow edits inside the project root
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            logger.warning(f"SelfUpdater refused path outside project root: {resolved}")
            return None

        if not resolved.exists() or not resolved.is_file():
            return None
        return resolved

