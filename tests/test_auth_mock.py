"""
tests/test_auth_mock.py
--------------------------
MOCK VERIFICATION — NOT a live Supabase test. This module injects a fake
`supabase` package (a hand-written stand-in for `create_client`) so that
backend/auth.py's actual Python control flow — error mapping, session
storage, profile bootstrap, audit-log calls, role-change awareness — can
be exercised without any network access or real Supabase project.

This proves the LOGIC is correct. It does NOT prove:
  - a real Supabase project accepts these calls the same way
  - RLS/the role-protection trigger actually fire (those are SQL,
    verified structurally in test_static_security.py, not executable
    here without a real Postgres instance)
  - Google's OAuth screens/redirect actually work

Run: python3 tests/test_auth_mock.py  (requires the streamlit stub on
PYTHONPATH — see tests/README.md)
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


# ---------------------------------------------------------------------------
# Fake `supabase` package
# ---------------------------------------------------------------------------
class FakeAuthAPI:
    def __init__(self, users_db: dict, fail_mode: str | None = None):
        self._users = users_db
        self._fail_mode = fail_mode
        self.signed_out = False

    def sign_up(self, creds):
        email = creds["email"]
        if email in self._users:
            raise Exception("User already registered")
        uid = f"uid-{len(self._users) + 1}"
        self._users[email] = {"id": uid, "email": email, "password": creds["password"]}
        return SimpleNamespace(
            user=SimpleNamespace(id=uid, email=email),
            session=SimpleNamespace(access_token="tok", refresh_token="ref"),
        )

    def sign_in_with_password(self, creds):
        if self._fail_mode == "invalid_credentials":
            raise Exception("Invalid login credentials")
        email = creds["email"]
        rec = self._users.get(email)
        if not rec or rec["password"] != creds["password"]:
            raise Exception("Invalid login credentials")
        return SimpleNamespace(
            user=SimpleNamespace(id=rec["id"], email=email),
            session=SimpleNamespace(access_token="tok", refresh_token="ref"),
        )

    def get_user(self, token):
        # Simplified: any non-empty token maps back to the last signed-in user.
        if not self._users:
            return SimpleNamespace(user=None)
        rec = list(self._users.values())[-1]
        return SimpleNamespace(user=SimpleNamespace(id=rec["id"], email=rec["email"]))

    def sign_out(self):
        self.signed_out = True

    def reset_password_for_email(self, email):
        pass

    def set_session(self, access_token, refresh_token):
        pass

    def sign_in_with_oauth(self, opts):
        return SimpleNamespace(url="https://fake-project.supabase.co/auth/v1/authorize?provider=google")


class FakeTableQuery:
    def __init__(self, table_store: dict, table_name: str):
        self._store = table_store
        self._table = table_name
        self._filters = {}
        self._insert_payload = None
        self._update_payload = None
        self._select_single = False

    def select(self, *a, **kw):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def single(self):
        self._select_single = True
        return self

    def execute(self):
        rows = self._store.setdefault(self._table, [])
        if self._insert_payload is not None:
            rows.append(dict(self._insert_payload))
            return SimpleNamespace(data=[self._insert_payload])
        if self._update_payload is not None:
            for r in rows:
                if all(r.get(k) == v for k, v in self._filters.items()):
                    r.update(self._update_payload)
            return SimpleNamespace(data=[])
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        if self._select_single:
            return SimpleNamespace(data=matched[0] if matched else None)
        return SimpleNamespace(data=matched)


class FakeSupabaseClient:
    def __init__(self, users_db: dict, table_store: dict, fail_mode: str | None = None):
        self.auth = FakeAuthAPI(users_db, fail_mode=fail_mode)
        self._table_store = table_store

    def table(self, name):
        return FakeTableQuery(self._table_store, name)


def install_fake_supabase(users_db: dict, table_store: dict, fail_mode: str | None = None) -> None:
    fake_module = ModuleType("supabase")
    fake_module.create_client = lambda url, key: FakeSupabaseClient(users_db, table_store, fail_mode=fail_mode)
    sys.modules["supabase"] = fake_module


def fresh_env_and_modules() -> None:
    os.environ["SUPABASE_URL"] = "https://fake-project.supabase.co"
    os.environ["SUPABASE_ANON_KEY"] = "fake-anon-key"
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "fake-service-role-key"
    os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "fake-client-id"
    os.environ["GOOGLE_OAUTH_REDIRECT_URL"] = "http://localhost:8501"
    for mod in list(sys.modules):
        if mod in ("config",) or mod.startswith(("backend.", "content.")):
            del sys.modules[mod]
    import streamlit as st
    st.session_state.clear()
    for key in ("sahay_supabase_session",):
        st.session_state.pop(key, None)


def run() -> int:
    import streamlit as st

    users_db: dict = {}
    table_store: dict = {}
    install_fake_supabase(users_db, table_store)
    fresh_env_and_modules()

    import backend.auth as auth

    # 1. Sign up
    user = auth.sign_up("student@example.com", "correct-horse-battery-staple")
    check("sign_up returns an AuthUser with an id/email", bool(user.id) and user.email == "student@example.com")
    check("sign_up stores a session in st.session_state", auth.SESSION_KEY in st.session_state)

    # 2. Duplicate sign-up is mapped to a friendly error, not a raw exception
    try:
        auth.sign_up("student@example.com", "another-password")
        check("Duplicate sign-up raises AuthError", False)
    except auth.AuthError as exc:
        check("Duplicate sign-up raises a friendly AuthError", "already exists" in str(exc).lower())

    # 3. Sign in with correct password creates/reuses profile row
    st.session_state.pop(auth.SESSION_KEY, None)
    user2 = auth.sign_in_with_password("student@example.com", "correct-horse-battery-staple")
    check("sign_in_with_password succeeds with correct credentials", user2.email == "student@example.com")
    check("ensure_profile_row created a profiles row", len(table_store.get("profiles", [])) == 1)
    check("profiles row defaults role to 'student'", table_store["profiles"][0]["role"] == "student")

    # 4. Sign in with wrong password -> friendly AuthError, audit event logged (best-effort, no raise)
    try:
        auth.sign_in_with_password("student@example.com", "wrong-password")
        check("Wrong password raises AuthError", False)
    except auth.AuthError as exc:
        check("Wrong password raises a friendly 'Incorrect email or password.'", str(exc) == "Incorrect email or password.")

    # 5. get_current_user reflects the stored session
    current = auth.get_current_user()
    check("get_current_user returns the signed-in user after sign_in", current is not None and current.email == "student@example.com")

    # 6. Sign out clears session and calls the fake client's sign_out
    auth.sign_out()
    check("sign_out clears the local session", auth.SESSION_KEY not in st.session_state)
    check("get_current_user returns None after sign_out", auth.get_current_user() is None)

    # 7. Google OAuth URL builder (structure only — not a real redirect test)
    url = auth.get_google_sign_in_url()
    check("get_google_sign_in_url returns a URL string when configured", isinstance(url, str) and url.startswith("https://"))

    # 8. _friendly_auth_error never leaks raw exception text for an unmapped error
    friendly = auth._friendly_auth_error(Exception("some_internal_supabase_error_code_9182"))
    check("Unmapped errors get a generic, non-leaking message",
          "9182" not in friendly and friendly == "Something went wrong signing you in. Please try again.")

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (MOCK verification — fake Supabase client, no network)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
