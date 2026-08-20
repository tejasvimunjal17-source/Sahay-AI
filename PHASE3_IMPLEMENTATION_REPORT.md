# PHASE 3 IMPLEMENTATION REPORT — Sahay AI
## AI Engine (OpenRouter + Mood Analysis + Safety + Response Generation)

## 1. Summary

Implemented the AI engine approved in `PHASE3_PRE_IMPLEMENTATION_AUDIT.md`:
a real OpenRouter client (timeout, bounded retries, rate-limit handling,
response validation, safe logging), five separated chatbot modules
(system prompt, mood analyzer, safety, response generator), and wired the
existing Phase 1/2 chat UI (`components/chatbot_launcher.py`,
`pages/companion.py`) to the real pipeline in place of the fixed
placeholder string. No conversation database, no new pages, no other
Phase 3+/4+ feature was added.

## 2. Files created

- `chatbot/system_prompt.py` (Sahay's full identity/safety/language prompt)
- `chatbot/mood_analyzer.py`
- `chatbot/safety.py`
- `chatbot/response_generator.py`
- `tests/test_safety_static.py`
- `tests/test_openrouter_client_mock.py`
- `tests/test_ai_engine_mock.py`

## 3. Files modified

- `backend/openrouter_client.py` — full rewrite (was a raising stub)
- `config.py` — added `base_url` to `OpenRouterConfig` (audit finding #1)
- `.env.example`, `.streamlit/secrets.toml.example` — added `OPENROUTER_BASE_URL`
- `requirements.txt` — uncommented `requests>=2.31`, `tenacity>=8.2` (tenacity listed but not currently imported — see §7)
- `components/chatbot_launcher.py` — `send_message()` now calls `chatbot.response_generator.generate_response()`
- `pages/companion.py` — added a language selector (English/Hindi/Hinglish, session-state only) and an "OpenRouter not connected" notice when unconfigured
- `tests/test_static_security.py` — check #5 updated per audit finding #2 (allowlist `backend/openrouter_client.py` instead of globally rejecting all HTTP calls); also fixed a pre-existing hardcoded-total-count bug while touching this file (documented in §8)
- `tests/README.md` — updated with the four new test files

**Untouched**: every migration, `backend/auth.py`, `backend/supabase_client.py`,
`backend/supabase_admin_client.py`, `backend/audit_log.py`,
`components/sidebar.py`, `components/landing.py`, `streamlit_app.py`'s
auth gate logic, every page other than `companion.py`, `content/*`
(crisis resources still empty, as required), `exports/*` (still stubs).

## 4. Architecture decisions

- **Safety runs before AND after the model, never depends on it.**
  `chatbot/response_generator.py`'s call order is fixed:
  `screen_input()` → [crisis/block short-circuit, model never called] →
  `analyze_mood()` → OpenRouter call → `screen_output()` → [block
  override] → return. Verified by `test_ai_engine_mock.py`, which counts
  actual model-call invocations and confirms 0 for crisis/blocked input.
- **No conversation persistence.** `chat_history` stays a plain
  `list[dict]` sourced from `st.session_state`, exactly as Phase 1/2 left
  it — matches the audit's §6 recommendation, confirmed by this
  implementation not touching any migration or Supabase table.
- **Language stays session-state only** (a `pages/companion.py`
  selectbox, `st.session_state["sahay_language"]`), not read from
  `profiles.preferred_language` — avoids coupling the AI engine to the
  auth module this phase, per the audit's recommendation to defer that
  coupling to Phase 4.
- **`requests` is imported lazily** inside `_post_with_retries()`, not at
  module level — confirmed by direct testing (§6) that
  `backend.openrouter_client` and all `chatbot/*` modules import cleanly
  in an environment without `requests`/`supabase` installed, matching
  the same discipline already used for `backend/supabase_client.py` in
  Phase 2.
- **Chain-of-thought defense in depth**: the system prompt instructs no
  reasoning disclosure, AND `openrouter_client.py` strips any
  `<think>...</think>`-shaped block as a backstop — verified this strip
  actually removes such content while preserving the real reply (§6).

## 5. Security decisions

- **API key never leaves the Authorization header.** Verified by
  `test_openrouter_client_mock.py`: the key is present in the request
  header, absent from the request body, absent from every error message
  raised (401/403/429 cases), and absent from the returned reply text.
- **429 is never auto-retried** — confirmed exactly one HTTP call is made
  on a 429 response, distinct from 5xx/timeout handling (which retries up
  to `MAX_RETRIES=2` additional times with exponential backoff).
- **No raw exception text reaches the user or the log at INFO+ with
  sensitive content** — every `OpenRouterError` subclass carries a
  pre-written, user-safe message; the underlying exception is logged
  separately (status code / exception type only, never headers/body).
- **Deterministic safety is the primary control**, not an LLM
  instruction — `chatbot/safety.py` has zero dependency on OpenRouter and
  is fully testable offline (§6, 41/41 static checks).
- **No invented crisis resources** — `crisis_response_text()` reads
  `content.crisis_resources.CRISIS_RESOURCES` (still `[]`) and produces a
  graceful fallback message when empty, never a fabricated number.
  Verified by `test_safety_static.py`.

## 6. Tests performed — exact results

### STATIC (no network, no mocking)

| Test | Result |
|---|---|
| `python3 -m py_compile` on all 51 `.py` files | **PASS** — 0 failures |
| `chatbot/*` and `backend/openrouter_client.py` import cleanly with no `requests` package installed | **PASS** — confirms lazy-import discipline |
| `tests/test_import_guard.py` | **PASS** — 1/1 |
| `tests/test_navigation_consistency.py` | **PASS** — 4/4 |
| `tests/test_static_security.py` | **PASS** — 14/14 (includes the updated OpenRouter-scoping check) |
| `tests/test_safety_static.py` | **PASS** — 41/41 (crisis detection, medical/medication/dependency/injection blocking, normal-message non-false-positives, output screening, non-clinical crisis-text framing) |

### MOCK (fake Supabase / fake `requests` / monkeypatched OpenRouter calls — not live)

| Test | Result |
|---|---|
| `tests/test_auth_mock.py` (Phase 2, re-run for regression) | **PASS — MOCK** — 12/12 |
| `tests/test_openrouter_client_mock.py` | **PASS — MOCK** — 23/23 (config validation, successful response, key non-leakage, chain-of-thought stripping, malformed/empty response, 429 no-retry, 500 bounded-retry, timeout bounded-retry, 401 no-leak, JSON-mode parsing) |
| `tests/test_ai_engine_mock.py` | **PASS — MOCK** — 23/23 (mood classification passthrough + field-level coercion, crisis/block short-circuits with model-call counting, normal flow, output-screening override, error handling, system-prompt non-leakage) |

### End-to-end (stub-driven Streamlit execution, real UI code path)

| Test | Result |
|---|---|
| Landing page, unconfigured OpenRouter/Supabase | **PASS** |
| Demo Mode entry | **PASS** |
| All 14 pages render (including the newly-wired `companion.py`) | **PASS** — 16/16 (landing + demo entry + 14 pages) |
| Suggestion chip click in Demo Mode, OpenRouter unconfigured → friendly "not connected" reply, no crash | **PASS** (verified reply text and `safety_action` field, not just "no exception") |
| Typed crisis message ("I want to end my life") through the real `companion.py` page → deterministic crisis response, no model call | **PASS** |
| Phase 1/2 regression: sidebar collapse, nav click, Exit Demo Mode, Google button (unconfigured, stays on landing), Demo Mode entry, auth gate redirect, chatbot launcher toggle | **PASS** — 7/7 |

### LIVE

| Test | Result |
|---|---|
| Any real OpenRouter API call | **NOT TESTED** — no network access in this environment (confirmed: the real `requests` package IS installed here, unlike `supabase`/`streamlit`, but no outbound network reaches `openrouter.ai`; see §8 for how this was discovered and handled) |
| OpenRouter timeout/rate-limit against the real service | **NOT TESTED** |
| Any of the 16 requested conversation scenarios (normal/stressed/anxious/lonely/exam-stress/etc.) against a real model | **NOT TESTED** — the safety-relevant ones (self-harm, medical, medication, injection) are covered by STATIC tests instead, since they never reach the model at all by design; the ones that would reach a real model (normal conversation, exam stress, etc.) are covered by MOCK tests with a fake model response, not a real one |
| Hindi/Hinglish output quality from a real model | **NOT TESTED** — the language parameter is confirmed to be correctly threaded into the system prompt (`test_ai_engine_mock.py`), but actual generation quality in Hindi/Hinglish requires a real model call |

**No live result is fabricated anywhere in this report.**

## 7. Known limitations

- **OpenRouter has never been called for real.** Everything above the
  `requests.post()` call itself is proven via mock; the actual API
  contract (does OpenRouter's real response shape match what
  `chat_completion()` expects?) is unverified. Recommend your first
  real-world test be a single manual `chat_completion()` call with a
  real key before trusting this in front of users.
- **`tenacity` is listed in `requirements.txt` but not actually used** —
  `backend/openrouter_client.py`'s retry logic is hand-rolled
  (`time.sleep` + a loop), not `tenacity`-based, even though the
  Phase 0/2/3 audits all referenced "requests + tenacity" as the pattern
  to follow (matching LearnMate's reference implementation). This was a
  scope simplification during implementation, not caught until writing
  this report — the hand-rolled version is fully tested and correct, but
  it's an inconsistency with what was planned. **Flagging rather than
  silently leaving it**: either remove `tenacity` from `requirements.txt`
  (if the hand-rolled approach is acceptable going forward) or refactor
  to use it — your call, not decided unilaterally here since it's a
  style/dependency choice, not a correctness bug.
- **Safety keyword coverage is inherently incomplete** — restated from
  the Phase 0 audit's risk assessment: `chatbot/safety.py`'s patterns
  catch the phrasings tested in `test_safety_static.py`, not every
  possible phrasing. This is a known, structural limitation of
  deterministic pattern matching, not something this implementation
  claims to have solved completely.
- **Prompt injection resistance is a backstop, not a guarantee** — the
  same caveat as above; `_PROMPT_INJECTION_PATTERNS` catches the common
  phrasings tested, and the system prompt separately instructs the model
  to resist injection, but a sufficiently creative adversarial prompt
  that matches neither could still get further than intended. Untestable
  without a real model to see how it actually responds under adversarial
  input.
- **`OPENROUTER_MODEL` and `OPENROUTER_BASE_URL` both have defaults** in
  `config.py`, meaning `OpenRouterConfig.is_configured` is effectively
  gated only by whether `OPENROUTER_API_KEY` is set. This is intentional
  and reasonable (sensible defaults), but worth knowing — "configured"
  doesn't mean "you've reviewed the base URL/model," just that a key is
  present.

## 8. Bugs found and fixed during this session (documented, not silently corrected)

1. **`chatbot/safety.py`'s diagnostic-output regex was too narrow.**
   `test_ai_engine_mock.py` caught that `"You have generalized anxiety
   disorder."` was NOT being blocked by output screening — the original
   pattern only matched the literal phrase "an anxiety disorder," missing
   "generalized anxiety disorder" and similar common clinical phrasing.
   **Fixed** by widening the pattern to allow up to 2 descriptor words
   between "have" and the condition name. Re-verified: `test_safety_static.py`
   still 41/41, `test_ai_engine_mock.py` now 23/23 (was 21/23).
2. **`chatbot/mood_analyzer.py` didn't catch `OpenRouterNotConfiguredError`
   specifically**, so an entirely expected state (no OpenRouter
   configured, the default in this environment) was falling through to
   the generic `except Exception` handler and logging a full ERROR-level
   traceback for what isn't actually an error. **Fixed** by adding an
   explicit `except OpenRouterNotConfiguredError` branch logging at INFO
   level instead. Re-verified via the end-to-end demo-mode chip-click
   test — logs are now clean.
3. **My own test file had a bug**, not the app: an early version of
   `test_openrouter_client_mock.py` tried to test a "missing
   `OPENROUTER_MODEL`" scenario, but `config.py`'s `OPENROUTER_MODEL`
   has a default value (`openai/gpt-4o-mini`), so clearing the env var
   doesn't actually leave the config unconfigured — the test's premise
   was wrong. This surfaced as a real (if harmless) DNS lookup to a fake
   hostname, revealing along the way that this sandbox actually has the
   real `requests` package installed. **Fixed** by correcting the test's
   understanding of which field genuinely has no default (only
   `OPENROUTER_API_KEY`), and by installing the fake `requests` module
   before any `chat_completion()` call regardless of config state, so no
   future test in this file can accidentally reach the real network.
4. **`tests/test_static_security.py` had a hardcoded total-check count**
   (`/12` in a print statement) left over from before the check was
   split into two (5 and 5b) — would have silently shown a wrong
   fraction. **Fixed** with a running counter, the same fix already
   applied to `test_auth_mock.py` in the Phase 2 session.

## 9. Phase 1 regression — checked

Sidebar collapse/expand, active-page nav click, Exit Demo Mode, Google
button (unconfigured → friendly notice, stays on landing, no fake
login), Demo Mode entry, chatbot launcher open/close — all re-verified
against real session-state assertions this session (§6, "Phase 1/2
regression" row, 7/7 passed). Sahay AI branding, the heart+speech-bubble
icon, and the sidebar's structure are all in files (`components/theme.py`,
`components/sidebar.py`, `assets/sahay_icon.svg`) that were not touched
this phase.

## 10. Phase 2 regression — checked

The auth gate (`streamlit_app.py`'s `main()`) correctly still forces an
unauthenticated, non-demo session back to the landing page (§6). No
migration, RLS policy, or Supabase client file was modified — confirmed
by the file-modification list in §3 and by `test_static_security.py`'s
unchanged checks for role-protection, RLS scoping, and service-role
isolation, all still 14/14 passing with the new Phase 3 code present.

## 11. Verification of deliverables

- `sahay-ai-phase3.zip` — packaged and confirmed present (see final
  message).
- LearnMate: `md5sum` of the uploaded zip confirmed identical to every
  previous phase's check (`5fa3f9b5...`) — untouched.
- No SQLite: confirmed via grep (the only hit is `test_static_security.py`'s
  own detection regex, not an actual usage).
- No hardcoded secrets: confirmed via grep.

## 12. Recommended next phase

**Phase 4 (conversation persistence + full chat UI)** is the natural next
step now that the AI engine works end-to-end in mock/demo form: it would
add the `conversations`/`messages` tables deferred in this phase's §3/§6
decision, wire `profiles.preferred_language` into the language selector
(replacing the session-state-only approach), and connect mood/risk data
to actual storage rather than being discarded after each turn. Before
that, I'd suggest you personally run one real OpenRouter call against
this implementation (a real API key, even just via `curl` or a quick
script) to confirm the response shape this code expects actually matches
what OpenRouter returns — that's the single biggest unverified
assumption carried out of this phase.
