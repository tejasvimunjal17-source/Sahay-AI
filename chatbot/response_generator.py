"""
chatbot/response_generator.py
--------------------------------
PHASE 3 IMPLEMENTATION.

Orchestrates a single chat turn:

    screen_input() -> [crisis/block short-circuit] -> analyze_mood()
        -> OpenRouter call -> screen_output() -> [block override] -> result

This is the ONLY place these pieces are wired together — UI code
(components/chatbot_launcher.py, pages/companion.py) calls only
generate_response(), never the individual chatbot/backend modules
directly, so the safety ordering can't be accidentally bypassed by a
future UI change.

No conversation persistence happens here (or anywhere in Phase 3) — see
PHASE3_PRE_IMPLEMENTATION_AUDIT.md §6. `chat_history` is whatever the
caller already has in st.session_state; nothing is written to Supabase.
"""

from __future__ import annotations

from backend.logging_config import get_logger
from backend.openrouter_client import (
    chat_completion, OpenRouterError, OpenRouterNotConfiguredError,
)
from chatbot import safety
from chatbot.mood_analyzer import analyze_mood, DEFAULT_RESULT as DEFAULT_MOOD, MOOD_SUGGESTIONS
from chatbot.system_prompt import get_system_prompt

logger = get_logger(__name__)

MAX_HISTORY_TURNS = 12  # trim like LearnMate's client did — bounds prompt size/cost


def generate_response(message: str, chat_history: list[dict] | None = None, language: str = "English") -> dict:
    """Returns {"reply": str, "mood": dict, "safety_action": str, "suggestion": dict | None}.

    "suggestion", added in Phase 5, is {"activity_key": str | None, "text": str}
    or None — a pure-data hint from chatbot.mood_analyzer.MOOD_SUGGESTIONS,
    attached ONLY on a normal successful turn (never on crisis/blocked/error/
    not-configured turns, and never when the mapped mood has no suggestion
    text — e.g. Happy/Calm/Neutral). This is a UI-layer hint, not part of
    the model's own reply — chatbot/system_prompt.py is unaware of it, per
    the approved Phase 5 decision. Whether/how often to actually render it
    (avoiding repetition, allowing dismissal) is entirely a UI-layer
    decision — see components/chatbot_launcher.py / pages/companion.py.

    NEVER raises — every failure mode (misconfiguration, network error,
    malformed model output, a safety block) resolves to a friendly reply
    string, so UI code can always just display result["reply"].

    NOT LIVE-TESTED in this environment — see PHASE3_IMPLEMENTATION_REPORT.md.
    """
    chat_history = chat_history or []

    # ---- 1. Deterministic input screening — runs BEFORE any model call ----
    input_screen = safety.screen_input(message)
    if input_screen["action"] == "crisis":
        logger.info("Crisis pattern matched on input — short-circuiting to deterministic response")
        return {
            "reply": safety.crisis_response_text(),
            "mood": dict(DEFAULT_MOOD),
            "safety_action": "crisis",
            "suggestion": None,
        }
    if input_screen["action"] == "block":
        logger.info("Blocked pattern matched on input (category=%s) — short-circuiting", input_screen["category"])
        return {
            "reply": safety.blocked_response_text(input_screen["category"]),
            "mood": dict(DEFAULT_MOOD),
            "safety_action": "block",
            "suggestion": None,
        }

    # ---- 2. Non-clinical mood/sentiment/risk classification ----
    mood = analyze_mood(message, chat_history)

    # ---- 3. Model call ----
    try:
        messages = _build_messages(message, chat_history, language)
        reply = chat_completion(messages)
    except OpenRouterNotConfiguredError:
        logger.info("OpenRouter not configured — returning a friendly not-available message")
        return {
            "reply": (
                "Sahay's AI conversation engine isn't connected yet in this environment. "
                "Once it is, I'll be able to respond here."
            ),
            "mood": mood,
            "safety_action": "not_configured",
            "suggestion": None,
        }
    except OpenRouterError as exc:
        logger.warning("OpenRouter call failed: %s", type(exc).__name__)
        return {
            "reply": str(exc),  # OpenRouterError messages are already user-safe (see openrouter_client.py)
            "mood": mood,
            "safety_action": "error",
            "suggestion": None,
        }

    # ---- 4. Deterministic output screening — runs BEFORE showing the reply ----
    output_screen = safety.screen_output(reply)
    if output_screen["action"] == "block":
        logger.warning("Model output blocked by output screening (category=%s)", output_screen["category"])
        reply = safety.safe_fallback_text()
        return {"reply": reply, "mood": mood, "safety_action": output_screen["action"], "suggestion": None}

    # ---- 5. Personalized wellness suggestion — data only, UI decides rendering ----
    suggestion = None
    mapped = MOOD_SUGGESTIONS.get(mood.get("mood"))
    if mapped and mapped.get("text"):
        suggestion = {"activity_key": mapped.get("activity_key"), "text": mapped["text"]}

    return {"reply": reply, "mood": mood, "safety_action": output_screen["action"], "suggestion": suggestion}


def _build_messages(message: str, chat_history: list[dict], language: str) -> list[dict]:
    trimmed = chat_history[-MAX_HISTORY_TURNS:]
    messages = [{"role": "system", "content": get_system_prompt(language)}]
    for turn in trimmed:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages
