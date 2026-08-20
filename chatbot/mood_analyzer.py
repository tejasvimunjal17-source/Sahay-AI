"""
chatbot/mood_analyzer.py
---------------------------
PHASE 3 IMPLEMENTATION.

Non-clinical mood/sentiment/risk classification, per the master spec §8.2.
Returns structured data:

    {"mood": "stressed", "sentiment": "negative", "confidence": 0.82, "risk_level": "low"}

This is an APPLICATION-LEVEL SIGNAL, never a medical diagnosis. Nothing
in this module or its output should be presented to a user as clinically
meaningful — callers (chatbot/response_generator.py, and any future UI)
must keep that framing.

Chain-of-thought: the model is instructed to return ONLY the JSON object
— no explanation, no reasoning — and instructed explicitly not to
disclose any thinking process. openrouter_client.chat_completion_json()
raises OpenRouterResponseError on anything that doesn't parse as valid
JSON, which this module treats as "classification unavailable," not a
raise up the stack.
"""

from __future__ import annotations

from backend.logging_config import get_logger
from backend.openrouter_client import (
    chat_completion_json, OpenRouterError, OpenRouterNotConfiguredError,
)

logger = get_logger(__name__)

VALID_MOODS = {
    "Happy", "Calm", "Neutral", "Sad", "Stressed",
    "Anxious", "Lonely", "Angry", "Overwhelmed",
}
VALID_SENTIMENTS = {"positive", "neutral", "negative"}
VALID_RISK_LEVELS = {"none", "low", "medium", "high"}

# Shared across pages/mood_checkin.py and pages/companion.py so the same
# mood always gets the same emoji everywhere it's shown.
MOOD_EMOJI = {
    "Happy": "😊", "Calm": "😌", "Neutral": "😐", "Sad": "😔",
    "Anxious": "😟", "Stressed": "😣", "Lonely": "🥺", "Angry": "😠", "Overwhelmed": "😵",
}

# PHASE 5: pure-data mapping from a mood to a suggested relaxation activity
# key (see pages/relaxation.py's ACTIVITIES list for the matching keys).
# Deliberately just a key, not suggestion copy — the UI layer (see
# components/chatbot_launcher.py / pages/companion.py) decides the actual
# wording and whether/when to show it. Kept UI-side and invisible to the
# system prompt per the approved Phase 5 decision — chatbot/system_prompt.py
# is not modified for this feature. Wording follows the master spec's
# "One option you could try is..." framing, never "You need to...".
MOOD_SUGGESTIONS: dict[str, dict[str, str]] = {
    "Stressed": {"activity_key": "box_breathing", "text": "One option you could try is a short breathing exercise."},
    "Anxious": {"activity_key": "grounding_54321", "text": "One option you could try is a quick grounding exercise."},
    "Overwhelmed": {"activity_key": "study_break", "text": "One option you could try is breaking things into smaller steps, with a short break first."},
    "Lonely": {"activity_key": None, "text": "One option you could try is reaching out to a trusted person — see Human Help for more ideas."},
    "Sad": {"activity_key": "journaling_prompt", "text": "One option you could try is a short journaling prompt, if that feels helpful."},
    "Angry": {"activity_key": "mindful_pause", "text": "One option you could try is a short mindful pause before responding to what's bothering you."},
    "Calm": {"activity_key": None, "text": "One option you could try is keeping up whatever's working for you right now."},
    "Happy": {"activity_key": None, "text": None},
    "Neutral": {"activity_key": None, "text": None},
}

DEFAULT_RESULT = {
    "mood": "Neutral",
    "sentiment": "neutral",
    "confidence": 0.0,
    "risk_level": "none",
}

_CLASSIFIER_INSTRUCTIONS = """You are a non-clinical mood classifier for a student \
wellness app. Read the student's latest message (with brief context if given) and \
classify it. This is NOT a medical or psychiatric assessment — it's an approximate, \
non-clinical signal only.

Respond with ONLY a single JSON object, no other text, no explanation, no reasoning:

{{
  "mood": one of ["Happy", "Calm", "Neutral", "Sad", "Stressed", "Anxious", "Lonely", "Angry", "Overwhelmed"],
  "sentiment": one of ["positive", "neutral", "negative"],
  "confidence": a number between 0.0 and 1.0,
  "risk_level": one of ["none", "low", "medium", "high"] — a rough, non-clinical signal \
of how much the message suggests the student may need extra support; "high" only for \
messages suggesting serious immediate distress
}}

Student's message: {message}"""


def analyze_mood(message: str, chat_history: list[dict] | None = None) -> dict:
    """Classifies a single message. Never raises — on any failure
    (misconfiguration, network error, malformed model output), returns
    DEFAULT_RESULT and logs a warning, so a classification hiccup never
    breaks the chat turn itself."""
    try:
        prompt = _CLASSIFIER_INSTRUCTIONS.format(message=message)
        result = chat_completion_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150,
        )
    except OpenRouterNotConfiguredError:
        # Expected in any environment without OpenRouter configured (e.g.
        # local dev, or this project's own sandbox) — not an error, so no
        # traceback/ERROR-level noise for what is a normal, anticipated state.
        logger.info("Mood classification skipped (OpenRouter not configured)")
        return dict(DEFAULT_RESULT)
    except OpenRouterError as exc:
        logger.warning("Mood classification unavailable this turn: %s", type(exc).__name__)
        return dict(DEFAULT_RESULT)
    except Exception:  # noqa: BLE001 - classification must never break the chat turn
        logger.exception("Unexpected error during mood classification")
        return dict(DEFAULT_RESULT)

    return _validate(result)


def _validate(raw: dict) -> dict:
    """Coerces a model's JSON output into a known-safe shape. Any field
    that's missing, mistyped, or outside the allowed set falls back to
    the default for that field rather than propagating an unexpected
    value (e.g. a model-invented mood label) into the rest of the app."""
    if not isinstance(raw, dict):
        return dict(DEFAULT_RESULT)

    mood = raw.get("mood")
    if mood not in VALID_MOODS:
        mood = DEFAULT_RESULT["mood"]

    sentiment = raw.get("sentiment")
    if sentiment not in VALID_SENTIMENTS:
        sentiment = DEFAULT_RESULT["sentiment"]

    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        confidence = DEFAULT_RESULT["confidence"]

    risk_level = raw.get("risk_level")
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = DEFAULT_RESULT["risk_level"]

    return {
        "mood": mood,
        "sentiment": sentiment,
        "confidence": float(confidence),
        "risk_level": risk_level,
    }
