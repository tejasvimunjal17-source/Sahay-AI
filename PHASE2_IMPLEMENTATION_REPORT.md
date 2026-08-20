# PHASE 2 IMPLEMENTATION REPORT — Sahay AI
## Supabase Database + Authentication + Security Foundation

## 1. Phase 2 Summary

Implemented the Supabase database + authentication foundation approved in
`PHASE2_ARCHITECTURE_AUDIT.md`: two tables (`profiles`, `audit_logs`),
RLS on both, a database-level role-self-escalation trigger, a real
anon-key/service-role client split, and full Supabase Auth wiring
(email/password sign-up/login/logout/reset, Google OAuth structure) into
the existing Phase 1 landing page and sidebar. Demo Mode is preserved as
an explicit, no-account preview path that never touches Supabase.

No OpenRouter, mood analysis, conversation storage, or other Phase 3+
feature was added — confirmed by the static scans in §6.

## 2. Files created / modified — exact list

**Created:**
- `database/migrations/001_initial_schema.sql`
- `database/migrations/002_rls_policies.sql`
- `database/migrations/003_role_protection.sql`
- `backend/audit_log.py`
- `tests/test_import_guard.py`
- `tests/test_static_security.py`
- `tests/test_navigation_consistency.py`
- `tests/test_auth_mock.py`
- `tests/README.md`

**Rewritten (were Phase 1 stubs, now real implementations):**
- `backend/supabase_client.py`
- `backend/supabase_admin_client.py`
- `backend/auth.py`

**Modified:**
- `streamlit_app.py` (centralized auth gate, OAuth callback handling)
- `components/sidebar.py` (`render_sidebar()` now takes `authenticated`/
  `user`; bottom row shows real Log Out for authenticated users, Exit
  Demo Mode for demo users)
- `components/landing.py` (real email/password forms via `st.tabs`,
  wired Google button, Demo Mode preserved)
- `pages/profile.py` (reads/writes the real `profiles` row when
  authenticated; unchanged disabled-placeholder behavior in Demo Mode)
- `requirements.txt` (`supabase>=2.4` uncommented)
- `database/migrations/README.md` (describes the real migrations)

**Untouched:** every other Phase 1 page (`overview`, `companion`,
`mood_checkin`, `relaxation`, `wellness_dashboard`, `resources`,
`human_help`, `government_services`, `conversations`, `mood_history`,
`reports`, `privacy`, `settings`), `components/theme.py`,
`components/cards.py`, `components/topbar.py`,
`components/chatbot_launcher.py`, `content/*`, `chatbot/*` (still
stubs), `exports/*` (still stubs), `backend/logging_config.py`.

## 3. Database

**Migrations** (`database/migrations/`, applied in order):

| File | Purpose |
|---|---|
| `001_initial_schema.sql` | Creates `profiles` and `audit_logs`, plus an `updated_at`-maintaining trigger on `profiles` |
| `002_rls_policies.sql` | Enables RLS on both tables; `profiles` gets owner-scoped SELECT/INSERT/UPDATE; `audit_logs` gets RLS enabled with **zero** policies for `anon`/`authenticated` |
| `003_role_protection.sql` | Trigger rejecting any `profiles.role` change unless executed via the service-role connection |

**Tables** — exactly the two approved in the audit, confirmed by
`test_static_security.py` check #11 (`tables == {"profiles",
"audit_logs"}`):

- `profiles(id, display_name, preferred_language, onboarding_complete, role, created_at, updated_at)`
- `audit_logs(id, actor_type, actor_id, action, target, created_at)`

**Indexes**: primary keys only, plus `idx_audit_logs_actor` and
`idx_audit_logs_created_at` (added in `001_initial_schema.sql` rather
than a separate `002_indexes.sql`, per the audit's own recommendation
against an otherwise-empty migration file).

**RLS policies** (`profiles`): `profiles_select_own`,
`profiles_insert_own`, `profiles_update_own` — all `auth.uid() = id`.
No DELETE policy (see the migration's comment for why — deletion is
meant to route through the auth `ON DELETE CASCADE` from `auth.users`,
not a direct client DELETE). `audit_logs`: RLS enabled, no policies at
all for `anon`/`authenticated` — service-role-only by default-deny.

**Role-protection mechanism**: `prevent_role_self_escalation()`
(`003_role_protection.sql`), a `BEFORE UPDATE` trigger on `profiles`
that raises an exception if `NEW.role IS DISTINCT FROM OLD.role` and the
executing Postgres role isn't `service_role`. This is in the same
migration set as the RLS policies, not a later addition — per your
"critical requirement" instruction. Verified structurally (present, and
checks the right condition) by `test_static_security.py` check #9; **not
executable** without a live Postgres/Supabase instance (see §6).

## 4. Authentication

- **Email/password**: `backend.auth.sign_up` / `sign_in_with_password`
  via Supabase Auth's own `auth.users` — no custom password table exists
  anywhere in this codebase (the LearnMate pattern rejected in Phase 0).
- **Password reset**: `reset_password_for_email` — deliberately never
  reveals whether an email exists (both a real and nonexistent email
  return the same "if an account exists..." message), avoiding an
  email-enumeration side channel.
- **Session handling**: `st.session_state["sahay_supabase_session"]`
  caches `{access_token, refresh_token}` — a cache of a Supabase-issued
  session, not an invented credential. `get_current_user()` re-validates
  against Supabase's `auth.get_user(token)` on every call rather than
  trusting a locally-set boolean (see `PHASE2_ARCHITECTURE_AUDIT.md` §6).
- **Logout**: calls the real `client.auth.sign_out()` (server-side
  token invalidation) before clearing local state — not just a local
  reset.
- **Auth gate**: centralized once in `streamlit_app.py`'s `main()`
  rather than per-page, per the audit's §4.3 recommendation. A real
  authenticated session always wins over a stale Demo Mode flag
  (`is_demo = st.session_state["sahay_demo_mode"] and current_user is
  None`).
- **Google OAuth**: `get_google_sign_in_url()` builds the redirect URL
  via `client.auth.sign_in_with_oauth(...)`;
  `complete_oauth_from_query_params()` reads `st.query_params["code"]` on
  every page load and exchanges it via
  `client.auth.exchange_code_for_session(...)` if present. **Structure
  implemented, NOT live-tested** — see §7.

## 5. Security

**Anon-key vs. service-role architecture**: `backend/supabase_client.py`
holds the anon-key, RLS-enforced client (used by `backend/auth.py` for
everything user-facing — sign-up, sign-in, profile read/write).
`backend/supabase_admin_client.py` holds the service-role client, used
by exactly one other file: `backend/audit_log.py`. Enforced by
`tests/test_import_guard.py` and `test_static_security.py` check #4,
both passing (0 references to `supabase_admin_client` anywhere in
`pages/`, `components/`, or `chatbot/`).

**Role protection**: see §3. The database, not the Streamlit app, is the
enforcement boundary — even a bug in `backend/auth.py` (which never
attempts to set `role` on update anyway, since `pages/profile.py` only
ever writes `display_name`/`preferred_language`) cannot promote a user,
because Postgres itself would reject the write.

**Secrets**: `SUPABASE_SERVICE_ROLE_KEY` is read only via
`config.SUPABASE_ADMIN_CONFIG`, which is read only inside
`backend/supabase_admin_client.py`. It is never passed to any Streamlit
widget, never rendered in HTML/markdown, never logged (confirmed by
reading `backend/audit_log.py` and `backend/logging_config.py` — no log
call anywhere includes a config value). `test_static_security.py` check
#1 confirms no hardcoded secret-looking string exists in the codebase.

**Demo Mode isolation**: confirmed by code inspection — no page module,
including `pages/profile.py`, calls into `backend.auth` unless
`st.session_state["sahay_supabase_session"]` is already present (see
`profile.py`'s guard clause). `components/chatbot_launcher.py` and every
other Phase 1 page were not modified and still only touch
`st.session_state`.

## 6. Testing evidence

Every test below was actually run this session; raw output is shown
inline in the working transcript. Labels follow your requested scheme
exactly.

| Test | Result | Label |
|---|---|---|
| `python3 -m py_compile` on all 49 `.py` files | 0 failures | **PASS — STATIC/STRUCTURAL** |
| `config.py` resolves correctly, `content.*` imports (6 services, 0 crisis resources) | Confirmed by direct import | **PASS — STATIC/STRUCTURAL** |
| `backend.auth`/`supabase_client`/`supabase_admin_client`/`audit_log` import cleanly with **no `supabase` package installed** | Confirmed — `import supabase` itself fails, but importing these modules doesn't, proving the lazy-import design works | **PASS — STATIC/STRUCTURAL** |
| `tests/test_import_guard.py` | 1/1 checks passed | **PASS — STATIC/STRUCTURAL** |
| `tests/test_navigation_consistency.py` | 4/4 checks passed | **PASS — STATIC/STRUCTURAL** |
| `tests/test_static_security.py` | 12/12 checks passed (3 initial false positives found, root-caused to the test scanning its own file, and fixed — see below) | **PASS — STATIC/STRUCTURAL** |
| `tests/test_auth_mock.py` (sign-up, duplicate-email rejection, sign-in success/failure, profile bootstrap, session validation, sign-out, OAuth URL construction, error-message leak check) | 12/12 checks passed against a hand-written fake Supabase client | **PASS — MOCK** |
| Full `streamlit_app.py` execution: landing (unconfigured default), Demo Mode entry, all 14 pages in Demo Mode | 16/16 ran clean via the Streamlit stub built in the Phase 1 validation round (extended this round with `cache_resource`, `tabs`, `form`, `link_button`, `query_params`) | **PASS — STATIC/STRUCTURAL** (stub-based, not a real Streamlit process) |
| Phase 1 regression: sidebar collapse, nav click, Exit Demo Mode, suggestion chip, launcher toggle — all in Demo Mode under the new auth-gated `main()` | 5/5 passed, each checked against the actual resulting session-state value, not just "no exception" | **PASS — STATIC/STRUCTURAL** |
| User A cannot read User B's profile (RLS) | Not run | **NOT TESTED** — requires a live Postgres/Supabase instance |
| User A cannot update User B's profile (RLS) | Not run | **NOT TESTED** — same |
| Role self-escalation actually blocked at the DB layer | Trigger's SQL logic reviewed and its presence/condition verified by static scan; **the trigger itself was never executed** | **NOT TESTED** (SQL-level) — logic reviewed, not run |
| Admin performing an approved operation | No admin UI exists yet (correctly out of Phase 2 scope) | **NOT TESTED** — not applicable this phase |
| `audit_logs` genuinely inaccessible via the anon/user client | RLS policy text confirmed to contain zero `CREATE POLICY` statements for it | **PASS — STATIC/STRUCTURAL** (SQL text review) — **NOT TESTED** as a live query |
| Registration / login / logout / password reset against a real Supabase project | Not run — no network access, no live project | **NOT TESTED** |
| Google OAuth end-to-end (real Google Cloud client + browser redirect) | Not run | **NOT TESTED** — see §7 |
| Session expiry against a real Supabase JWT | Not run | **NOT TESTED** |

**On the 3 initial test false-positives**: `test_static_security.py`'s
SQLite/LearnMate-import/uploads-path scans initially flagged the test
file itself, because it legitimately contains those strings in its own
comments and regex patterns. Fixed by scoping those three checks to
`APP_FILES` (excludes `tests/`) and tightening the LearnMate-import
regex to require actual `from X import`/`import X` syntax rather than
matching prose like "adapted from LearnMate AI's...". Re-run confirmed
12/12 passing after the fix — documented here rather than silently
corrected, per your instruction to document any fix made during
verification.

## 7. Known limitations

- **Supabase live testing**: not performed. No network access in this
  environment (confirmed by the Phase 1 validation round's failed `pip
  install streamlit`/`pip install supabase` attempts — same constraint
  applies here). Everything Supabase-related is either static/structural
  review or mock-client verification.
- **Google OAuth live testing**: not performed, and cannot be — it
  requires an actual Google Cloud OAuth client, a real Supabase project
  with the Google provider configured, and a live browser redirect.
  Status: **"Configured but not live-tested."** The
  `get_google_sign_in_url()`/`complete_oauth_from_query_params()` pair
  implements the standard Supabase-recommended pattern for a framework
  (Streamlit) with no native OAuth-callback handling, but I have not
  watched it work end-to-end.
- **Streamlit Cloud testing**: not performed — no deployment happened
  this phase.
- **RLS and the role-protection trigger**: reviewed for correctness
  (structurally, by reading the SQL), never executed against a real
  Postgres engine. This is the single most important thing for you to
  verify yourself once you apply the migrations — recommend running the
  exact test queries from `PHASE2_ARCHITECTURE_AUDIT.md` §13 (`set role
  authenticated; set request.jwt.claim.sub = '<user-a-id>';`) in
  Supabase's SQL editor before considering Phase 2 truly done.
- **`supabase` Python package**: not installed in this environment (no
  network). Every module that imports it does so lazily, inside a
  function, specifically so the rest of the codebase (config, content,
  page rendering) stays testable without it — but this also means the
  actual `create_client(...)` call itself has never executed, mocked or
  otherwise, only the code paths around it.

## 8. Phase 1 regression

Checked and confirmed passing (§6, "Phase 1 regression" row): sidebar
collapse/expand, active-page nav click, Exit Demo Mode, suggestion
chips, chatbot launcher open/close — all exercised against real
session-state assertions (not just "no crash") under the new
auth-gated `streamlit_app.py`. Landing page, Sahay AI branding, and the
heart + speech-bubble icon are unchanged files (`components/theme.py`,
`assets/sahay_icon.svg` untouched) — confirmed by the file-modification
list in §2. All 14 placeholder pages still render cleanly (§6).

## 9. Phase 3 readiness

**Not yet fully ready — one manual step required from you first.**
The code is complete and internally consistent (static/mock verification
all green), but Phase 3 (AI engine) will need real conversation storage
eventually, which depends on `profiles`/RLS actually working against a
live database — something only you can verify by:

1. Creating the Supabase project and applying the 3 migrations (§10).
2. Running the RLS cross-user test queries from
   `PHASE2_ARCHITECTURE_AUDIT.md` §13.
3. Confirming email/password sign-up → login → logout works in a real
   browser.
4. Optionally configuring and testing Google OAuth (can be deferred —
   email/password alone is sufficient to unblock Phase 3's actual
   scope, which is the AI engine, not auth).

Once you've done that and confirmed no surprises, Phase 3 can proceed
against a real `profiles` table with confidence that the security
foundation under it is sound — not just "looks right in the SQL file."

## 10. Manual Supabase setup

**Supabase project**
1. Create a project at supabase.com. Note the Project URL and, from
   Settings → API, the `anon`/`public` key and the `service_role` key.

**Migrations**
2. Open the SQL Editor in your Supabase project and run, in order:
   `database/migrations/001_initial_schema.sql`,
   `002_rls_policies.sql`, `003_role_protection.sql`.

**Authentication providers**
3. Authentication → Providers → Email: ensure it's enabled (on by
   default).
4. Authentication → Providers → Google: toggle on, and enter the
   Client ID / Client Secret from a Google Cloud OAuth client you create
   (see step 6 below) — the secret is entered here, in the Supabase
   dashboard, never in this codebase.

**Site URL / redirect URLs**
5. Authentication → URL Configuration → Site URL: set to your deployed
   app's URL (e.g. `http://localhost:8501` for local dev, or your
   Streamlit Cloud URL in production — these differ, so you'll update
   this when you deploy).
6. Google Cloud Console → APIs & Services → Credentials → create an
   OAuth 2.0 Client ID (Web application). Authorized redirect URI:
   `https://<your-project-ref>.supabase.co/auth/v1/callback`.

**Secrets**
7. Fill in `.streamlit/secrets.toml` (copy from
   `.streamlit/secrets.toml.example`) locally:
   ```
   SUPABASE_URL = "https://<your-project-ref>.supabase.co"
   SUPABASE_ANON_KEY = "<your anon/public key>"
   SUPABASE_SERVICE_ROLE_KEY = "<your service_role key>"
   GOOGLE_OAUTH_CLIENT_ID = "<your Google OAuth client ID>"
   GOOGLE_OAUTH_REDIRECT_URL = "http://localhost:8501"
   ```
8. For Streamlit Community Cloud: paste the same key/value pairs into
   your app's Settings → Secrets, with `GOOGLE_OAUTH_REDIRECT_URL` set to
   your deployed app's actual URL instead of `localhost`.

**RLS**
9. Already applied by migration `002_rls_policies.sql` — no manual
   dashboard step needed, but worth opening Table Editor →
   `profiles`/`audit_logs` → confirm the RLS toggle shows "Enabled" for
   both.

I have not filled in any of the above with a real project's values — every
placeholder above is exactly that, a placeholder, per your instruction
not to invent values dependent on your actual project.
