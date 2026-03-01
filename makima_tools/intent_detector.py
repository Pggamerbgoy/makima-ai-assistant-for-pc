"""
TOOL: Intent Detector
──────────────────────────────────────────────
Figures out EXACTLY what the user wants before
routing the command — stops Makima from asking
unnecessary clarifying questions.

Detects: intent type, entities, confidence, missing slots.

USAGE in command_router.py:
    from tools.intent_detector import IntentDetector
    detector = IntentDetector()

    intent = detector.detect("play something chill")
    # intent.type     → "play_music"
    # intent.entities → {"mood": "chill"}
    # intent.confidence → 0.92
    # intent.missing  → []   ← nothing missing, just execute!
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# ── Intent definitions ────────────────────────────────────────────────────────

INTENTS = {
    "play_music": {
        "patterns": ["play", "music", "song", "track", "playlist", "spotify",
                     "put on", "queue", "some music", "on spotify", "play some"],
        "entities": ["artist", "genre", "mood", "song_name"],
        "required": [],
        "examples": ["play something chill", "put on metallica", "play some music on spotify"]
    },
    "open_app": {
        "patterns": ["open", "launch", "start", "run", "switch to",
                     "open up", "fire up", "bring up", "load", "for me"],
        "entities": ["app_name"],
        "required": ["app_name"],
        "examples": ["open chrome", "launch vscode", "open google chrome for me"]
    },
    "close_app": {
        "patterns": ["close", "quit", "exit", "kill", "shut down", "terminate", "stop"],
        "entities": ["app_name"],
        "required": ["app_name"],
        "examples": ["close spotify", "quit chrome", "exit vscode"]
    },
    "send_email": {
        "patterns": ["email", "send", "mail", "write to", "message"],
        "entities": ["recipient", "subject", "body"],
        "required": ["recipient"],
        "examples": ["email john about the meeting", "send a mail to boss"]
    },
    "search_web": {
        "patterns": ["search", "google", "look up", "find", "search for", "browse", "look online", "find me"],
        "entities": ["query"],
        "required": ["query"],
        "examples": ["search python decorators", "what is quantum computing"]
    },
    "set_reminder": {
        "patterns": ["remind", "reminder", "alert", "notify", "don't let me forget"],
        "entities": ["task", "time", "date"],
        "required": ["task"],
        "examples": ["remind me to call mom at 6pm", "set a reminder for the meeting"]
    },
    "file_operation": {
        "patterns": ["open file", "find file", "save", "create", "delete", "move", "copy", "folder"],
        "entities": ["filename", "operation", "destination"],
        "required": ["filename"],
        "examples": ["open report.pdf", "find my resume", "save this as notes.txt"]
    },
    "write_code": {
        "patterns": ["code", "write a", "create a script", "program", "function", "class", "implement"],
        "entities": ["language", "task_description"],
        "required": ["task_description"],
        "examples": ["write a python function to sort a list", "create a web scraper"]
    },
    "get_info": {
        "patterns": ["what", "how", "why", "when", "where", "explain", "tell me",
                     "describe", "define", "what time", "what is", "what are",
                     "how do", "how does", "can you tell", "do you know"],
        "entities": ["topic"],
        "required": ["topic"],
        "examples": ["explain async await", "what is the capital of France", "what time is it"]
    },
    "system_control": {
        "patterns": ["volume", "brightness", "shutdown", "restart", "sleep", "lock", "screenshot", "wifi"],
        "entities": ["action", "value"],
        "required": ["action"],
        "examples": ["increase volume", "take a screenshot", "lock the screen"]
    },
    "calendar": {
        "patterns": ["schedule", "meeting", "appointment", "calendar", "event", "book", "free time"],
        "entities": ["event_name", "time", "date", "duration"],
        "required": [],
        "examples": ["schedule a meeting tomorrow at 3pm", "what's on my calendar today"]
    },
    "chat": {
        "patterns": ["hi", "hello", "hey", "how are you", "what's up", "talk", "chat"],
        "entities": [],
        "required": [],
        "examples": ["hey makima", "how are you doing"]
    }
}

# Entity extraction patterns
ENTITY_PATTERNS = {
    "time": r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight|morning|evening|night|tonight)\b',
    "date": r'\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next\s+\w+|\d{1,2}[/-]\d{1,2})\b',
    "duration": r'\b(\d+\s*(?:minute|min|hour|hr|second|sec)s?)\b',
    "number": r'\b(\d+(?:\.\d+)?)\b',
    "email_addr": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
}

MOOD_KEYWORDS = {
    "happy": ["happy", "upbeat", "cheerful", "fun", "party"],
    "chill": ["chill", "relaxed", "calm", "mellow", "lofi", "lo-fi", "soft"],
    "focus": ["focus", "concentrate", "work", "study", "deep work"],
    "hype": ["hype", "pump", "energy", "workout", "intense", "aggressive"],
    "sad": ["sad", "melancholy", "emotional", "heartbreak"]
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class Intent:
    type: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    raw: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""

    def __str__(self):
        return (
            f"Intent({self.type}, "
            f"conf={self.confidence:.0%}, "
            f"entities={self.entities}, "
            f"missing={self.missing})"
        )


# ── Detector ──────────────────────────────────────────────────────────────────

class IntentDetector:

    def detect(self, text: str) -> Intent:
        """
        Main entry point.
        Returns Intent object with everything Makima needs to act immediately.
        """
        text_lower = text.lower().strip()

        # Score all intents
        scores = {}
        for intent_name, intent_def in INTENTS.items():
            score = self._score_intent(text_lower, intent_def["patterns"])
            scores[intent_name] = score

        # Priority overrides — explicit trigger words always win
        OPEN_TRIGGERS = ["open ", "launch ", "start ", "fire up ", "load "]
        CLOSE_TRIGGERS = ["close ", "quit ", "exit ", "kill ", "stop "]
        INFO_TRIGGERS = ["what is ", "what are ", "what time", "how does ", "how do ", "explain "]

        if any(text_lower.startswith(t) for t in OPEN_TRIGGERS):
            scores["open_app"] = max(scores["open_app"], 0.92)
        if any(text_lower.startswith(t) for t in CLOSE_TRIGGERS):
            scores["close_app"] = max(scores.get("close_app", 0), 0.92)
        if any(t in text_lower for t in INFO_TRIGGERS):
            scores["get_info"] = max(scores["get_info"], 0.88)

        # Pick best match
        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]

        # Fallback for very low confidence
        if confidence < 0.15:
            best_intent = "chat"
            confidence = 0.5

        # Extract entities
        entities = self._extract_entities(text_lower, text, INTENTS[best_intent]["entities"])

        # Check what's missing
        required = INTENTS[best_intent].get("required", [])
        missing = [r for r in required if r not in entities]

        # Should Makima ask for clarification?
        needs_clarification = len(missing) > 0 and confidence < 0.9

        clarification = ""
        if needs_clarification and missing:
            clarification = self._build_clarification(best_intent, missing, entities)

        return Intent(
            type=best_intent,
            confidence=confidence,
            entities=entities,
            missing=missing,
            raw=text,
            needs_clarification=needs_clarification,
            clarification_question=clarification
        )

    def _score_intent(self, text: str, patterns: List[str]) -> float:
        score = 0.0
        words = text.split()
        matched = 0

        for pattern in patterns:
            if pattern in text:
                # Multi-word phrase match scores highest
                score += 1.0 if len(pattern.split()) > 1 else 0.7
                matched += 1
            elif any(pattern in w for w in words):
                score += 0.45
                matched += 1

        if matched == 0:
            return 0.0

        # Normalize by matched count, NOT total patterns
        # 1 strong hit = high confidence, not diluted by unmatched patterns
        normalized = score / matched

        # Bonus if multiple patterns matched (more evidence = more confidence)
        coverage_bonus = min(matched / len(patterns), 1.0) * 0.25

        return min(normalized + coverage_bonus, 1.0)

    def _extract_entities(self, text_lower: str, text_original: str, entity_types: List[str]) -> Dict:
        entities = {}

        for entity in entity_types:
            # Time
            if entity == "time":
                m = re.search(ENTITY_PATTERNS["time"], text_lower)
                if m:
                    entities["time"] = m.group(1)

            # Date
            elif entity == "date":
                m = re.search(ENTITY_PATTERNS["date"], text_lower, re.IGNORECASE)
                if m:
                    entities["date"] = m.group(1)

            # Mood (for music)
            elif entity == "mood":
                for mood, keywords in MOOD_KEYWORDS.items():
                    if any(k in text_lower for k in keywords):
                        entities["mood"] = mood
                        break

            # App name (word after trigger word)
            elif entity == "app_name":
                m = re.search(r'(?:open|launch|start|run|switch to)\s+([a-zA-Z0-9_\-]+)', text_lower)
                if m:
                    entities["app_name"] = m.group(1)

            # Recipient (for email)
            elif entity == "recipient":
                m = re.search(ENTITY_PATTERNS["email_addr"], text_original)
                if m:
                    entities["recipient"] = m.group(0)
                else:
                    # Try "to [name]"
                    m = re.search(r'\bto\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b', text_lower)
                    if m:
                        entities["recipient"] = m.group(1)

            # Filename
            elif entity == "filename":
                m = re.search(r'([a-zA-Z0-9_\- ]+\.[a-zA-Z]{2,5})', text_original)
                if m:
                    entities["filename"] = m.group(1)
                else:
                    # Try "find/open [name]"
                    m = re.search(r'(?:find|open|get|load)\s+(?:my\s+)?([a-zA-Z0-9_\- ]+)', text_lower)
                    if m:
                        entities["filename"] = m.group(1).strip()

            # Task description (for reminders, code)
            elif entity in ("task", "task_description", "query", "topic"):
                # Everything after trigger words
                for trigger in ["remind me to", "remind me", "write a", "write", "search for",
                                 "search", "explain", "what is", "how to", "code", "implement"]:
                    if trigger in text_lower:
                        idx = text_lower.find(trigger) + len(trigger)
                        remainder = text_lower[idx:].strip()
                        # Remove time/date from task
                        remainder = re.sub(ENTITY_PATTERNS["time"], "", remainder, flags=re.IGNORECASE).strip()
                        remainder = re.sub(ENTITY_PATTERNS["date"], "", remainder, flags=re.IGNORECASE).strip()
                        if remainder:
                            entities[entity] = remainder
                        break

            # System action
            elif entity == "action":
                system_actions = ["volume up", "volume down", "mute", "unmute", "screenshot",
                                  "lock", "shutdown", "restart", "sleep", "brightness up", "brightness down"]
                for action in system_actions:
                    if action in text_lower:
                        entities["action"] = action
                        break

        return entities

    def _build_clarification(self, intent: str, missing: List[str], known: Dict) -> str:
        """Generate a specific, helpful clarification question."""
        questions = {
            ("send_email", "recipient"): "Who should I send this to?",
            ("set_reminder", "task"): "What should I remind you about?",
            ("file_operation", "filename"): "Which file are you referring to?",
            ("write_code", "task_description"): "What should the code do?",
            ("open_app", "app_name"): "Which app should I open?",
            ("system_control", "action"): "What should I do? (e.g. volume up, screenshot)",
        }

        key = (intent, missing[0])
        if key in questions:
            return questions[key]

        # Generic fallback
        return f"Could you clarify: {missing[0].replace('_', ' ')}?"
