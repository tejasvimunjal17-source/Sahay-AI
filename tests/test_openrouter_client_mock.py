"""
tests/test_openrouter_client_mock.py
---------------------------------------
MOCK VERIFICATION — NOT a live OpenRouter test. Installs a fake
`requests` module so backend/openrouter_client.py's actual control flow
(timeout/retry, rate-limit handling, response validation, error mapping)
can be exercised with zero network access.

Run: python3 tests/test_openrouter_client_mock.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType

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


class FakeResponse:
    def __init__(self, status_code: int, json_data=None, raw_text: str | None = None):
        self.status_code = status_code
        self._json_data = json_data
        self._raw_text = raw_text

    def json(self):
        if self._raw_text is not None:
            raise ValueError("not valid json")
        return self._json_data


class FakeRequestsModule:
    """Installed as sys.modules['requests']. `responder` is a callable the
    test sets per-scenario: (url, headers, json, timeout) -> FakeResponse
    or raises an exception."""

    def __init__(self):
        self.responder = None
        self.calls = []

        class exceptions:
            class Timeout(Exception):
                pass

            class ConnectionError(Exception):
                pass

            class RequestException(Exception):
                pass

        self.exceptions = exceptions

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.responder(url, headers, json, timeout)


def install_fake_requests() -> FakeRequestsModule:
    fake = FakeRequestsModule()
    mod = ModuleType("requests")
    mod.post = fake.post
    mod.exceptions = fake.exceptions
    sys.modules["requests"] = mod
    return fake


def fresh_modules_with_config(configured: bool = True) -> None:
    if configured:
        os.environ["OPENROUTER_API_KEY"] = "sk-fake-test-key-do-not-leak"
        os.environ["OPENROUTER_BASE_URL"] = "https://fake.openrouter.test/api/v1"
        os.environ["OPENROUTER_MODEL"] = "fake/test-model"
    else:
        for k in ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "OPENROUTER_MODEL"):
            os.environ.pop(k, None)
    for mod in list(sys.modules):
        if mod in ("config",) or mod.startswith("backend."):
            del sys.modules[mod]


def run() -> int:
    # ---- 1. Missing configuration ----
    # Install the fake `requests` module FIRST — this sandbox actually has
    # the real `requests` package installed (unlike `supabase`/`streamlit`),
    # discovered when an early version of this test made a real DNS lookup
    # to a fake hostname and failed with a network error instead of the
    # expected OpenRouterNotConfiguredError. Installing the fake module
    # before any chat_completion() call, regardless of config state,
    # guarantees no real network attempt ever happens in this test file.
    fake_requests = install_fake_requests()

    fresh_modules_with_config(configured=False)
    import backend.openrouter_client as orc
    try:
        orc.chat_completion([{"role": "user", "content": "hi"}])
        check("Missing config raises OpenRouterNotConfiguredError", False)
    except orc.OpenRouterNotConfiguredError:
        check("Missing config raises OpenRouterNotConfiguredError", True)

    # OPENROUTER_MODEL and OPENROUTER_BASE_URL both have sensible defaults in
    # config.py (openai/gpt-4o-mini and the real OpenRouter API URL) — only
    # OPENROUTER_API_KEY has no default, so it's the only field that can
    # actually leave the config "unconfigured" via a missing env var. This
    # was discovered while writing this test (an earlier version incorrectly
    # assumed clearing OPENROUTER_MODEL alone would trigger
    # OpenRouterNotConfiguredError — it doesn't, because the default fills
    # it in). Documenting the correction here rather than silently fixing it.
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ["OPENROUTER_BASE_URL"] = "https://fake.test/api/v1"
    os.environ["OPENROUTER_MODEL"] = "fake/test-model"
    for mod in list(sys.modules):
        if mod in ("config",) or mod.startswith("backend."):
            del sys.modules[mod]
    import backend.openrouter_client as orc2
    try:
        orc2.chat_completion([{"role": "user", "content": "hi"}])
        check("Missing OPENROUTER_API_KEY (the only field with no default) raises OpenRouterNotConfiguredError", False)
    except orc2.OpenRouterNotConfiguredError:
        check("Missing OPENROUTER_API_KEY (the only field with no default) raises OpenRouterNotConfiguredError", True)

    # ---- Fully configured from here on ----
    fresh_modules_with_config(configured=True)
    import backend.openrouter_client as orc3

    # ---- 2. Successful mocked response ----
    fake_requests.responder = lambda *a: FakeResponse(200, {
        "choices": [{"message": {"content": "That sounds stressful. Want to talk through it?"}}]
    })
    reply = orc3.chat_completion([{"role": "user", "content": "I'm stressed about exams"}])
    check("Successful mocked response returns the message content", reply == "That sounds stressful. Want to talk through it?")

    # ---- 3. API key never appears in the returned reply ----
    check("API key not present in the returned reply", "sk-fake-test-key-do-not-leak" not in reply)

    # ---- 4. API key sent in Authorization header, not query params or body ----
    last_call = fake_requests.calls[-1]
    check("API key sent via Authorization header", "sk-fake-test-key-do-not-leak" in last_call["headers"].get("Authorization", ""))
    check("API key NOT present in the request body/payload", "sk-fake-test-key-do-not-leak" not in str(last_call["json"]))

    # ---- 5. Chain-of-thought stripping ----
    fake_requests.responder = lambda *a: FakeResponse(200, {
        "choices": [{"message": {"content": "<think>the user seems stressed, I should be supportive</think>Here's a thought — try a short walk?"}}]
    })
    reply2 = orc3.chat_completion([{"role": "user", "content": "hi"}])
    check("<think> reasoning block is stripped from the reply", "<think>" not in reply2 and "seems stressed" not in reply2)
    check("Actual reply content survives the strip", "short walk" in reply2)

    # ---- 6. Malformed response: invalid JSON ----
    fake_requests.responder = lambda *a: FakeResponse(200, raw_text="not json")
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("Invalid JSON response raises OpenRouterResponseError", False)
    except orc3.OpenRouterResponseError:
        check("Invalid JSON response raises OpenRouterResponseError", True)

    # ---- 7. Malformed response: missing expected keys ----
    fake_requests.responder = lambda *a: FakeResponse(200, {"unexpected": "shape"})
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("Missing-keys response raises OpenRouterResponseError", False)
    except orc3.OpenRouterResponseError:
        check("Missing-keys response raises OpenRouterResponseError", True)

    # ---- 8. Empty content ----
    fake_requests.responder = lambda *a: FakeResponse(200, {"choices": [{"message": {"content": "   "}}]})
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("Empty-content response raises OpenRouterResponseError", False)
    except orc3.OpenRouterResponseError:
        check("Empty-content response raises OpenRouterResponseError", True)

    # ---- 9. Rate limit (429) — must NOT retry, must raise a friendly error ----
    call_count_before = len(fake_requests.calls)
    fake_requests.responder = lambda *a: FakeResponse(429)
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("429 raises OpenRouterRateLimitError", False)
    except orc3.OpenRouterRateLimitError as exc:
        check("429 raises OpenRouterRateLimitError", True)
        check("429 does not leak internal detail in its message", "429" not in str(exc))
    calls_made = len(fake_requests.calls) - call_count_before
    check("429 results in exactly ONE request (no automatic retry)", calls_made == 1, f"made {calls_made} calls")

    # ---- 10. Generic 500 error — retries then fails gracefully ----
    call_count_before = len(fake_requests.calls)
    fake_requests.responder = lambda *a: FakeResponse(500)
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("Persistent 500 eventually raises an OpenRouterError", False)
    except orc3.OpenRouterError:
        check("Persistent 500 eventually raises an OpenRouterError", True)
    calls_made = len(fake_requests.calls) - call_count_before
    check("500 triggers more than one attempt (retry occurred)", calls_made > 1, f"made {calls_made} calls")
    check("500 does not retry forever (bounded attempts)", calls_made <= orc3.MAX_RETRIES + 1, f"made {calls_made} calls")

    # ---- 11. Timeout — retries then fails gracefully ----
    def timeout_responder(*a):
        raise fake_requests.exceptions.Timeout("simulated timeout")
    fake_requests.responder = timeout_responder
    call_count_before = len(fake_requests.calls)
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("Persistent timeout raises OpenRouterTimeoutError", False)
    except orc3.OpenRouterTimeoutError:
        check("Persistent timeout raises OpenRouterTimeoutError", True)
    calls_made = len(fake_requests.calls) - call_count_before
    check("Timeout triggers bounded retries, not infinite", 1 <= calls_made <= orc3.MAX_RETRIES + 1, f"made {calls_made} calls")

    # ---- 12. 401/403 (auth error) — friendly message, no key leak ----
    fake_requests.responder = lambda *a: FakeResponse(401)
    try:
        orc3.chat_completion([{"role": "user", "content": "hi"}])
        check("401 raises a generic OpenRouterError", False)
    except orc3.OpenRouterError as exc:
        check("401 raises a generic OpenRouterError", True)
        check("401 error message does not leak the API key", "sk-fake-test-key-do-not-leak" not in str(exc))

    # ---- 13. JSON-mode completion (used by mood_analyzer) ----
    fake_requests.responder = lambda *a: FakeResponse(200, {
        "choices": [{"message": {"content": '{"mood": "Stressed", "sentiment": "negative", "confidence": 0.8, "risk_level": "low"}'}}]
    })
    parsed = orc3.chat_completion_json([{"role": "user", "content": "classify this"}])
    check("chat_completion_json parses valid JSON content", parsed == {"mood": "Stressed", "sentiment": "negative", "confidence": 0.8, "risk_level": "low"})

    fake_requests.responder = lambda *a: FakeResponse(200, {
        "choices": [{"message": {"content": "not actually json"}}]
    })
    try:
        orc3.chat_completion_json([{"role": "user", "content": "classify this"}])
        check("chat_completion_json raises OpenRouterResponseError on non-JSON content", False)
    except orc3.OpenRouterResponseError:
        check("chat_completion_json raises OpenRouterResponseError on non-JSON content", True)

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (MOCK verification — fake `requests` module, no network)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
