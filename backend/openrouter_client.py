"""
backend/openrouter_client.py
-------------------------------
PHASE 3 IMPLEMENTATION.

Thin wrapper around OpenRouter's OpenAI-compatible Chat Completions API.
Structurally adapted from LearnMate AI's backend/openrouter_client.py
pattern (see PHASE0_AUDIT.md §B) — `requests` + bounded retry/backoff,
trimmed history, try/except mapped to friendly errors, never raises a
raw requests/network exception past this module.

SECURITY / SAFETY NOTES:
- OPENROUTER_API_KEY is read only from config.OPENROUTER_CONFIG (env var
  / Streamlit secrets) and is placed only in the outgoing request's
  Authorization header — never logged, never included in any exception
  message, never returned to a caller.
- Retries are DELIBERATELY LIMITED and ONLY apply to genuinely transient
  failures (connection errors, timeouts, 5xx). A 429 (rate limit) is
  NEVER retried automatically — see generate_response's rate-limit
  handling below; hammering a rate-limited endpoint would make things
  worse, not better.
- Response content is validated before being trusted: this module never
  hands back an empty string, a non-string, or an unparsed raw API
  response to its caller.
- A lightweight defensive strip removes any `<think>...</think>`-style
  reasoning block some models may emit even when not asked to, so a
  chain-of-thought never reaches the UI even if the system prompt's
  instruction not to produce one is imperfectly followed by the model.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.logging_config import get_logger
from config import OPENROUTER_CONFIG

logger = get_logger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2  # total attempts = MAX_RETRIES + 1, only for transient failures
RETRY_BACKOFF_BASE_SECONDS = 1.0
MAX_TOKENS_DEFAULT = 600
TEMPERATURE_DEFAULT = 0.7


class OpenRouterNotConfiguredError(RuntimeError):
    """Raised when OPENROUTER_API_KEY / OPENROUTER_BASE_URL / OPENROUTER_MODEL are missing."""


class OpenRouterError(RuntimeError):
    """Base class for all OpenRouter call failures. Message is safe to
    show to a user as-is (never contains the API key or raw response body)."""


class OpenRouterTimeoutError(OpenRouterError):
    pass


class OpenRouterRateLimitError(OpenRouterError):
    pass


class OpenRouterResponseError(OpenRouterError):
    """Malformed, empty, or unexpected-shape response from the API."""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_CONFIG.api_key}",
        "Content-Type": "application/json",
        # OpenRouter-recommended attribution headers — no secret data.
        "HTTP-Referer": "https://sahay.ai",
        "X-Title": "Sahay AI",
    }


def _strip_reasoning_blocks(text: str) -> str:
    """Defensive strip of any <think>...</think>-style reasoning block.
    See module docstring — this is a backstop, not the primary control
    (the primary control is the system prompt instructing no such output)."""
    return _THINK_BLOCK_RE.sub("", text).strip()


def _post_with_retries(payload: dict) -> Any:
    """Makes the HTTP call with a small number of retries, but ONLY for
    connection errors / timeouts / 5xx — never for 4xx (including 429,
    handled separately by the caller so it isn't silently retried)."""
    import time
    import requests

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{OPENROUTER_CONFIG.base_url.rstrip('/')}/chat/completions",
                headers=_headers(),
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("OpenRouter request timed out (attempt %d/%d)", attempt + 1, MAX_RETRIES + 1)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("OpenRouter connection error (attempt %d/%d)", attempt + 1, MAX_RETRIES + 1)
        else:
            if response.status_code >= 500 and attempt < MAX_RETRIES:
                logger.warning("OpenRouter server error %s (attempt %d/%d)",
                                response.status_code, attempt + 1, MAX_RETRIES + 1)
                last_exc = None
                time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            return response

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt))

    # Exhausted retries on a transient failure.
    raise OpenRouterTimeoutError(
        "Sahay couldn't reach its AI service in time. Please try again in a moment."
    ) from last_exc


def chat_completion(
    messages: list[dict],
    *,
    temperature: float = TEMPERATURE_DEFAULT,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    json_mode: bool = False,
) -> str:
    """Low-level call: sends `messages` (OpenAI-style role/content dicts,
    caller's responsibility to include the system prompt as the first
    message) and returns the validated text content of the first choice.

    Raises OpenRouterNotConfiguredError / OpenRouterTimeoutError /
    OpenRouterRateLimitError / OpenRouterResponseError / OpenRouterError
    on any failure — never a raw `requests` exception, never an
    unvalidated/empty string.

    NOT LIVE-TESTED in this environment (no network access) — see
    PHASE3_IMPLEMENTATION_REPORT.md for exactly what was and wasn't
    exercised (static/mock only).
    """
    if not OPENROUTER_CONFIG.is_configured:
        raise OpenRouterNotConfiguredError(
            "OPENROUTER_API_KEY, OPENROUTER_BASE_URL, and OPENROUTER_MODEL must all be "
            "set before any AI response can be generated."
        )

    payload: dict = {
        "model": OPENROUTER_CONFIG.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    response = _post_with_retries(payload)

    if response.status_code == 429:
        logger.warning("OpenRouter rate limit hit (429) — not retrying automatically")
        raise OpenRouterRateLimitError(
            "Sahay is getting a lot of requests right now. Please wait a moment and try again."
        )
    if response.status_code == 401 or response.status_code == 403:
        # Never include the key or raw body in the message/log.
        logger.error("OpenRouter auth error (status %s) — check OPENROUTER_API_KEY", response.status_code)
        raise OpenRouterError("Sahay's AI service isn't configured correctly. Please try again later.")
    if response.status_code >= 400:
        logger.error("OpenRouter request error (status %s)", response.status_code)
        raise OpenRouterError("Sahay couldn't process that message. Please try again.")

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("OpenRouter returned non-JSON response (status %s)", response.status_code)
        raise OpenRouterResponseError("Sahay received an unexpected response. Please try again.") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("OpenRouter response missing expected fields (keys present: %s)",
                     list(data.keys()) if isinstance(data, dict) else type(data).__name__)
        raise OpenRouterResponseError("Sahay received an unexpected response. Please try again.") from exc

    if not isinstance(content, str) or not content.strip():
        logger.error("OpenRouter returned an empty or non-string content field")
        raise OpenRouterResponseError("Sahay didn't have a response that time. Please try again.")

    return _strip_reasoning_blocks(content)


def chat_completion_json(messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 200) -> dict:
    """Convenience wrapper for structured (JSON) completions, used by
    chatbot/mood_analyzer.py. Parses the returned text as JSON and raises
    OpenRouterResponseError if it isn't valid JSON — callers should treat
    that as "classification unavailable this turn", not a crash."""
    text = chat_completion(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("OpenRouter JSON-mode response failed to parse as JSON")
        raise OpenRouterResponseError("Sahay couldn't classify that message this time.") from exc
