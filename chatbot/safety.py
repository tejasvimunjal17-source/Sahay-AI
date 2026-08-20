"""
chatbot/safety.py
--------------------
PHASE 3 IMPLEMENTATION.

Deterministic, pattern-based safety screening — the PRIMARY safety
control, independent of the LLM. Per the master spec: "do not rely on
the LLM alone for safety." chatbot/system_prompt.py's instructions are a
second, reinforcing layer, not a substitute for this one.

screen_input() runs on the raw user message BEFORE any OpenRouter call —
a crisis or blocked match here means the model is never even consulted
for that turn; the deterministic response is returned directly.

screen_output() runs on the model's generated reply BEFORE it's shown to
the user — catches cases where the model's own output drifts into
diagnostic-sounding language, claims professional identity, or otherwise
violates a rule the system prompt asked it not to.

CRISIS RESOURCES: reads from content/crisis_resources.py, which is
intentionally empty until verified India-specific resources are added
(see that module's docstring). This module MUST handle the empty-list
case gracefully — never invents a phone number or URL to fill the gap.
"""

from __future__ import annotations

import re

from content.crisis_resources import CRISIS_RESOURCES

# ---------------------------------------------------------------------------
# Pattern categories (case-insensitive, word-boundary where relevant).
# These are intentionally not exhaustive — they're a deterministic
# backstop layered with the system prompt's instructions, not a claim of
# perfect coverage. See PHASE3_IMPLEMENTATION_REPORT.md's "known
# limitations" section for an honest statement of that boundary.
# ---------------------------------------------------------------------------

_SELF_HARM_PATTERNS = [
    r"\bkill(ing)?\s+myself\b", r"\bend(ing)?\s+my\s+life\b", r"\bsuicid",
    r"\bwant(ed)?\s+to\s+die\b", r"\bdon'?t\s+want\s+to\s+(be\s+alive|live)\b",
    r"\bself[\s-]?harm", r"\bhurt(ing)?\s+myself\b", r"\bcut(ting)?\s+myself\b",
    r"\bno\s+reason\s+to\s+live\b", r"\bbetter\s+off\s+dead\b",
    r"\bplan\s+to\s+kill\b",
]

_VIOLENCE_PATTERNS = [
    r"\bkill(ing)?\s+(him|her|them|someone|somebody)\b",
    r"\bhurt(ing)?\s+(him|her|them|someone|somebody)\b",
    r"\battack(ing)?\s+(him|her|them|someone|somebody)\b",
    r"\bwant(ed)?\s+to\s+hurt\s+(him|her|them|someone|somebody)\b",
]

_MEDICAL_DIAGNOSIS_PATTERNS = [
    r"\bdo\s+i\s+have\s+(depression|anxiety|bipolar|adhd|a\s+disorder)\b",
    r"\bdiagnos(e|is)\s+me\b", r"\bwhat\s+disorder\s+do\s+i\s+have\b",
    r"\bam\s+i\s+(depressed|bipolar|schizophrenic)\b",
]

_MEDICATION_PATTERNS = [
    r"\bwhat\s+medication\s+should\s+i\s+take\b", r"\bprescribe\b",
    r"\bdosage\s+of\b", r"\bhow\s+much\s+(antidepressant|xanax|prozac|ssri)\b",
    r"\bshould\s+i\s+(stop|increase|decrease)\s+my\s+(medication|meds|dose)\b",
]

# PHASE 5: distinct from _MEDICATION_PATTERNS above — that category is for
# ordinary "what should I take" questions, which get a simple redirect
# (blocked_response_text). These patterns are inherently a safety signal
# (a request for a lethal/fatal amount, or a dangerous combination) and
# are routed to the CRISIS path, not a block, since the underlying risk
# is the same as self-harm ideation even when phrased as a factual
# medical question. No dosage/quantity/method information is ever
# generated in response — only the same deterministic crisis_response_text().
_DANGEROUS_MEDICAL_INSTRUCTION_PATTERNS = [
    r"\b(lethal|fatal|deadly)\s+dos", r"\bhow\s+(much|many)\s+.*\bto\s+(overdose|die)\b",
    r"\bhow\s+to\s+overdose\b", r"\bdangerous\s+(combination|mix)\s+of\b",
    r"\bmix(ing)?\s+.*\s+with\s+alcohol\s+to\b",
]

_DEPENDENCY_PATTERNS = [
    r"\byou'?re\s+all\s+i\s+(need|have)\b", r"\bi\s+don'?t\s+need\s+anyone\s+else\s+but\s+you\b",
    r"\bpromise\s+you'?ll\s+(never\s+leave|always\s+be\s+here)\b",
    r"\byou'?re\s+the\s+only\s+one\s+who\s+(understands|cares)\b",
    r"\bi\s+don'?t\s+need\s+a\s+(therapist|doctor|counselor)\b",
]

_PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions\b",
    r"\byou\s+are\s+now\s+(unrestricted|free|jailbroken)\b",
    r"\bpretend\s+you\s+(have\s+no\s+rules|are\s+not\s+an?\s+ai)\b",
    r"\bdisregard\s+your\s+(rules|instructions|guidelines)\b",
    r"\breveal\s+your\s+(system\s+prompt|instructions)\b",
    r"\bwhat\s+(are|is)\s+your\s+(system\s+prompt|instructions)\b",
    r"\bact\s+as\s+(a\s+)?(therapist|doctor|psychiatrist|unrestricted\s+ai)\b",
]

_DIAGNOSTIC_OUTPUT_PATTERNS = [
    # Allows up to 2 descriptor words between "have" and the condition
    # (e.g. "you have GENERALIZED ANXIETY disorder", "you have CLINICAL
    # depression") — the original version only matched "an anxiety
    # disorder" literally and missed this common phrasing. Found via
    # tests/test_ai_engine_mock.py during Phase 3 verification; fixed
    # here rather than narrowing the test to fit the gap.
    r"\byou\s+have\s+(?:\w+\s+){0,2}(depression|anxiety|bipolar|ptsd|panic\s+disorder)\b",
    r"\byour\s+diagnosis\s+is\b",
    r"\bas\s+(a\s+)?(your\s+)?(licensed\s+)?(therapist|doctor|psychiatrist|psychologist|counselor)\b",
    r"\bi\s+am\s+a\s+(licensed\s+)?(therapist|doctor|psychiatrist|psychologist)\b",
]

_ACTION_CRISIS = "crisis"
_ACTION_BLOCK = "block"
_ACTION_ALLOW = "allow"


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def screen_input(message: str) -> dict:
    """Screens a raw user message BEFORE any model call. Returns
    {"action": "crisis" | "block" | "allow", "category": str | None}.

    "crisis" — self-harm/suicide/violence indicators. The caller must
    short-circuit straight to crisis_response_text(), skipping the model
    entirely for this turn.
    "block" — medical diagnosis / medication / dependency-manipulation /
    prompt-injection attempts. The caller should respond with a fixed
    redirect (see blocked_response_text()) rather than sending the raw
    message to the model, since even a well-instructed model can be
    inconsistent under adversarial phrasing.
    "allow" — proceed normally (mood analysis + model response).
    """
    if not message or not message.strip():
        return {"action": _ACTION_ALLOW, "category": None}

    if _matches_any(_SELF_HARM_PATTERNS, message) or _matches_any(_VIOLENCE_PATTERNS, message):
        return {"action": _ACTION_CRISIS, "category": "self_harm_or_violence"}

    if _matches_any(_DANGEROUS_MEDICAL_INSTRUCTION_PATTERNS, message):
        return {"action": _ACTION_CRISIS, "category": "dangerous_medical_instruction_request"}

    if _matches_any(_MEDICAL_DIAGNOSIS_PATTERNS, message):
        return {"action": _ACTION_BLOCK, "category": "medical_diagnosis_request"}

    if _matches_any(_MEDICATION_PATTERNS, message):
        return {"action": _ACTION_BLOCK, "category": "medication_request"}

    if _matches_any(_DEPENDENCY_PATTERNS, message):
        return {"action": _ACTION_BLOCK, "category": "dependency_or_replace_professional_help"}

    if _matches_any(_PROMPT_INJECTION_PATTERNS, message):
        return {"action": _ACTION_BLOCK, "category": "prompt_injection"}

    return {"action": _ACTION_ALLOW, "category": None}


def screen_output(response: str) -> dict:
    """Screens the model's generated reply BEFORE it's shown to the user.
    Returns {"action": "block" | "allow", "category": str | None}.
    "block" means the reply must be replaced with safe_fallback_text(),
    never shown as-is."""
    if not response or not response.strip():
        return {"action": _ACTION_BLOCK, "category": "empty_response"}

    if _matches_any(_DIAGNOSTIC_OUTPUT_PATTERNS, response):
        return {"action": _ACTION_BLOCK, "category": "diagnostic_or_professional_claim"}

    return {"action": _ACTION_ALLOW, "category": None}


# ---------------------------------------------------------------------------
# Fixed, deterministic response text — never generated by the model.
# ---------------------------------------------------------------------------

def crisis_response_text() -> str:
    base = (
        "Thank you for telling me — that took courage, and I want you to be safe. "
        "I'm an AI companion, not a crisis service, so please reach out to a trusted "
        "person right now if you can, and consider contacting local emergency services "
        "or a crisis helpline in your area."
    )
    if CRISIS_RESOURCES:
        lines = "\n".join(
            f"- {r['name']}: {r['contact']}" + (f" ({r['availability']})" if r.get("availability") else "")
            for r in CRISIS_RESOURCES
        )
        base += "\n\nSome resources that may help:\n" + lines
    else:
        base += (
            "\n\nIf you're a student in India, your campus counseling office or a "
            "trusted teacher, family member, or friend is a good place to start right "
            "now — verified helpline numbers will appear here once they've been added "
            "to Sahay's resource list."
        )
    return base


def blocked_response_text(category: str | None) -> str:
    if category == "medical_diagnosis_request":
        return (
            "I'm not able to diagnose conditions — I'm an AI wellness companion, not a "
            "medical professional. A doctor or licensed counselor can properly assess "
            "what you're experiencing. I'm glad to just listen or talk through how "
            "you're feeling, if that would help."
        )
    if category == "medication_request":
        return (
            "I can't advise on medications or dosages — that needs to come from a "
            "doctor or pharmacist who knows your full situation. I'm happy to support "
            "you in other ways, like talking through what's going on."
        )
    if category == "dependency_or_replace_professional_help":
        return (
            "I care about how you're doing, and I'm glad to be here to talk — but I'm "
            "an AI companion, not a substitute for the people and professionals in "
            "your life. Please keep those connections going alongside our chats."
        )
    if category == "prompt_injection":
        return (
            "I'm Sahay, your AI wellness companion — that's who I am here to be. "
            "What's on your mind today?"
        )
    return safe_fallback_text()


def safe_fallback_text() -> str:
    return (
        "I want to make sure I respond to you thoughtfully — could you tell me a bit "
        "more about what's on your mind?"
    )
