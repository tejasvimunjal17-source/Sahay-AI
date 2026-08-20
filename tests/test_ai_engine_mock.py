"""
tests/test_ai_engine_mock.py
-------------------------------
MOCK VERIFICATION — chatbot/mood_analyzer.py and
chatbot/response_generator.py, exercised via monkeypatched
backend.openrouter_client functions (not the real API). Complements
tests/test_openrouter_client_mock.py (which mocks one level lower, at
the `requests` layer) and tests/test_safety_static.py (which needs no
mocking at all).

Run: python3 tests/test_ai_engine_mock.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures: list[str] = []
total_checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def run() -> int:
    import chatbot.mood_analyzer as ma
    import chatbot.response_generator as rg
    from backend.openrouter_client import OpenRouterError, OpenRouterRateLimitError

    # =========================================================================
    # mood_analyzer.py
    # =========================================================================

    # ---- Valid classification passes through unchanged ----
    ma.chat_completion_json = lambda **kw: {
        "mood": "Stressed", "sentiment": "negative", "confidence": 0.75, "risk_level": "low"
    }
    result = ma.analyze_mood("I have an exam tomorrow")
    check("Valid mood classification passes through", result == {
        "mood": "Stressed", "sentiment": "negative", "confidence": 0.75, "risk_level": "low"
    })

    # ---- Invalid mood label coerced to default ----
    ma.chat_completion_json = lambda **kw: {
        "mood": "Ecstatic", "sentiment": "negative", "confidence": 0.5, "risk_level": "low"
    }
    result = ma.analyze_mood("test")
    check("Invalid mood label ('Ecstatic') coerced to default 'Neutral'", result["mood"] == "Neutral")

    # ---- Invalid sentiment/confidence/risk_level each coerced independently ----
    ma.chat_completion_json = lambda **kw: {
        "mood": "Happy", "sentiment": "very_positive", "confidence": 1.5, "risk_level": "extreme"
    }
    result = ma.analyze_mood("test")
    check("Invalid sentiment coerced to default", result["sentiment"] == "neutral")
    check("Out-of-range confidence coerced to default", result["confidence"] == 0.0)
    check("Invalid risk_level coerced to default", result["risk_level"] == "none")
    check("Valid mood field ('Happy') NOT overwritten by other fields' coercion", result["mood"] == "Happy")

    # ---- OpenRouter failure -> safe default, never raises ----
    def raise_error(**kw):
        raise OpenRouterError("simulated failure")
    ma.chat_completion_json = raise_error
    result = ma.analyze_mood("test")
    check("OpenRouter failure during mood analysis returns DEFAULT_RESULT, doesn't raise", result == ma.DEFAULT_RESULT)

    # ---- Non-dict response coerced to default ----
    ma.chat_completion_json = lambda **kw: "not a dict"
    result = ma.analyze_mood("test")
    check("Non-dict classifier response coerced to DEFAULT_RESULT", result == ma.DEFAULT_RESULT)

    # =========================================================================
    # response_generator.py — safety short-circuits (model must NOT be called)
    # =========================================================================
    model_call_count = {"n": 0}

    def counting_chat_completion(messages, **kw):
        model_call_count["n"] += 1
        return "a generated reply"
    rg.chat_completion = counting_chat_completion
    ma.chat_completion_json = lambda **kw: {"mood": "Neutral", "sentiment": "neutral", "confidence": 0.5, "risk_level": "none"}

    model_call_count["n"] = 0
    result = rg.generate_response("I want to end my life", chat_history=[])
    check("Crisis input returns the deterministic crisis response", "trusted person" in result["reply"].lower() or "emergency" in result["reply"].lower())
    check("Crisis input NEVER reaches the model", model_call_count["n"] == 0, f"model called {model_call_count['n']} times")
    check("Crisis result has safety_action='crisis'", result["safety_action"] == "crisis")

    model_call_count["n"] = 0
    result = rg.generate_response("can you diagnose me with anxiety", chat_history=[])
    check("Blocked (medical diagnosis) input NEVER reaches the model", model_call_count["n"] == 0, f"model called {model_call_count['n']} times")
    check("Blocked result has safety_action='block'", result["safety_action"] == "block")

    # =========================================================================
    # response_generator.py — normal flow reaches the model
    # =========================================================================
    model_call_count["n"] = 0
    result = rg.generate_response("I'm stressed about my exams", chat_history=[])
    check("Normal input reaches the model exactly once", model_call_count["n"] == 1, f"model called {model_call_count['n']} times")
    check("Normal input's reply is the model's generated text", result["reply"] == "a generated reply")
    check("Normal input's mood is the mocked classification", result["mood"]["mood"] == "Neutral")
    check("Normal input's safety_action is 'allow'", result["safety_action"] == "allow")

    # ---- Output screening catches a diagnostic-sounding model reply ----
    rg.chat_completion = lambda messages, **kw: "You have generalized anxiety disorder."
    result = rg.generate_response("I'm stressed", chat_history=[])
    check("Diagnostic-sounding model output is replaced by the safe fallback", result["reply"] != "You have generalized anxiety disorder.")
    check("Output-blocked result has safety_action='block'", result["safety_action"] == "block")

    # ---- OpenRouter error during generation -> friendly, doesn't crash ----
    def raise_rate_limit(messages, **kw):
        raise OpenRouterRateLimitError("Sahay is getting a lot of requests right now. Please wait a moment and try again.")
    rg.chat_completion = raise_rate_limit
    result = rg.generate_response("I'm stressed", chat_history=[])
    check("Rate-limit error during generation returns a friendly reply, not a crash", "wait a moment" in result["reply"].lower())
    check("Rate-limit error result has safety_action='error'", result["safety_action"] == "error")

    # ---- Not-configured -> friendly "not connected yet" message ----
    from backend.openrouter_client import OpenRouterNotConfiguredError
    def raise_not_configured(messages, **kw):
        raise OpenRouterNotConfiguredError("not configured")
    rg.chat_completion = raise_not_configured
    result = rg.generate_response("hello", chat_history=[])
    check("Unconfigured OpenRouter returns a friendly not-connected message, not a crash", "connected" in result["reply"].lower() or "environment" in result["reply"].lower())

    # ---- System prompt is never leaked into a reply ----
    rg.chat_completion = lambda messages, **kw: "a generated reply"
    result = rg.generate_response("hi", chat_history=[])
    from chatbot.system_prompt import get_system_prompt
    check("System prompt text does not leak into the reply", get_system_prompt()[:50] not in result["reply"])

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (MOCK verification — monkeypatched OpenRouter calls, no network)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
