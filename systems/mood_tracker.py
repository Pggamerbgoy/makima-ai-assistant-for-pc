"""
systems/mood_tracker.py

Mood Tracker — Text-Based Emotional Intelligence
──────────────────────────────────────────────────
Tracks the user's emotional state from their text/voice input.
No extra libraries needed — pure text analysis.

What it does:
  - Detects mood from keywords, punctuation, message length, time of day
  - Maintains a rolling mood history across the session
  - Adapts Makima's responses (prefix, tone hint) to match
  - Logs mood trends so Makima can notice patterns ("you seem stressed on Mondays")
  - Triggers proactive check-ins when mood is consistently low

Commands (wired via command_router):
  "how am I feeling?" / "my mood"        → summary of your session mood
  "mood history"                          → trend over last N sessions
  "I'm feeling stressed / tired / happy"  → explicit mood set

Usage:
    from systems.mood_tracker import MoodTracker
    tracker = MoodTracker()
    result = tracker.analyze("ugh this stupid bug won't fix")
    # result.emotion   → "frustrated"
    # result.prefix    → "Take a breath — I've got this with you. "
    # result.intensity → 0.7
"""

import json
import os
import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from collections import deque, Counter

logger = logging.getLogger("Makima.MoodTracker")

MOOD_LOG_FILE = "makima_memory/mood_log.json"
MAX_MOOD_HISTORY = 200   # entries kept on disk
SESSION_WINDOW   = 10    # last N messages used for session mood


# ── Keyword maps ──────────────────────────────────────────────────────────────

MOOD_KEYWORDS: dict[str, list[str]] = {
    "happy": [
        "happy", "great", "awesome", "amazing", "love", "yay", "haha", "lol",
        "excited", "fantastic", "wonderful", "brilliant", "perfect", "nice",
        "good", "glad", "excellent", "yes!", "nailed it", "got it", "done!"
    ],
    "sad": [
        "sad", "depressed", "unhappy", "crying", "cry", "miss", "lonely",
        "heartbroken", "hopeless", "down", "low", "dull", "gloomy", "upset",
        "disappointed", "sigh", "😢", "😔"
    ],
    "stressed": [
        "stressed", "stress", "overwhelmed", "too much", "can't handle",
        "deadline", "behind", "panic", "anxious", "anxiety", "pressure",
        "overloaded", "drowning", "barely", "no time", "running out"
    ],
    "frustrated": [
        "ugh", "argh", "wtf", "damn", "broken", "stupid", "doesn't work",
        "not working", "bug", "error", "failed", "keeps failing", "again",
        "seriously", "why won't", "can't believe", "annoying", "hate this"
    ],
    "tired": [
        "tired", "exhausted", "sleepy", "sleep", "fatigue", "drained",
        "worn out", "need rest", "need a break", "burned out", "burnout",
        "yawning", "can barely", "barely awake", "been awake"
    ],
    "excited": [
        "!", "can't wait", "so cool", "incredible", "let's go", "hyped",
        "pumped", "wow", "omg", "insane", "mind blown", "finally!", "woo",
        "this is huge", "big news", "just finished"
    ],
    "calm": [
        "okay", "alright", "sure", "fine", "sounds good", "no problem",
        "understood", "got it", "makes sense", "I see", "cool"
    ],
    "curious": [
        "wondering", "curious", "interesting", "how does", "why does",
        "what if", "tell me more", "explain", "can you", "I want to know",
        "never thought", "hadn't considered"
    ],
}

# How strongly each emotion is weighted
MOOD_WEIGHTS = {
    "happy":      1.0,
    "sad":        1.2,
    "stressed":   1.3,
    "frustrated": 1.2,
    "tired":      1.1,
    "excited":    1.0,
    "calm":       0.8,
    "curious":    0.8,
    "neutral":    0.5,
}

# Makima's response prefixes per mood (injected before her reply)
MOOD_RESPONSE_PREFIXES = {
    "happy":      "",
    "sad":        "Hey. I noticed you seem a little down. ",
    "stressed":   "Take a breath — I've got you. ",
    "frustrated": "I hear you, that's genuinely annoying. ",
    "tired":      "Quick answer since you sound drained: ",
    "excited":    "",
    "calm":       "",
    "curious":    "",
    "neutral":    "",
}

# Proactive check-in messages (triggered after sustained low mood)
CHECKIN_MESSAGES = {
    "stressed":   "You've seemed stressed for a while. Want to talk about it, or just take a quick break?",
    "tired":      "You've mentioned feeling tired a few times. Are you getting enough sleep?",
    "sad":        "I've noticed you seem a bit low today. I'm here if you want to talk.",
    "frustrated": "Things seem to be fighting back today. Want to step away for a bit?",
}


@dataclass
class MoodResult:
    emotion: str
    intensity: float       # 0.0 – 1.0
    prefix: str            # prepend to Makima's response
    should_checkin: bool   # trigger proactive check-in?
    checkin_message: str   # what to say if check-in fires

    def __repr__(self):
        return f"MoodResult(emotion={self.emotion!r}, intensity={self.intensity:.2f})"


class MoodTracker:
    """Tracks user mood from text and adapts Makima's tone accordingly."""

    def __init__(self):
        os.makedirs("makima_memory", exist_ok=True)
        self._session_moods: deque[str] = deque(maxlen=SESSION_WINDOW)
        self._mood_timestamps: deque[float] = deque(maxlen=SESSION_WINDOW)
        self._history: list[dict] = self._load_history()
        self._last_checkin_emotion: Optional[str] = None
        self._last_checkin_time: float = 0.0
        self.current_emotion: str = "neutral"
        self.current_intensity: float = 0.0
        logger.info(f"🎭 MoodTracker ready. {len(self._history)} mood entries loaded.")

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> MoodResult:
        """Analyze text and return a MoodResult with tone adaptation hints."""
        emotion, intensity = self._detect_emotion(text)
        self._record(emotion, intensity)

        prefix = MOOD_RESPONSE_PREFIXES.get(emotion, "")
        checkin, checkin_msg = self._should_checkin(emotion)

        self.current_emotion = emotion
        self.current_intensity = intensity

        return MoodResult(
            emotion=emotion,
            intensity=intensity,
            prefix=prefix,
            should_checkin=checkin,
            checkin_message=checkin_msg,
        )

    def set_emotion(self, emotion: str) -> str:
        """Explicitly set mood (from user saying 'I'm feeling stressed')."""
        emotion = emotion.lower().strip()
        known = list(MOOD_KEYWORDS.keys()) + ["neutral"]
        if emotion not in known:
            # Try fuzzy match
            for k in known:
                if k in emotion or emotion in k:
                    emotion = k
                    break
            else:
                emotion = "neutral"
        self._record(emotion, 0.8)
        self.current_emotion = emotion
        responses = {
            "stressed":   "I hear you. Let me know if you want to slow down or take a break.",
            "tired":      "Got it. I'll keep my answers shorter for now.",
            "sad":        "I'm here. Talk to me whenever you're ready.",
            "frustrated": "Noted. Let's work through it together.",
            "happy":      "Good! Let's make the most of it.",
            "excited":    "That energy is contagious. Let's go!",
        }
        return responses.get(emotion, f"Okay, I've noted that you're feeling {emotion}.")

    def get_session_summary(self) -> str:
        """Return a human-readable summary of this session's mood."""
        if not self._session_moods:
            return "No mood data yet for this session."
        counter = Counter(self._session_moods)
        dominant = counter.most_common(1)[0][0]
        distribution = ", ".join(f"{e}: {c}" for e, c in counter.most_common())
        trend = self._get_trend()
        return (
            f"This session you've mostly seemed {dominant}. "
            f"({distribution}). {trend}"
        )

    def get_history_summary(self, days: int = 7) -> str:
        """Return mood trends over the last N days."""
        cutoff = time.time() - (days * 86400)
        recent = [e for e in self._history if e.get("timestamp", 0) > cutoff]
        if not recent:
            return f"No mood data from the last {days} days."
        counter = Counter(e["emotion"] for e in recent)
        dominant = counter.most_common(1)[0][0]
        total = len(recent)
        return (
            f"Over the last {days} days ({total} data points), "
            f"you've most often seemed {dominant}. "
            + ", ".join(f"{e}: {c/total:.0%}" for e, c in counter.most_common(3))
        )

    # ── Detection ─────────────────────────────────────────────────────────────

    def _detect_emotion(self, text: str) -> tuple[str, float]:
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for emotion, keywords in MOOD_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits:
                base = hits / len(keywords)
                scores[emotion] = base * MOOD_WEIGHTS.get(emotion, 1.0)

        # Punctuation signals
        if text.count("!") >= 2:
            scores["excited"] = scores.get("excited", 0) + 0.2
        if text.count("?") >= 2:
            scores["curious"] = scores.get("curious", 0) + 0.15
        if "..." in text or text.endswith(".."):
            scores["sad"] = scores.get("sad", 0) + 0.1

        # Very short messages → probably terse / neutral or tired
        if len(text.split()) <= 3:
            scores["neutral"] = scores.get("neutral", 0) + 0.3

        # Caps lock → frustrated or excited
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.5 and len(text) > 5:
            scores["frustrated"] = scores.get("frustrated", 0) + 0.25

        if not scores:
            return "neutral", 0.3

        best = max(scores, key=scores.get)
        intensity = min(scores[best] * 3, 1.0)  # scale 0–1
        return best, intensity

    # ── Recording ─────────────────────────────────────────────────────────────

    def _record(self, emotion: str, intensity: float):
        now = time.time()
        self._session_moods.append(emotion)
        self._mood_timestamps.append(now)

        entry = {
            "timestamp": now,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "emotion": emotion,
            "intensity": round(intensity, 2),
        }
        self._history.append(entry)
        if len(self._history) > MAX_MOOD_HISTORY:
            self._history = self._history[-MAX_MOOD_HISTORY:]
        self._save_history()

    def _should_checkin(self, current_emotion: str) -> tuple[bool, str]:
        """Return (should_fire, message) for a proactive check-in."""
        checkin_emotions = {"stressed", "tired", "sad", "frustrated"}
        if current_emotion not in checkin_emotions:
            return False, ""

        # Require 3 consecutive low-mood messages before checking in
        recent = list(self._session_moods)[-4:]
        sustained = sum(1 for e in recent if e == current_emotion)
        if sustained < 3:
            return False, ""

        # Cooldown: don't check in more than once per 10 minutes on same emotion
        now = time.time()
        if (self._last_checkin_emotion == current_emotion and
                now - self._last_checkin_time < 600):
            return False, ""

        self._last_checkin_emotion = current_emotion
        self._last_checkin_time = now
        msg = CHECKIN_MESSAGES.get(current_emotion, "")
        return bool(msg), msg

    def _get_trend(self) -> str:
        moods = list(self._session_moods)
        if len(moods) < 4:
            return ""
        first_half  = Counter(moods[:len(moods)//2])
        second_half = Counter(moods[len(moods)//2:])
        neg = {"stressed", "sad", "frustrated", "tired"}
        pos = {"happy", "excited", "calm", "curious"}
        neg_before = sum(first_half[e] for e in neg)
        neg_after  = sum(second_half[e] for e in neg)
        pos_before = sum(first_half[e] for e in pos)
        pos_after  = sum(second_half[e] for e in pos)
        if neg_after < neg_before and pos_after >= pos_before:
            return "Your mood seems to be improving as the session goes on."
        if neg_after > neg_before:
            return "You seem to be getting a bit more tense — want a break?"
        return ""

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_history(self) -> list:
        if os.path.exists(MOOD_LOG_FILE):
            try:
                return json.loads(open(MOOD_LOG_FILE, encoding="utf-8").read())
            except Exception:
                pass
        return []

    def _save_history(self):
        try:
            json.dump(self._history, open(MOOD_LOG_FILE, "w", encoding="utf-8"), indent=2)
        except Exception as e:
            logger.warning(f"Mood log save error: {e}")
