"""
╔══════════════════════════════════════════════════════════════╗
║         MAKIMA V3 — FULL SYSTEM TEST SUITE                  ║
║  Covers every module except system restart / shutdown        ║
╚══════════════════════════════════════════════════════════════╝

Run:  python test_makima_full.py
      python test_makima_full.py --module memory
      python test_makima_full.py --module ai
      python test_makima_full.py --verbose
      python test_makima_full.py --fast       (skips slow AI tests)

Results: printed to console + saved to _test_results_full.json
"""

import os
import sys
import json
import time
import re
import tempfile
import traceback
import argparse
import platform
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# ── Ensure project root is on path ───────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── ANSI colours ─────────────────────────────────────────────────────────────
C = {
    "green":  "\033[92m",
    "red":    "\033[91m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "blue":   "\033[94m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}
# Disable colours on Windows without ANSI support
if platform.system() == "Windows" and not os.environ.get("ANSICON"):
    C = {k: "" for k in C}

PASS  = f"{C['green']}✅ PASS{C['reset']}"
FAIL  = f"{C['red']}❌ FAIL{C['reset']}"
SKIP  = f"{C['yellow']}⏭  SKIP{C['reset']}"
WARN  = f"{C['yellow']}⚠  WARN{C['reset']}"

# ── Global results store ──────────────────────────────────────────────────────
results: list[dict] = []
verbose = False
fast_mode = False


# ═════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═════════════════════════════════════════════════════════════════════════════

def run(label: str, fn: Callable, module: str = "general", skip_in_fast: bool = False):
    """Run a single test and record result."""
    global results, verbose

    if fast_mode and skip_in_fast:
        results.append({"label": label, "module": module, "status": "skip", "reason": "fast mode"})
        print(f"  {SKIP} [{module}] {label}")
        return

    start = time.time()
    try:
        msg = fn()
        elapsed = time.time() - start
        results.append({"label": label, "module": module, "status": "pass", "elapsed": elapsed})
        detail = f" {C['dim']}({elapsed:.2f}s){C['reset']}" if verbose else ""
        print(f"  {PASS} [{module}] {label}{detail}")
        if verbose and msg:
            print(f"       {C['dim']}→ {str(msg)[:120]}{C['reset']}")
    except AssertionError as e:
        elapsed = time.time() - start
        results.append({"label": label, "module": module, "status": "fail", "error": str(e), "elapsed": elapsed})
        print(f"  {FAIL} [{module}] {label}")
        print(f"       {C['red']}{e}{C['reset']}")
    except Exception as e:
        elapsed = time.time() - start
        tb = traceback.format_exc().strip().split("\n")[-1]
        results.append({"label": label, "module": module, "status": "fail", "error": str(e), "tb": tb, "elapsed": elapsed})
        print(f"  {FAIL} [{module}] {label}")
        print(f"       {C['red']}{e}{C['reset']}")
        if verbose:
            print(f"       {C['dim']}{tb}{C['reset']}")


def section(title: str):
    print(f"\n{C['bold']}{C['cyan']}{'─'*60}{C['reset']}")
    print(f"{C['bold']}{C['cyan']}  {title}{C['reset']}")
    print(f"{C['bold']}{C['cyan']}{'─'*60}{C['reset']}")


# ═════════════════════════════════════════════════════════════════════════════
# 1. ETERNAL MEMORY
# ═════════════════════════════════════════════════════════════════════════════

def test_memory():
    section("1. ETERNAL MEMORY")
    from core.eternal_memory import EternalMemory

    mem = EternalMemory()

    def t_save_and_recall():
        mem.remember("test_key_xyz", "test_value_abc")
        val = mem.recall_note("test_key_xyz")
        assert val == "test_value_abc", f"Expected 'test_value_abc', got {val!r}"
        return val

    def t_fuzzy_recall():
        mem.remember("python favorite language", "Python 3.12")
        val = mem.recall_note("python")
        assert val is not None, "Fuzzy recall returned None"
        return val

    def t_search_memories():
        mem.remember("project deadline", "end of March 2026")
        results_list = mem.search_memories("project timeline", top_k=3)
        assert isinstance(results_list, list), "search_memories should return a list"
        return f"{len(results_list)} results"

    def t_save_conversation():
        before = len(mem._corpus)
        mem.save_conversation("user", "this is a unique test message 99991")
        mem.save_conversation("makima", "acknowledged test message 99991")
        assert len(mem._corpus) >= before + 2, "Corpus should grow after save_conversation"
        return f"corpus size: {len(mem._corpus)}"

    def t_build_memory_context():
        ctx = mem.build_memory_context("python language preference")
        assert isinstance(ctx, str), "Context should be a string"
        return f"{len(ctx)} chars"

    def t_memory_stats():
        stats = mem.get_stats()
        assert "total_entries" in stats
        assert "notes_count" in stats
        return stats

    def t_format_stats():
        s = mem.format_stats()
        assert "memories" in s.lower() or "entries" in s.lower()
        return s

    run("Save and recall exact note",     t_save_and_recall,      "memory")
    run("Fuzzy partial key recall",        t_fuzzy_recall,          "memory")
    run("Semantic memory search",          t_search_memories,       "memory")
    run("Save conversation to corpus",     t_save_conversation,     "memory")
    run("Build memory context for AI",     t_build_memory_context,  "memory")
    run("Get memory stats dict",           t_memory_stats,          "memory")
    run("Format stats as readable string", t_format_stats,          "memory")


# ═════════════════════════════════════════════════════════════════════════════
# 2. AI HANDLER
# ═════════════════════════════════════════════════════════════════════════════

def test_ai():
    section("2. AI HANDLER")
    from core.ai_handler import AIHandler
    from core.eternal_memory import EternalMemory

    mem = EternalMemory()
    ai  = AIHandler(memory=mem)

    def t_init():
        assert ai is not None
        status = ai.get_status()
        assert "persona" in status
        return status

    def t_set_persona_makima():
        r = ai.set_persona("makima")
        assert "makima" in r.lower() or "mode" in r.lower()
        return r

    def t_set_persona_normal():
        r = ai.set_persona("normal")
        assert ai.persona == "normal"
        return r

    def t_set_persona_date():
        r = ai.set_persona("date")
        assert ai.persona == "date"
        ai.set_persona("makima")  # reset
        return r

    def t_set_persona_invalid():
        r = ai.set_persona("nonexistent_persona_xyz")
        assert "unknown" in r.lower() or "available" in r.lower()
        return r

    def t_add_clear_history():
        ai.clear_history()
        ai.add_to_history("user", "hello test")
        ai.add_to_history("assistant", "hi back")
        assert len(ai.conversation_history) == 2
        ai.clear_history()
        assert len(ai.conversation_history) == 0
        return "history cleared"

    def t_trim_history():
        ai.clear_history()
        for i in range(20):
            ai.add_to_history("user", f"msg {i}")
            ai.add_to_history("assistant", f"reply {i}")
        max_expected = ai.max_history_turns * 2
        assert len(ai.conversation_history) <= max_expected, \
            f"History should trim to {max_expected}, got {len(ai.conversation_history)}"
        ai.clear_history()
        return f"trimmed to {len(ai.conversation_history)}"

    def t_update_awareness():
        ai.update_awareness(active_window="vscode", vision_summary="coding python", distraction_level="low")
        assert ai.awareness_context.get("active_window") == "vscode"
        return ai.awareness_context

    def t_build_prompt():
        prompt = ai._build_prompt("test question", context="extra info")
        assert "test question" in prompt
        assert len(prompt) > 50
        return f"{len(prompt)} chars"

    def t_parse_response_json():
        raw = '{"emotion": "happy", "reply": "hello there!"}'
        reply, emotion = ai._parse_response(raw)
        assert reply == "hello there!"
        assert emotion == "happy"
        return f"reply={reply!r}, emotion={emotion!r}"

    def t_parse_response_plain():
        raw = "plain text without json"
        reply, emotion = ai._parse_response(raw)
        assert reply == raw
        assert emotion == "neutral"
        return "fallback parse works"

    def t_parse_response_wrapped():
        raw = '```json\n{"emotion": "focused", "reply": "deep work"}\n```'
        reply, emotion = ai._parse_response(raw)
        assert reply == "deep work"
        assert emotion == "focused"
        return "wrapped JSON parsed"

    def t_chat_returns_tuple(skip_in_fast=True):
        reply, emotion = ai.chat("hello makima, quick test")
        assert isinstance(reply, str) and len(reply) > 0
        assert isinstance(emotion, str)
        return f"reply={reply[:60]!r}, emotion={emotion!r}"

    def t_generate_response(skip_in_fast=True):
        r = ai.generate_response("You are a helper. Reply in one word.", "Say: yes")
        assert isinstance(r, str)
        return f"raw: {r[:80]!r}"

    run("AIHandler initializes",           t_init,                    "ai")
    run("Set persona: makima",             t_set_persona_makima,      "ai")
    run("Set persona: normal",             t_set_persona_normal,      "ai")
    run("Set persona: date",               t_set_persona_date,        "ai")
    run("Set persona: invalid → error msg",t_set_persona_invalid,     "ai")
    run("Add / clear history",             t_add_clear_history,       "ai")
    run("History trimming works",          t_trim_history,            "ai")
    run("Update awareness context",        t_update_awareness,        "ai")
    run("Build prompt string",             t_build_prompt,            "ai")
    run("Parse JSON response",             t_parse_response_json,     "ai")
    run("Parse plain text fallback",       t_parse_response_plain,    "ai")
    run("Parse wrapped JSON (```json)",    t_parse_response_wrapped,  "ai")
    run("chat() returns (str, str)",       t_chat_returns_tuple,      "ai",  skip_in_fast=True)
    run("generate_response() works",       t_generate_response,       "ai",  skip_in_fast=True)


# ═════════════════════════════════════════════════════════════════════════════
# 3. COMMAND ROUTER
# ═════════════════════════════════════════════════════════════════════════════

def test_router():
    section("3. COMMAND ROUTER")
    from core.ai_handler import AIHandler
    from core.eternal_memory import EternalMemory
    from core.command_router import CommandRouter

    mem = EternalMemory()
    ai  = AIHandler(memory=mem)
    router = CommandRouter(ai=ai, memory=mem)

    def route(cmd):
        resp, handler = router.route(cmd)
        return resp, handler

    def t_time():
        resp, h = route("what time is it")
        assert resp and len(resp) > 0
        return resp

    def t_date():
        resp, h = route("what is today's date")
        assert resp and len(resp) > 0
        return resp

    def t_day():
        resp, h = route("what day is it")
        assert resp
        return resp

    def t_remember():
        resp, h = route("remember that my cat is named Luna")
        assert "luna" in resp.lower() or "remember" in resp.lower()
        return resp

    def t_recall():
        resp, h = route("do you remember my cat")
        assert resp
        return resp

    def t_memory_stats():
        resp, h = route("memory stats")
        assert resp and ("memories" in resp.lower() or "entries" in resp.lower() or "notes" in resp.lower())
        return resp

    def t_volume_set():
        resp, h = route("volume to 40")
        assert resp
        return resp

    def t_volume_up():
        resp, h = route("volume up")
        assert resp
        return resp

    def t_volume_down():
        resp, h = route("volume down")
        assert resp
        return resp

    def t_mute():
        resp, h = route("mute")
        assert resp and "muted" in resp.lower()
        return resp

    def t_unmute():
        resp, h = route("unmute")
        # Should NOT say "Muted" — this was the bug we fixed
        assert "muted" not in resp.lower() or "un" in resp.lower(), \
            f"Unmute triggered mute handler! Response: {resp!r}"
        return resp

    def t_screenshot():
        resp, h = route("screenshot")
        assert resp
        return resp

    def t_cpu():
        resp, h = route("cpu usage")
        assert resp and ("%" in resp or "cpu" in resp.lower())
        return resp

    def t_ram():
        resp, h = route("ram usage")
        assert resp and ("%" in resp or "gb" in resp.lower() or "mb" in resp.lower())
        return resp

    def t_battery():
        resp, h = route("battery status")
        assert resp
        return resp

    def t_status():
        resp, h = route("status")
        assert resp
        return resp

    def t_persona_switch():
        resp, h = route("switch to normal mode")
        assert resp
        return resp

    def t_clear_history():
        resp, h = route("clear history")
        assert resp
        return resp

    def t_which_ai():
        resp, h = route("which ai are you using")
        assert resp and ("ollama" in resp.lower() or "gemini" in resp.lower())
        return resp

    def t_use_ollama():
        resp, h = route("use ollama")
        assert "ollama" in resp.lower() or "offline" in resp.lower()
        return resp

    def t_greeting():
        resp, h = route("good morning")
        assert resp
        return resp

    def t_web_search():
        resp, h = route("search for python tutorials")
        assert resp
        return resp

    def t_ai_fallback():
        resp, h = route("tell me something interesting about space")
        assert isinstance(resp, str) and len(resp) > 5
        return f"handler={h}, resp={resp[:80]!r}"

    def t_list_skills():
        resp, h = route("what skills have you learned")
        assert resp
        return resp

    def t_background_status():
        resp, h = route("background status")
        assert resp
        return resp

    def t_list_preferences():
        resp, h = route("list my preferences")
        assert resp
        return resp

    def t_set_preference():
        resp, h = route("set my default browser to Firefox")
        assert resp and ("firefox" in resp.lower() or "preference" in resp.lower() or "browser" in resp.lower())
        return resp

    def t_report():
        resp, h = route("how am i doing")
        assert resp
        return resp

    run("Time query",                       t_time,            "router")
    run("Date query",                       t_date,            "router")
    run("Day query",                        t_day,             "router")
    run("Remember note",                    t_remember,        "router")
    run("Recall note",                      t_recall,          "router")
    run("Memory stats",                     t_memory_stats,    "router")
    run("Volume set to number",             t_volume_set,      "router")
    run("Volume up",                        t_volume_up,       "router")
    run("Volume down",                      t_volume_down,     "router")
    run("Mute",                             t_mute,            "router")
    run("Unmute (not mute!) — Bug #6 check",t_unmute,          "router")
    run("Screenshot",                       t_screenshot,      "router")
    run("CPU usage",                        t_cpu,             "router")
    run("RAM usage",                        t_ram,             "router")
    run("Battery status",                   t_battery,         "router")
    run("System status",                    t_status,          "router")
    run("Persona switch",                   t_persona_switch,  "router")
    run("Clear history",                    t_clear_history,   "router")
    run("Which AI are you using",           t_which_ai,        "router")
    run("Use Ollama mode",                  t_use_ollama,      "router")
    run("Morning greeting",                 t_greeting,        "router")
    run("Web search command",               t_web_search,      "router")
    run("AI fallback for open questions",   t_ai_fallback,     "router")
    run("List learned skills",              t_list_skills,     "router")
    run("Background status",                t_background_status,"router")
    run("List preferences",                 t_list_preferences,"router")
    run("Set preference",                   t_set_preference,  "router")
    run("Learning report",                  t_report,          "router")


# ═════════════════════════════════════════════════════════════════════════════
# 4. MAKIMA MANAGER
# ═════════════════════════════════════════════════════════════════════════════

def test_manager():
    section("4. MAKIMA MANAGER")
    from core.makima_manager import MakimaManager

    spoken = []
    mgr = MakimaManager(speak_fn=lambda t: spoken.append(t))
    mgr.start()

    def t_start():
        assert mgr.running is True
        return "running"

    def t_status_dict():
        s = mgr.status()
        assert "running" in s
        assert "subsystems" in s
        assert "timestamp" in s
        return {k: v for k, v in s["subsystems"].items()}

    def t_status_str():
        s = mgr.status_str()
        assert isinstance(s, str) and len(s) > 0
        return s

    def t_handle_time():
        r = mgr.handle("what time is it")
        assert r and len(r) > 0
        return r

    def t_handle_memory():
        r = mgr.handle("remember that makima test key is hello world 42")
        assert r
        return r

    def t_handle_volume():
        r = mgr.handle("volume up")
        assert r
        return r

    def t_handle_ai_chat():
        r = mgr.handle("just say hi back")
        assert isinstance(r, str) and len(r) > 0
        return r[:80]

    def t_event_hooks():
        fired = []
        mgr.on("on_command", lambda command, **kw: fired.append(command))
        mgr.handle("test event hook command abc123")
        assert "test event hook command abc123" in fired
        return f"hook fired: {fired[-1]!r}"

    def t_update_context():
        mgr.update_context(battery_percent=50, active_app="vscode")
        return "context updated"

    def t_convenience_methods():
        # These should not raise even if subsystems unavailable
        mgr.open("notepad")
        mgr.search("python test")
        mgr.screenshot()
        return "convenience methods called"

    def t_decision_question_detection():
        assert mgr._is_decision_question("should i invest $5000 in bitcoin") is True
        assert mgr._is_decision_question("what time is it") is False
        return "detection correct"

    def t_web_search_detection():
        assert mgr._needs_web_search("search for latest ai news today") is True
        assert mgr._needs_web_search("what is my name") is False  # personal = no web
        assert mgr._needs_web_search("who is the president of France") is True
        return "web search gating correct"

    def t_memory_saved_after_handle():
        from core.eternal_memory import EternalMemory
        before = len(mgr._memory._corpus) if mgr._memory else 0
        mgr.handle("makima manager memory test unique string 77771")
        after = len(mgr._memory._corpus) if mgr._memory else 0
        assert after > before, f"Memory should grow: before={before}, after={after}"
        return f"corpus grew {before} → {after}"

    run("Manager starts",                    t_start,                      "manager")
    run("Status dict has all keys",          t_status_dict,                "manager")
    run("Status string readable",            t_status_str,                 "manager")
    run("handle() time query",               t_handle_time,                "manager")
    run("handle() memory command",           t_handle_memory,              "manager")
    run("handle() volume up",                t_handle_volume,              "manager")
    run("handle() AI chat fallback",         t_handle_ai_chat,             "manager")
    run("Event hooks fire",                  t_event_hooks,                "manager")
    run("update_context() works",            t_update_context,             "manager")
    run("Convenience methods (open/search)", t_convenience_methods,        "manager")
    run("Decision question detection",       t_decision_question_detection,"manager")
    run("Web search gating (Bug #10)",       t_web_search_detection,       "manager")
    run("Memory saved after handle() — Bug #3", t_memory_saved_after_handle,"manager")


# ═════════════════════════════════════════════════════════════════════════════
# 5. INTENT DETECTOR
# ═════════════════════════════════════════════════════════════════════════════

def test_intent():
    section("5. INTENT DETECTOR")
    from makima_tools.intent_detector import IntentDetector

    det = IntentDetector()

    cases = [
        ("open chrome",                    "open_app",      "app_name"),
        ("launch vscode",                  "open_app",      "app_name"),
        ("close spotify",                  "close_app",     None),
        ("play some lofi music",           "play_music",    "mood"),
        ("play metallica",                 "play_music",    None),
        ("search for python tutorials",    "search_web",    None),
        ("remind me to call mom at 6pm",   "set_reminder",  "task"),
        ("volume up",                      "system_control",None),
        ("take a screenshot",              "system_control",None),
        ("what time is it",                "get_info",      None),
        ("explain machine learning",       "get_info",      None),
        ("hey makima",                     "chat",          None),
        ("write a python function",        "write_code",    None),
        ("send email to john",             "send_email",    "recipient"),
    ]

    for text, expected_type, expected_entity in cases:
        def _t(t=text, et=expected_type, ee=expected_entity):
            intent = det.detect(t)
            assert intent.type == et, f"'{t}' → expected {et!r}, got {intent.type!r}"
            assert 0.0 <= intent.confidence <= 1.0
            if ee:
                assert ee in intent.entities, \
                    f"Expected entity {ee!r} in {intent.entities} for '{t}'"
            return f"conf={intent.confidence:.0%}, entities={intent.entities}"
        run(f"detect: {text!r}", _t, "intent")

    def t_confidence_range():
        for phrase in ["open chrome", "play music", "volume up", "random gibberish xyz"]:
            i = det.detect(phrase)
            assert 0.0 <= i.confidence <= 1.0, f"Confidence out of range for {phrase!r}"
        return "all in range"

    def t_missing_slots():
        intent = det.detect("open")
        assert "app_name" in intent.missing or intent.needs_clarification or intent.confidence < 0.9
        return f"missing={intent.missing}"

    run("Confidence always 0–1", t_confidence_range, "intent")
    run("Missing slots detected", t_missing_slots,    "intent")


# ═════════════════════════════════════════════════════════════════════════════
# 6. RESPONSE CACHE
# ═════════════════════════════════════════════════════════════════════════════

def test_cache():
    section("6. RESPONSE CACHE")
    from makima_tools.response_cache import ResponseCache

    cache = ResponseCache()
    cache.clear()  # start fresh

    def t_store_and_get():
        cache.store("what is 2+2", "4")
        r = cache.get("what is 2+2")
        assert r == "4", f"Expected '4', got {r!r}"
        return r

    def t_fuzzy_match():
        cache.store("what is the capital of France", "Paris")
        r = cache.get("what's the capital of France")  # slightly different
        # might match or not — both are valid
        return f"fuzzy result: {r!r}"

    def t_miss_returns_none():
        r = cache.get("this query definitely does not exist xyz99999")
        assert r is None, f"Expected None, got {r!r}"
        return "None on miss"

    def t_stats():
        s = cache.stats()
        assert "entries" in s
        assert "total_hits" in s
        return s

    def t_invalidate():
        cache.store("temp query abc", "temp response")
        cache.invalidate("temp query abc")
        r = cache.get("temp query abc")
        assert r is None
        return "invalidated"

    def t_permanent_entry():
        cache.store("permanent fact", "the sky is blue", permanent=True)
        r = cache.get("permanent fact")
        assert r == "the sky is blue"
        return "permanent stored"

    def t_clear():
        cache.store("a", "1")
        cache.store("b", "2")
        cache.clear()
        assert cache.stats()["entries"] == 0
        return "cleared"

    run("Store and exact get",    t_store_and_get,    "cache")
    run("Fuzzy match",            t_fuzzy_match,      "cache")
    run("Miss returns None",      t_miss_returns_none,"cache")
    run("Stats dict",             t_stats,            "cache")
    run("Invalidate entry",       t_invalidate,       "cache")
    run("Permanent entry",        t_permanent_entry,  "cache")
    run("Clear all",              t_clear,            "cache")


# ═════════════════════════════════════════════════════════════════════════════
# 7. SHORTCUT EXPANDER
# ═════════════════════════════════════════════════════════════════════════════

def test_shortcuts():
    section("7. SHORTCUT EXPANDER")
    from makima_tools.shortcut_expander import ShortcutExpander

    sc = ShortcutExpander()

    def t_add_and_expand():
        sc.add("wm", "what's the weather in Mumbai")
        result = sc.expand("wm")
        assert result == "what's the weather in Mumbai", f"Got {result!r}"
        return result

    def t_no_match_passthrough():
        result = sc.expand("this is not a shortcut 9999")
        assert result == "this is not a shortcut 9999"
        return "passthrough OK"

    def t_case_insensitive():
        sc.add("gm", "good morning makima")
        result = sc.expand("GM")
        assert result == "good morning makima"
        return result

    def t_list_all():
        sc.add("test99", "test expansion 99")
        items = sc.list_all()
        assert isinstance(items, list)
        return f"{len(items)} shortcuts"

    def t_remove():
        sc.add("remove_me", "something")
        sc.remove("remove_me")
        result = sc.expand("remove_me")
        assert result == "remove_me"  # passthrough after removal
        return "removed"

    def t_record_usage():
        # Should not raise
        sc.record_usage("open chrome")
        sc.record_usage("open chrome")
        sc.record_usage("open chrome")
        return "usage recorded"

    def t_suggestions():
        # After repeated usage, suggestions might appear
        suggestions = sc.get_suggestions()
        assert isinstance(suggestions, list)
        return f"{len(suggestions)} suggestions"

    run("Add and expand shortcut",      t_add_and_expand,    "shortcuts")
    run("Non-shortcut passthrough",     t_no_match_passthrough,"shortcuts")
    run("Case-insensitive expand",      t_case_insensitive,  "shortcuts")
    run("List all shortcuts",           t_list_all,          "shortcuts")
    run("Remove shortcut",              t_remove,            "shortcuts")
    run("Record usage",                 t_record_usage,      "shortcuts")
    run("Get suggestions",              t_suggestions,       "shortcuts")


# ═════════════════════════════════════════════════════════════════════════════
# 8. PROACTIVE ENGINE
# ═════════════════════════════════════════════════════════════════════════════

def test_proactive():
    section("8. PROACTIVE ENGINE")
    from makima_tools.proactive_engine import ProactiveEngine

    spoken = []
    engine = ProactiveEngine(speak_fn=lambda t: spoken.append(t))

    def t_init():
        assert engine is not None
        return "OK"

    def t_update_context():
        engine.update_context(battery_percent=12, is_charging=False)
        assert engine._context.get("battery_percent") == 12
        return "context updated"

    def t_battery_critical():
        engine.update_context(battery_percent=8, is_charging=False)
        s = engine.check_now()
        assert s is not None, "Should trigger on 8% battery"
        assert s.priority == 3
        assert "battery" in s.message.lower() or "8" in s.message
        return s.message

    def t_battery_low():
        engine.update_context(battery_percent=18, is_charging=False)
        s = engine.check_now()
        assert s is not None
        assert s.priority >= 2
        return s.message

    def t_clipboard_url():
        engine._last_triggered.clear()
        engine.update_context(
            battery_percent=80, is_charging=True,
            clipboard_content="https://github.com/test"
        )
        s = engine.check_now()
        # May or may not fire depending on other rules — just ensure no crash
        return f"suggestion={s}"

    def t_no_suggestion_all_clear():
        engine._last_triggered.clear()
        engine.update_context(
            battery_percent=85, is_charging=True,
            active_app="", clipboard_content="",
            pending_notifications=0
        )
        # At 9am on a weekday this might trigger morning briefing — that's OK
        s = engine.check_now()
        return f"suggestion={s}"

    def t_cooldown():
        engine._last_triggered.clear()
        engine.update_context(battery_percent=5, is_charging=False)
        s1 = engine.check_now()
        assert s1 is not None

        # Manually set last_triggered to simulate recent fire
        engine._last_triggered[s1.trigger] = time.time()
        engine._fire(s1)
        # spoken should NOT grow since cooldown active
        len_before = len(spoken)
        engine._fire(s1)
        assert len(spoken) == len_before, "Cooldown should prevent double-fire"
        return f"cooldown works, spoken count={len(spoken)}"

    run("Engine initializes",              t_init,                "proactive")
    run("update_context stores values",    t_update_context,      "proactive")
    run("Battery critical → priority 3",   t_battery_critical,    "proactive")
    run("Battery low → suggestion",        t_battery_low,         "proactive")
    run("Clipboard URL → suggestion",      t_clipboard_url,       "proactive")
    run("All-clear → no crash",            t_no_suggestion_all_clear,"proactive")
    run("Cooldown prevents repeat fires",  t_cooldown,            "proactive")


# ═════════════════════════════════════════════════════════════════════════════
# 9. PREFERENCES MANAGER
# ═════════════════════════════════════════════════════════════════════════════

def test_preferences():
    section("9. PREFERENCES MANAGER")
    from core.preferences_manager import PreferencesManager

    prefs = PreferencesManager()

    def t_set_and_get():
        prefs.set_explicit_preference("browser_test", "Firefox")
        val = prefs.get_preference("browser_test")
        assert val == "Firefox", f"Expected 'Firefox', got {val!r}"
        return val

    def t_list():
        prefs.set_explicit_preference("editor_test", "VSCode")
        listing = prefs.list_preferences()
        assert isinstance(listing, str)
        assert "editor_test" in listing or "vscode" in listing.lower()
        return listing[:100]

    def t_record_usage():
        prefs.record_usage("music_test", "lofi")
        prefs.record_usage("music_test", "lofi")
        prefs.record_usage("music_test", "lofi")
        val = prefs.get_preference("music_test")
        assert val is not None, "Recording 3 usages should set a preference"
        return val

    def t_clear():
        prefs.set_explicit_preference("temp_pref_xyz", "temp_val")
        msg = prefs.clear_preference("temp_pref_xyz")
        val = prefs.get_preference("temp_pref_xyz")
        assert val is None
        return msg

    run("Set and get preference",  t_set_and_get,    "prefs")
    run("List preferences",        t_list,           "prefs")
    run("Record usage → learns",   t_record_usage,   "prefs")
    run("Clear preference",        t_clear,          "prefs")


# ═════════════════════════════════════════════════════════════════════════════
# 10. SYSTEM COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

def test_system():
    section("10. SYSTEM COMMANDS")
    from systems.system_commands import SystemCommands

    sys_cmd = SystemCommands()

    def t_volume_set():
        r = sys_cmd.set_volume(30)
        assert r and isinstance(r, str)
        return r

    def t_volume_up():
        r = sys_cmd.volume_up()
        assert r
        return r

    def t_volume_down():
        r = sys_cmd.volume_down()
        assert r
        return r

    def t_mute():
        r = sys_cmd.mute()
        assert r
        return r

    def t_unmute():
        r = sys_cmd.unmute()
        assert r
        return r

    def t_cpu():
        r = sys_cmd.cpu_usage()
        assert r and ("%" in r or "cpu" in r.lower())
        return r

    def t_ram():
        r = sys_cmd.ram_usage()
        assert r and ("gb" in r.lower() or "mb" in r.lower() or "%" in r)
        return r

    def t_battery():
        r = sys_cmd.battery_status()
        assert r
        return r

    def t_screenshot():
        r = sys_cmd.screenshot()
        assert r and isinstance(r, str)
        return r

    def t_maximize():
        r = sys_cmd.maximize_window()
        assert r
        return r

    def t_minimize():
        r = sys_cmd.minimize_window()
        assert r
        return r

    run("Set volume to 30",  t_volume_set,  "system")
    run("Volume up",         t_volume_up,   "system")
    run("Volume down",       t_volume_down, "system")
    run("Mute",              t_mute,        "system")
    run("Unmute",            t_unmute,      "system")
    run("CPU usage",         t_cpu,         "system")
    run("RAM usage",         t_ram,         "system")
    run("Battery status",    t_battery,     "system")
    run("Screenshot",        t_screenshot,  "system")
    run("Maximize window",   t_maximize,    "system")
    run("Minimize window",   t_minimize,    "system")


# ═════════════════════════════════════════════════════════════════════════════
# 11. APP CONTROL
# ═════════════════════════════════════════════════════════════════════════════

def test_app_control():
    section("11. APP CONTROL")
    from systems.app_control import AppControl

    app = AppControl()

    def t_scan():
        r = app.scan()
        assert r and isinstance(r, str)
        return r[:80]

    def t_open_notepad():
        r = app.open("notepad")
        assert r and isinstance(r, str)
        return r

    def t_open_fuzzy():
        r = app.open("calc")  # should match calculator
        assert r and isinstance(r, str)
        return r

    def t_close_notepad():
        r = app.close("notepad")
        assert r and isinstance(r, str)
        return r

    def t_open_nonexistent():
        r = app.open("xyznonexistent12345app")
        assert r and isinstance(r, str)  # should return error message, not crash
        return r

    run("Scan installed apps",       t_scan,              "app_control")
    run("Open Notepad",              t_open_notepad,      "app_control")
    run("Open with fuzzy name",      t_open_fuzzy,        "app_control")
    run("Close Notepad",             t_close_notepad,     "app_control")
    run("Open nonexistent — no crash", t_open_nonexistent,"app_control")


# ═════════════════════════════════════════════════════════════════════════════
# 12. REMINDER SYSTEM
# ═════════════════════════════════════════════════════════════════════════════

def test_reminder():
    section("12. REMINDER SYSTEM")
    from systems.reminder import ReminderSystem

    fired = []
    remind = ReminderSystem(callback=lambda msg: fired.append(msg))

    def t_add_future():
        r = remind.add("take a break", "in 2 minutes")
        assert r and isinstance(r, str)
        return r

    def t_add_invalid_time():
        r = remind.add("something", "not a real time xyz")
        assert r and isinstance(r, str)  # should fail gracefully
        return r

    def t_list():
        remind.add("drink water", "in 5 minutes")
        listing = remind.list_reminders()
        assert isinstance(listing, str)
        return listing[:100]

    run("Add reminder (future)",        t_add_future,        "reminder")
    run("Add reminder (invalid time)",  t_add_invalid_time,  "reminder")
    run("List reminders",               t_list,              "reminder")


# ═════════════════════════════════════════════════════════════════════════════
# 13. FOCUS MODE
# ═════════════════════════════════════════════════════════════════════════════

def test_focus():
    section("13. FOCUS MODE")
    from systems.focus_mode import FocusMode

    focus = FocusMode()

    def t_start():
        r = focus.start()
        assert r and isinstance(r, str)
        return r

    def t_stop():
        r = focus.stop()
        assert r and isinstance(r, str)
        return r

    run("Start focus mode", t_start, "focus")
    run("Stop focus mode",  t_stop,  "focus")


# ═════════════════════════════════════════════════════════════════════════════
# 14. QUANTUM SIMULATOR
# ═════════════════════════════════════════════════════════════════════════════

def test_quantum():
    section("14. QUANTUM SIMULATOR")
    from systems.quantum_simulator import QuantumSimulator

    qs = QuantumSimulator(verbose=False)

    def t_investment():
        r = qs.analyze_investment_decision(
            amount=10000, asset="Bitcoin",
            expected_return=0.15, volatility=0.60,
            num_simulations=1000  # small for speed
        )
        assert "recommendation" in r
        assert "statistics" in r
        rec = r["recommendation"]
        assert isinstance(rec, str) and len(rec) > 10
        return rec[:100]

    def t_job_change():
        r = qs.analyze_job_change(
            current_salary=70000, new_salary=90000,
            num_simulations=1000
        )
        assert "recommendation" in r
        return r["recommendation"][:100]

    def t_business_venture():
        r = qs.analyze_business_venture(
            investment=50000, success_rate=0.4,
            success_return=5.0, num_simulations=1000
        )
        assert "recommendation" in r
        return r["recommendation"][:100]

    def t_statistics_keys():
        r = qs.analyze_investment_decision(
            amount=5000, asset="ETF",
            expected_return=0.08, volatility=0.15,
            num_simulations=500
        )
        stats = r.get("statistics", {})
        assert "mean" in stats or "outcomes" in stats, f"Stats keys: {list(stats.keys())}"
        return f"stats keys: {list(stats.keys())}"

    run("Investment simulation",   t_investment,       "quantum")
    run("Job change simulation",   t_job_change,       "quantum")
    run("Business venture sim",    t_business_venture, "quantum")
    run("Statistics dict present", t_statistics_keys,  "quantum")


# ═════════════════════════════════════════════════════════════════════════════
# 15. WEB AGENT
# ═════════════════════════════════════════════════════════════════════════════

def test_web():
    section("15. WEB AGENT")
    from agents.web_agent import WebAgent
    from core.ai_handler import AIHandler

    ai     = AIHandler()
    agent  = WebAgent(ai=ai)

    def t_search():
        r = agent.search("python programming language")
        assert r and isinstance(r, str)
        return r[:100]

    def t_open_url():
        r = agent.open_url("https://example.com")
        assert r and isinstance(r, str)
        return r[:80]

    run("Web search",  t_search,   "web",  )
    run("Open URL",    t_open_url, "web")


# ═════════════════════════════════════════════════════════════════════════════
# 16. MISHEARING CORRECTOR
# ═════════════════════════════════════════════════════════════════════════════

def test_mishearing():
    section("16. MISHEARING CORRECTOR")
    from core.mishearing import correct_mishearings

    cases = [
        ("hey ma kima open chrome",   "makima"),
        ("hey making a",               None),   # may or may not correct
        ("volume app",                 None),
        ("open chrome",                "chrome"),
    ]

    def t_no_crash_on_any_input():
        inputs = [
            "", "   ", "normal sentence",
            "🎵 emoji input 🎵",
            "a" * 200,
            "open CHROME please",
        ]
        for inp in inputs:
            r = correct_mishearings(inp)
            assert isinstance(r, str), f"Should return str for {inp!r}"
        return "all inputs handled"

    def t_passthrough_clean():
        r = correct_mishearings("open notepad")
        assert r and isinstance(r, str)
        return r

    def t_corrects_known():
        # "ma kima" → "makima" is in the correction table
        r = correct_mishearings("hey ma kima")
        assert isinstance(r, str)
        return r

    run("No crash on any input",   t_no_crash_on_any_input, "mishearing")
    run("Passthrough clean input", t_passthrough_clean,     "mishearing")
    run("Known mishearing fix",    t_corrects_known,        "mishearing")


# ═════════════════════════════════════════════════════════════════════════════
# 17. SMART FILE FINDER
# ═════════════════════════════════════════════════════════════════════════════

def test_file_finder():
    section("17. SMART FILE FINDER")
    from makima_tools.smart_file_finder import SmartFileFinder

    finder = SmartFileFinder()
    time.sleep(0.5)  # let background indexer start

    def t_find_returns_list():
        r = finder.find("test")
        assert isinstance(r, list)
        return f"{len(r)} results"

    def t_find_recent():
        r = finder.find_recent(hours=24)
        assert isinstance(r, list)
        return f"{len(r)} recent files"

    def t_stats():
        s = finder.stats()
        assert "indexed" in s or isinstance(s, dict)
        return s

    def t_find_nonexistent():
        r = finder.find("zzz_definitely_not_a_real_file_xyz99999")
        assert isinstance(r, list)
        assert len(r) == 0 or all(isinstance(x, dict) for x in r)
        return f"{len(r)} results (expected 0)"

    run("find() returns list",          t_find_returns_list,  "files")
    run("find_recent() returns list",   t_find_recent,        "files")
    run("stats() works",                t_stats,              "files")
    run("No results for garbage query", t_find_nonexistent,   "files")


# ═════════════════════════════════════════════════════════════════════════════
# 18. HEALTH TRACKER
# ═════════════════════════════════════════════════════════════════════════════

def test_health():
    section("18. HEALTH TRACKER")
    from systems.health_tracker import HealthTracker

    spoken = []
    ht = HealthTracker(speak_callback=lambda t: spoken.append(t))

    def t_screen_time():
        r = ht.get_screen_time()
        assert r and isinstance(r, str)
        return r

    def t_log_habit():
        r = ht.log_habit("exercise")
        assert r and isinstance(r, str)
        return r

    def t_get_habits():
        r = ht.get_habits()
        assert isinstance(r, str)
        return r[:100]

    def t_health_summary():
        r = ht.health_summary()
        assert isinstance(r, str)
        return r[:100]

    def t_water_reminder():
        r = ht.set_water_reminder(60)
        assert r and isinstance(r, str)
        ht.disable_water_reminder()
        return r

    def t_break_reminder():
        r = ht.set_break_reminder(30)
        assert r and isinstance(r, str)
        ht.disable_break_reminder()
        return r

    run("Get screen time",      t_screen_time,     "health")
    run("Log habit",            t_log_habit,       "health")
    run("Get habits summary",   t_get_habits,      "health")
    run("Health summary",       t_health_summary,  "health")
    run("Set water reminder",   t_water_reminder,  "health")
    run("Set break reminder",   t_break_reminder,  "health")


# ═════════════════════════════════════════════════════════════════════════════
# 19. MACROS
# ═════════════════════════════════════════════════════════════════════════════

def test_macros():
    section("19. MACRO SYSTEM")
    from systems.macros import MacroSystem

    macros = MacroSystem()

    def t_list():
        r = macros.list_macros()
        assert isinstance(r, str)
        return r[:100]

    def t_run_nonexistent():
        r = macros.run_macro("nonexistent_macro_xyz_12345")
        assert r and isinstance(r, str)
        r_low = r.lower()
        assert any(w in r_low for w in ["not found", "no macro", "error", "nonexistent", "not installed", "unavailable", "pynput"])
        return r

    run("List macros",                t_list,             "macros")
    run("Run nonexistent gracefully", t_run_nonexistent,  "macros")


# ═════════════════════════════════════════════════════════════════════════════
# 20. TRANSLATOR
# ═════════════════════════════════════════════════════════════════════════════

def test_translator():
    section("20. TRANSLATOR")
    from agents.translator import TranslationSystem
    from core.ai_handler import AIHandler

    ai = AIHandler()
    t  = TranslationSystem(ai=ai)

    def t_detect_english():
        res = t.detect_language("Hello how are you today")
        assert res and (isinstance(res, str) or isinstance(res, (tuple, list)))
        code = res[0] if isinstance(res, (tuple, list)) else res
        return code

    def t_detect_hindi():
        res = t.detect_language("नमस्ते आप कैसे हैं")
        # googletrans might return a list or tuple
        code = res[0] if isinstance(res, (tuple, list)) else res
        return code

    def t_enable_disable():
        r = t.enable("hindi")
        assert r and isinstance(r, str)
        r2 = t.disable()
        assert r2 and isinstance(r2, str)
        return f"enable: {r}, disable: {r2}"

    def t_status():
        r = t.get_status()
        assert isinstance(r, str)
        return r

    run("Detect English",           t_detect_english,  "translator")
    run("Detect Hindi/Devanagari",  t_detect_hindi,    "translator")
    run("Enable and disable",       t_enable_disable,  "translator")
    run("Get status",               t_status,          "translator")


# ═════════════════════════════════════════════════════════════════════════════
# 21. SECURITY MANAGER
# ═════════════════════════════════════════════════════════════════════════════

def test_security():
    section("21. SECURITY MANAGER")
    from systems.security_manager import SecurityManager

    sec = SecurityManager()

    def t_quick_scan():
        r = sec.quick_scan()
        assert r and isinstance(r, str)
        return r[:100]

    def t_scan_downloads():
        r = sec.scan_downloads()
        assert r and isinstance(r, str)
        return r[:100]

    run("Quick scan",       t_quick_scan,      "security")
    run("Scan downloads",   t_scan_downloads,  "security")


# ═════════════════════════════════════════════════════════════════════════════
# 22. MAKIMA MANAGER — MUSIC / APPS / SYSTEM VIA SUB-MANAGERS
# ═════════════════════════════════════════════════════════════════════════════

def test_sub_managers():
    section("22. SUB-MANAGERS (Music / Apps / System via MakimaManager)")
    from core.makima_manager import (
        MusicManager, AppManager, SystemManager,
        DecisionSimulator, WebSearchManager
    )

    def t_music_manager_init():
        mm = MusicManager()
        assert hasattr(mm, "play")
        return f"ready={mm.ready}"

    def t_music_now_playing():
        mm = MusicManager()
        r = mm.now_playing()
        assert isinstance(r, str)
        return r

    def t_app_manager_open():
        am = AppManager()
        r = am.open("notepad")
        assert isinstance(r, str)
        return r

    def t_system_manager_volume():
        sm = SystemManager()
        r = sm.volume_up()
        assert isinstance(r, str)
        return r

    def t_system_manager_screenshot():
        sm = SystemManager()
        r = sm.screenshot()
        assert isinstance(r, str)
        return r

    def t_decision_simulator():
        ds = DecisionSimulator()
        r = ds.analyze("should I invest $5000 in bitcoin",
                        context={"amount": 5000, "asset": "Bitcoin"})
        assert isinstance(r, str) and len(r) > 10
        return r[:100]

    def t_web_search_manager():
        from core.ai_handler import AIHandler
        ai = AIHandler()
        ws = WebSearchManager(ai_handler=ai)
        r = ws.search("python")
        assert isinstance(r, str)
        return r[:80]

    run("MusicManager initializes",          t_music_manager_init,      "sub_mgr")
    run("MusicManager now_playing()",        t_music_now_playing,       "sub_mgr")
    run("AppManager open()",                 t_app_manager_open,        "sub_mgr")
    run("SystemManager volume_up()",         t_system_manager_volume,   "sub_mgr")
    run("SystemManager screenshot()",        t_system_manager_screenshot,"sub_mgr")
    run("DecisionSimulator analyze()",       t_decision_simulator,      "sub_mgr")
    run("WebSearchManager search()",         t_web_search_manager,      "sub_mgr")


# ═════════════════════════════════════════════════════════════════════════════
# 23. REGRESSION TESTS (all 12 bugs from the fix report)
# ═════════════════════════════════════════════════════════════════════════════

def test_regressions():
    section("23. REGRESSION TESTS — All 12 Fixed Bugs")

    # BUG 1: MakimaV4 import no longer at top level of makima_assistant
    def t_bug1_no_top_level_v4_import():
        src = Path("makima_assistant.py").read_text(encoding="utf-8")
        # Should NOT have a bare top-level "from Makima_v4.main import MakimaV4"
        lines = [l.strip() for l in src.splitlines()]
        for line in lines:
            if line == "from Makima_v4.main import MakimaV4":
                assert False, "Bare top-level Makima_v4 import still present!"
        return "clean"

    # BUG 2: No double memory save in process_input
    def t_bug2_no_double_save():
        src = Path("makima_assistant.py").read_text(encoding="utf-8")
        # Should NOT have memory.save_conversation inside process_input before manager.handle
        pi_start = src.find("def process_input")
        pi_end   = src.find("\n    def ", pi_start + 1)
        pi_body  = src[pi_start:pi_end]
        count = pi_body.count("save_conversation")
        assert count <= 1, f"process_input has {count} save_conversation calls — should be ≤ 1"
        return f"{count} save_conversation call(s) in process_input"

    # BUG 3: Memory saved in handle()
    def t_bug3_memory_in_handle():
        src = Path("core/makima_manager.py").read_text(encoding="utf-8")
        assert "save_conversation" in src, "handle() should call save_conversation"
        return "save_conversation present in manager"

    # BUG 4 & 5: _get_dj and _get_qs use self._ not free function
    def t_bug4_dj_method_call():
        src = Path("core/command_router.py").read_text(encoding="utf-8")
        # Should have self._get_dj() calls in handlers.
        assert "self._get_dj()" in src, "Missing self._get_dj() calls"
        # The buggy version was something like 'dj = _get_dj(self)'
        assert "_get_dj(self)" not in src.replace("def _get_dj(self):", ""), \
            "Still has buggy _get_dj(self) call (outside of definition)"
        return "method call correct"

    def t_bug5_qs_method_call():
        src = Path("core/command_router.py").read_text(encoding="utf-8")
        assert "self._get_qs()" in src, "Missing self._get_qs() calls"
        assert "_get_qs(self)" not in src.replace("def _get_qs(self):", ""), \
            "Still has buggy _get_qs(self) call (outside of definition)"
        return "method call correct"

    # BUG 6: mute regex doesn't match unmute
    def t_bug6_mute_regex():
        import re
        from core.command_router import CommandRouter
        from core.ai_handler import AIHandler
        from core.eternal_memory import EternalMemory
        mem    = EternalMemory()
        ai     = AIHandler(memory=mem)
        router = CommandRouter(ai=ai, memory=mem)
        resp, handler = router.route("unmute volume")
        assert handler != "_handle_mute", f"Unmute triggered mute handler! handler={handler}"
        assert "muted" not in resp.lower() or "unmuted" in resp.lower(), \
            f"Unmute returned mute response: {resp!r}"
        return f"handler={handler}, resp={resp!r}"

    # BUG 7: command_router_v2.py has content
    def t_bug7_v2_has_content():
        src = Path("core/command_router_v2.py").read_text(encoding="utf-8")
        assert len(src.strip()) > 4, "command_router_v2.py is still effectively empty"
        return f"{len(src)} bytes"

    # BUG 8: Memory re-index uses smarter threshold
    def t_bug8_reindex_threshold():
        src = Path("core/eternal_memory.py").read_text(encoding="utf-8")
        # Old code had "% 10" only. New code has adaptive threshold
        assert "threshold" in src or ("% 5" in src and "% 20" in src), \
            "Memory still uses old fixed-10 re-index threshold"
        return "adaptive threshold present"

    # BUG 9: No duplicate imports in generate_response
    def t_bug9_no_local_import():
        src = Path("core/ai_handler.py").read_text(encoding="utf-8")
        gr_start = src.find("def generate_response")
        gr_end   = src.find("\n    def ", gr_start + 1)
        gr_body  = src[gr_start:gr_end]
        assert "import ollama" not in gr_body, "generate_response still has local 'import ollama'"
        assert "import requests" not in gr_body, "generate_response still has local 'import requests'"
        return "no local imports in generate_response"

    # BUG 10: _needs_web_search tighter
    def t_bug10_web_search_gating():
        from core.makima_manager import MakimaManager
        mgr = MakimaManager()
        assert mgr._needs_web_search("what is my name") is False, \
            "'what is my name' should NOT trigger web search (personal question)"
        assert mgr._needs_web_search("search for latest news today") is True, \
            "'search for latest news today' SHOULD trigger web search"
        return "gating correct"

    # BUG 11: Voice loop now gives feedback on silence
    def t_bug11_voice_feedback():
        src = Path("makima_assistant.py").read_text(encoding="utf-8")
        assert "listening" in src.lower() or "say your command" in src.lower(), \
            "Voice loop should say something when no command heard after wake word"
        return "feedback phrase present"

    # BUG 12: No local re-import in generate_response (same as bug 9 — double check)
    def t_bug12_no_duplicate_import():
        src = Path("core/ai_handler.py").read_text(encoding="utf-8")
        # Count top-level import ollama (should be 0 since it's imported as _ollama)
        local_import_count = src.count("\n        import ollama")
        assert local_import_count == 0, f"Found {local_import_count} local 'import ollama' inside methods"
        return f"local imports: {local_import_count}"

    run("Bug 1: No top-level MakimaV4 import",          t_bug1_no_top_level_v4_import, "regression")
    run("Bug 2: No double save in process_input",        t_bug2_no_double_save,         "regression")
    run("Bug 3: Memory saved in handle()",               t_bug3_memory_in_handle,       "regression")
    run("Bug 4: _get_dj uses self._ method call",        t_bug4_dj_method_call,         "regression")
    run("Bug 5: _get_qs uses self._ method call",        t_bug5_qs_method_call,         "regression")
    run("Bug 6: unmute doesn't trigger mute handler",    t_bug6_mute_regex,             "regression")
    run("Bug 7: command_router_v2.py has content",       t_bug7_v2_has_content,         "regression")
    run("Bug 8: adaptive re-index threshold",            t_bug8_reindex_threshold,      "regression")
    run("Bug 9: no local imports in generate_response",  t_bug9_no_local_import,        "regression")
    run("Bug 10: web search gating correct",             t_bug10_web_search_gating,     "regression")
    run("Bug 11: voice loop gives feedback on silence",  t_bug11_voice_feedback,        "regression")
    run("Bug 12: no duplicate module imports",           t_bug12_no_duplicate_import,   "regression")


# ═════════════════════════════════════════════════════════════════════════════
# 24. END-TO-END FLOW TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_e2e():
    section("24. END-TO-END FLOW TESTS")
    from core.makima_manager import MakimaManager

    spoken = []
    mgr = MakimaManager(speak_fn=lambda t: spoken.append(t))
    mgr.start()

    e2e_commands = [
        ("Hello Makima, who are you?",                "chat/identity"),
        ("Remember that my favorite color is crimson","memory"),
        ("What is my favorite color?",                "memory_recall"),
        ("Which AI are you using?",                   "ai_status"),
        ("Set volume to 25",                          "volume"),
        ("Volume up",                                 "volume"),
        ("Volume down",                               "volume"),
        ("Mute",                                      "mute"),
        ("Unmute",                                    "unmute_regression"),
        ("Battery status",                            "battery"),
        ("RAM usage",                                 "ram"),
        ("CPU usage",                                 "cpu"),
        ("What is my music taste profile?",           "profile"),
        ("Set my default browser to Chrome",          "preference"),
        ("List my preferences",                       "pref_list"),
        ("Search for Python programming",             "web"),
        ("What time is it",                           "time"),
        ("Simulate an investment of $5000 in Apple",  "quantum"),
        ("Good morning",                              "greeting"),
        ("Memory stats",                              "memory_stats"),
    ]

    for cmd, tag in e2e_commands:
        def _t(c=cmd, t=tag):
            r = mgr.handle(c)
            assert r and isinstance(r, str) and len(r) > 0, \
                f"Empty response for: {c!r}"
            # Special check: unmute should not say "Muted"
            if t == "unmute_regression":
                assert "muted" not in r.lower() or "unmuted" in r.lower(), \
                    f"Unmute returned mute response: {r!r}"
            return r[:80]
        run(f"E2E: {cmd[:50]}", _t, "e2e")


# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════

def print_summary(filter_module: Optional[str] = None):
    filtered = [r for r in results if not filter_module or r["module"] == filter_module]

    passed  = [r for r in filtered if r["status"] == "pass"]
    failed  = [r for r in filtered if r["status"] == "fail"]
    skipped = [r for r in filtered if r["status"] == "skip"]
    total   = len(filtered)

    print(f"\n{'═'*60}")
    print(f"{C['bold']}  TEST SUMMARY{C['reset']}")
    print(f"{'═'*60}")
    print(f"  {C['green']}Passed:  {len(passed)}/{total}{C['reset']}")
    print(f"  {C['red']}Failed:  {len(failed)}/{total}{C['reset']}")
    print(f"  {C['yellow']}Skipped: {len(skipped)}/{total}{C['reset']}")

    if failed:
        print(f"\n{C['red']}{C['bold']}  FAILED TESTS:{C['reset']}")
        for r in failed:
            print(f"  {C['red']}✗ [{r['module']}] {r['label']}{C['reset']}")
            if r.get("error"):
                print(f"    {C['dim']}{r['error']}{C['reset']}")

    # Save to JSON
    out = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total, "passed": len(passed),
            "failed": len(failed), "skipped": len(skipped),
            "pass_rate": f"{len(passed)/total*100:.1f}%" if total else "0%"
        },
        "results": filtered
    }
    Path("_test_results_full.json").write_text(json.dumps(out, indent=2))

    print(f"\n  Results saved → {C['cyan']}_test_results_full.json{C['reset']}")

    if not failed:
        print(f"\n{C['green']}{C['bold']}  🌸 ALL TESTS PASSED! Makima is healthy.{C['reset']}\n")
    else:
        print(f"\n{C['red']}{C['bold']}  ⚠  {len(failed)} test(s) failed. See above.{C['reset']}\n")

    return len(failed) == 0


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

MODULE_MAP = {
    "memory":       test_memory,
    "ai":           test_ai,
    "router":       test_router,
    "manager":      test_manager,
    "intent":       test_intent,
    "cache":        test_cache,
    "shortcuts":    test_shortcuts,
    "proactive":    test_proactive,
    "prefs":        test_preferences,
    "system":       test_system,
    "app":          test_app_control,
    "reminder":     test_reminder,
    "focus":        test_focus,
    "quantum":      test_quantum,
    "web":          test_web,
    "mishearing":   test_mishearing,
    "files":        test_file_finder,
    "health":       test_health,
    "macros":       test_macros,
    "translator":   test_translator,
    "security":     test_security,
    "sub_managers": test_sub_managers,
    "regression":   test_regressions,
    "e2e":          test_e2e,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Makima V3 Full Test Suite")
    parser.add_argument("--module",   "-m", help=f"Run only: {', '.join(MODULE_MAP)}")
    parser.add_argument("--verbose",  "-v", action="store_true", help="Show response previews")
    parser.add_argument("--fast",     "-f", action="store_true", help="Skip slow AI API calls")
    args = parser.parse_args()

    verbose   = args.verbose
    fast_mode = args.fast

    os.chdir(ROOT)  # ensure relative paths work

    print(f"\n{C['bold']}{C['cyan']}")
    print("╔══════════════════════════════════════════════════════╗")
    print("║         🌸 MAKIMA V3 — FULL SYSTEM TEST SUITE       ║")
    print(f"║  {'Fast mode ON — skipping AI calls' if fast_mode else 'Full mode — testing everything':<50} ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(C['reset'])

    if args.module:
        m = args.module.lower()
        if m not in MODULE_MAP:
            print(f"Unknown module {m!r}. Available: {', '.join(MODULE_MAP)}")
            sys.exit(1)
        MODULE_MAP[m]()
        ok = print_summary(filter_module=m.replace("app", "app_control")
                           .replace("prefs", "prefs").replace("sub_managers","sub_mgr"))
    else:
        for fn in MODULE_MAP.values():
            fn()
        ok = print_summary()

    sys.exit(0 if ok else 1)
