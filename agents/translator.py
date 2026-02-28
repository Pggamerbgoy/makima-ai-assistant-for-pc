"""
agents/translator.py

Real-Time Translation System
──────────────────────────────
Makima speaks and understands any language:
  - Auto-detects what language you're speaking
  - Translates your input to English for processing
  - Translates AI response back to your language
  - Supports 100+ languages via Google Translate (free) or DeepL
  - Language memory: remembers your preferred language per session
  - Side-by-side mode: shows both original + translation

Commands:
  "Translate to Hindi"
  "Speak in French"
  "Switch to Japanese"
  "Detect language"
  "Translate: [text]"
  "What language am I speaking?"
  "Turn off translation"
  "Translation status"

Supported engines:
  - googletrans (free, no API key)
  - DeepL (set DEEPL_API_KEY for higher quality)
  - LibreTranslate (self-hosted option)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger("Makima.Translator")

# Language name → code
LANGUAGE_MAP = {
    "hindi": "hi", "english": "en", "french": "fr", "spanish": "es",
    "german": "de", "japanese": "ja", "korean": "ko", "chinese": "zh-cn",
    "arabic": "ar", "portuguese": "pt", "russian": "ru", "italian": "it",
    "dutch": "nl", "turkish": "tr", "polish": "pl", "swedish": "sv",
    "bengali": "bn", "tamil": "ta", "telugu": "te", "marathi": "mr",
    "urdu": "ur", "gujarati": "gu", "punjabi": "pa", "malayalam": "ml",
    "thai": "th", "vietnamese": "vi", "indonesian": "id", "malay": "ms",
}

try:
    from googletrans import Translator as GTranslator, LANGUAGES
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False
    logger.warning("googletrans not installed. Run: pip install googletrans==4.0.0rc1")

import os
DEEPL_KEY = os.getenv("DEEPL_API_KEY", "")


class TranslationSystem:
    """Translation and language detection service."""

    def __init__(self, ai):
        self.ai = ai
        self.enabled = False
        self.target_language = "en"       # language for responses
        self.detected_language = "en"     # auto-detected from user input
        self.auto_detect = True
        self._gtrans = GTranslator() if GOOGLETRANS_AVAILABLE else None
        self._cache: dict[str, str] = {}  # Simple translation cache

    # ── Core Translation ──────────────────────────────────────────────────────

    def translate(self, text: str, src: str = "auto", dest: str = "en") -> str:
        """Translate text from src to dest language."""
        if src == dest or not text.strip():
            return text

        cache_key = f"{src}:{dest}:{text[:50]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = None

        # Try DeepL first (higher quality)
        if DEEPL_KEY:
            result = self._translate_deepl(text, dest)

        # Fallback to googletrans
        if not result and self._gtrans:
            result = self._translate_google(text, src, dest)

        # Final fallback: AI translation
        if not result:
            result = self._translate_ai(text, dest)

        if result:
            self._cache[cache_key] = result

        return result or text

    def _translate_google(self, text: str, src: str, dest: str) -> Optional[str]:
        try:
            result = self._gtrans.translate(text, src=src, dest=dest)
            return result.text
        except Exception as e:
            logger.debug(f"Google translate error: {e}")
            return None

    def _translate_deepl(self, text: str, dest: str) -> Optional[str]:
        try:
            import requests
            dest_upper = dest.upper().split("-")[0]
            resp = requests.post(
                "https://api-free.deepl.com/v2/translate",
                data={
                    "auth_key": DEEPL_KEY,
                    "text": text,
                    "target_lang": dest_upper,
                },
                timeout=5,
            )
            return resp.json()["translations"][0]["text"]
        except Exception as e:
            logger.debug(f"DeepL error: {e}")
            return None

    def _translate_ai(self, text: str, dest_lang: str) -> str:
        lang_name = self._code_to_name(dest_lang)
        return self.ai.chat(
            f"Translate the following text to {lang_name}. "
            f"Return ONLY the translation, nothing else:\n\n{text}"
        )

    def detect_language(self, text: str) -> tuple[str, str]:
        """Detect language of text. Returns (code, name)."""
        if self._gtrans:
            try:
                result = self._gtrans.detect(text)
                code = result.lang
                name = self._code_to_name(code)
                self.detected_language = code
                return code, name
            except Exception:
                pass
        return "en", "English"

    # ── Processing Pipeline ───────────────────────────────────────────────────

    def process_input(self, user_input: str) -> tuple[str, str]:
        """
        Process user input:
        Returns (english_text, detected_lang_code)
        """
        if not self.enabled:
            return user_input, "en"

        lang_code, lang_name = self.detect_language(user_input)
        self.detected_language = lang_code

        if lang_code != "en":
            english = self.translate(user_input, src=lang_code, dest="en")
            logger.info(f"Translated [{lang_name}→EN]: {user_input[:30]} → {english[:30]}")
            return english, lang_code

        return user_input, "en"

    def process_response(self, response: str, target_lang: str = None) -> str:
        """
        Translate Makima's response to target language.
        """
        if not self.enabled:
            return response

        dest = target_lang or self.target_language
        if dest == "en":
            return response

        translated = self.translate(response, src="en", dest=dest)
        return translated

    # ── Configuration ─────────────────────────────────────────────────────────

    def enable(self, language: str = None) -> str:
        self.enabled = True
        if language:
            return self.set_language(language)
        return "Translation enabled. I'll auto-detect your language and respond accordingly."

    def disable(self) -> str:
        self.enabled = False
        self.target_language = "en"
        return "Translation disabled. Back to English mode."

    def set_language(self, language: str) -> str:
        lang_lower = language.lower().strip()
        code = LANGUAGE_MAP.get(lang_lower)
        if not code:
            # Try direct code
            if len(lang_lower) <= 5:
                code = lang_lower
            else:
                return f"I don't recognize '{language}'. Try: Hindi, French, Japanese, etc."

        self.target_language = code
        self.enabled = True
        lang_name = self._code_to_name(code)
        return f"Switched to {lang_name}! I'll respond in {lang_name} from now."

    def translate_text(self, text: str) -> str:
        """Translate arbitrary text to current target language."""
        if self.target_language == "en":
            code, name = self.detect_language(text)
            result = self.translate(text, src=code, dest="en")
            return f"Translation: {result}"
        result = self.translate(text, dest=self.target_language)
        return f"Translation: {result}"

    def _code_to_name(self, code: str) -> str:
        reverse = {v: k.title() for k, v in LANGUAGE_MAP.items()}
        if code in reverse:
            return reverse[code]
        if GOOGLETRANS_AVAILABLE:
            try:
                return LANGUAGES.get(code, code).title()
            except Exception:
                pass
        return code.upper()

    def get_status(self) -> str:
        if not self.enabled:
            return "Translation off. Say 'translate to [language]' to enable."
        lang_name = self._code_to_name(self.target_language)
        detected = self._code_to_name(self.detected_language)
        return f"Translation on. Responding in {lang_name}. Last detected: {detected}."
