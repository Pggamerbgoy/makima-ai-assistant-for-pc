"""
TOOL: Response Cache
──────────────────────────────────────────────
Caches AI responses so repeated/similar questions
are answered instantly without API calls.

USAGE in ai_handler.py:
    from tools.response_cache import ResponseCache
    cache = ResponseCache()

    # Before calling LLM:
    cached = cache.get(user_input)
    if cached: return cached

    # After getting LLM response:
    cache.store(user_input, response)
"""

import json
import hashlib
import time
import os
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher


CACHE_FILE = Path("makima_memory/response_cache.json")
MAX_CACHE_SIZE = 500       # max entries
CACHE_TTL_HOURS = 48       # expire after 48 hours
SIMILARITY_THRESHOLD = 0.85  # 85% similar = same question


class ResponseCache:

    def __init__(self):
        CACHE_FILE.parent.mkdir(exist_ok=True)
        self.cache = self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, query: str) -> Optional[str]:
        """Return cached response or None. Checks exact + fuzzy match."""
        self._expire_old()

        # Exact match (hash lookup — O(1))
        key = self._hash(query)
        if key in self.cache:
            entry = self.cache[key]
            entry["hits"] += 1
            print(f"[Cache] ✅ Exact hit ({entry['hits']} hits)")
            return entry["response"]

        # Fuzzy match (for slight rephrasing) — skip very short queries to avoid noise
        if len(query.strip()) >= 10:
            for k, entry in self.cache.items():
                similarity = SequenceMatcher(None, query.lower(), entry["query"].lower()).ratio()
                if similarity >= SIMILARITY_THRESHOLD:
                    entry["hits"] += 1
                    print(f"[Cache] 🔍 Fuzzy hit ({similarity:.0%} similar)")
                    return entry["response"]

        return None

    def store(self, query: str, response: str, permanent: bool = False):
        """Store a response. permanent=True means it never expires."""
        if len(self.cache) >= MAX_CACHE_SIZE:
            self._evict_lru()

        key = self._hash(query)
        self.cache[key] = {
            "query": query,
            "response": response,
            "timestamp": time.time(),
            "hits": 0,
            "permanent": permanent
        }
        self._save()

    def invalidate(self, query: str):
        """Remove a specific entry."""
        key = self._hash(query)
        self.cache.pop(key, None)
        self._save()

    def clear(self):
        """Wipe everything."""
        self.cache = {}
        self._save()

    def stats(self) -> dict:
        total = len(self.cache)
        hits = sum(e["hits"] for e in self.cache.values())
        return {"entries": total, "total_hits": hits, "max_size": MAX_CACHE_SIZE}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def _expire_old(self):
        cutoff = time.time() - (CACHE_TTL_HOURS * 3600)
        before = len(self.cache)
        self.cache = {
            k: v for k, v in self.cache.items()
            if v.get("permanent") or v["timestamp"] > cutoff
        }
        if len(self.cache) < before:
            self._save()

    def _evict_lru(self):
        """Remove least recently used non-permanent entry."""
        candidates = {k: v for k, v in self.cache.items() if not v.get("permanent")}
        if candidates:
            lru_key = min(candidates, key=lambda k: candidates[k]["timestamp"])
            del self.cache[lru_key]

    def _load(self) -> dict:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save(self):
        CACHE_FILE.write_text(json.dumps(self.cache, indent=2))
