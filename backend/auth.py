"""
backend/auth.py
------------------
PHASE 2 IMPLEMENTATION.

Wraps Supabase Auth (email/password + Google OAuth + password reset)
behind a small, friendly-error API that streamlit_app.py and
components/landing.py call. Deliberately does NOT reuse LearnMate's
email-lookup "auth" pattern (no custom password table, no email-only
"login") — see PHASE0_AUDIT.md §C.

SESSION MODEL (see PHASE2_ARCHITECTURE_AUDIT.md §6):
st.session_state caches a Supabase-issued session (access_token +
refresh_token); it does NOT invent its own credential. Every page load
that needs to know "is this a real, still-valid session" re-validates
via get_current_user(), which asks the Supabase client for the current
user rather than trusting a locally-set boolean flag.

GOOGLE OAUTH — IMPORTANT HONESTY NOTE:
Streamlit has no native way to receive an OAuth redirect callback inside
a normal page the way a typical web framework does; the standard pattern
is: generate the provider's sign-in URL via `sign_in_with_oauth`, send
the user to it in their browser, and on return read the auth code
Supabase appends to the redirect URL via `st.query_params`, then exchange
it with `exchange_code_for_session` (supabase-py >= 2.4). This module
implements that structure. It has NOT been exercised against a live
Google Cloud OAuth client or a live Supabase project in this environment
(no network access) — see PHASE2_IMPLEMENTATION_REPORT.md for exactly
what is and isn't verified.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from backend.audit_log import (
    log_event, EVENT_SIGNUP, EVENT_LOGIN, EVENT_LOGIN_FAILED, EVENT_LOGOUT,
    EVENT_PASSWORD_RESET_REQUESTED, EVENT_PROFILE_CREATED,
)
from backend.logging_config import get_logger
from backend.supabase_client import get_user_client, SupabaseNotConfiguredError
from config import GOOGLE_OAUTH_CONFIG, SUPABASE_USER_CONFIG

logger = get_logger(__name__)

SESSION_KEY = "sahay_supabase_session"  # {"access_token", "refresh_token"}


class AuthError(RuntimeError):
    """A friendly, user-facing auth error. Message is safe to show as-is
    (never contains a raw exception, stack trace, or token)."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _client():
    session = st.session_state.get(SESSION_KEY)
    if session:
        return get_user_client(session["access_token"], session["refresh_token"])
    return get_user_client()


def _store_session(auth_response) -> None:
    session = getattr(auth_response, "session", None)
    if session is None:
        return
    st.session_state[SESSION_KEY] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }


def get_current_user() -> AuthUser | None:
    """The single source of truth for "is someone really signed in."
    Re-validates against the Supabase client rather than trusting a
    locally-set boolean — see the module docstring's SESSION MODEL note.
    Returns None (not an exception) when there is no valid session, so
    callers can use it directly in an `if` check."""
    session = st.session_state.get(SESSION_KEY)
    if not session:
        return None
    try:
        client = _client()
        resp = client.auth.get_user(session["access_token"])
        user = getattr(resp, "user", None)
        if user is None:
            return None
        return AuthUser(id=user.id, email=user.email)
    except SupabaseNotConfiguredError:
        raise
    except Exception:  # noqa: BLE001 - any auth-check failure means "not signed in"
        logger.exception("get_current_user: session validation failed")
        return None


def ensure_profile_row(user: AuthUser) -> None:
    """Create a minimal profiles row on first login if one doesn't exist
    yet. Uses the user's OWN anon-key session (not the admin client) —
    the INSERT is covered by the profiles_insert_own RLS policy
    (auth.uid() = id), so this works entirely within RLS."""
    client = _client()
    existing = client.table("profiles").select("id").eq("id", user.id).execute()
    if existing.data:
        return
    client.table("profiles").insert({
        "id": user.id,
        "role": "student",
        "onboarding_complete": False,
    }).execute()
    log_event(actor_type="system", action=EVENT_PROFILE_CREATED, actor_id=user.id)


def get_profile(user: AuthUser) -> dict | None:
    client = _client()
    resp = client.table("profiles").select("*").eq("id", user.id).single().execute()
    return resp.data


def get_client_for_current_user():
    """Public accessor for the current session's RLS-scoped client, for
    pages that need to read/write their own profile data beyond what
    get_profile()/ensure_profile_row() already cover (e.g. profile
    edits). Returns the same client _client() would build internally —
    exposed publicly so callers don't need to reach into a private
    function."""
    return _client()


# ---------------------------------------------------------------------------
# Email / password
# ---------------------------------------------------------------------------

def sign_up(email: str, password: str) -> AuthUser:
    try:
        client = _client()
        resp = client.auth.sign_up({"email": email, "password": password})
    except SupabaseNotConfiguredError:
        raise
    except Exception as exc:
        raise AuthError(_friendly_auth_error(exc)) from exc

    if resp.user is None:
        raise AuthError("Could not create an account with those details. Please try again.")

    _store_session(resp)
    user = AuthUser(id=resp.user.id, email=resp.user.email)
    log_event(actor_type="user", action=EVENT_SIGNUP, actor_id=user.id)
    return user


def sign_in_with_password(email: str, password: str) -> AuthUser:
    try:
        client = _client()
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
    except SupabaseNotConfiguredError:
        raise
    except Exception as exc:
        log_event(actor_type="user", action=EVENT_LOGIN_FAILED, target=_mask_email(email))
        raise AuthError(_friendly_auth_error(exc)) from exc

    if resp.user is None:
        log_event(actor_type="user", action=EVENT_LOGIN_FAILED, target=_mask_email(email))
        raise AuthError("Incorrect email or password.")

    _store_session(resp)
    user = AuthUser(id=resp.user.id, email=resp.user.email)
    ensure_profile_row(user)
    log_event(actor_type="user", action=EVENT_LOGIN, actor_id=user.id)
    return user


def reset_password_for_email(email: str) -> None:
    """Sends a password-reset email via Supabase. Always returns silently
    (Supabase itself decides whether the email exists — this function
    never reveals that to the caller, avoiding an email-enumeration
    side-channel)."""
    try:
        client = _client()
        client.auth.reset_password_for_email(email)
    except SupabaseNotConfiguredError:
        raise
    except Exception:
        logger.exception("reset_password_for_email failed")
        # Deliberately no re-raise with detail — see docstring.
    log_event(actor_type="user", action=EVENT_PASSWORD_RESET_REQUESTED, target=_mask_email(email))


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

def get_google_sign_in_url() -> str:
    """Builds the Supabase-hosted Google OAuth URL to redirect the user to.

    NOT LIVE-TESTED — see module docstring and PHASE2_IMPLEMENTATION_REPORT.md.
    Requires GOOGLE_OAUTH_CONFIG.is_configured (client ID + redirect URL)
    and SUPABASE_USER_CONFIG.is_configured; raises AuthError with a clear
    message if either is missing, rather than silently failing.
    """
    if not SUPABASE_USER_CONFIG.is_configured:
        raise AuthError("Google Sign-In isn't configured yet — Supabase connection is missing.")
    if not GOOGLE_OAUTH_CONFIG.is_configured:
        raise AuthError("Google Sign-In isn't configured yet — Google OAuth settings are missing.")

    client = _client()
    resp = client.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": GOOGLE_OAUTH_CONFIG.redirect_url},
    })
    return resp.url


def complete_oauth_from_query_params() -> AuthUser | None:
    """Call once near the top of the app on every load. If the URL query
    params contain an OAuth callback code (i.e. the user was just
    redirected back from Google via Supabase), exchanges it for a session.
    Returns None (no-op) on any normal page load with no callback present.

    NOT LIVE-TESTED — see module docstring.
    """
    params = st.query_params
    code = params.get("code")
    if not code:
        return None

    try:
        client = _client()
        resp = client.auth.exchange_code_for_session({"auth_code": code})
    except SupabaseNotConfiguredError:
        raise
    except Exception as exc:
        logger.exception("OAuth callback exchange failed")
        raise AuthError("Google Sign-In didn't complete. Please try again.") from exc

    if resp.user is None:
        raise AuthError("Google Sign-In didn't complete. Please try again.")

    _store_session(resp)
    user = AuthUser(id=resp.user.id, email=resp.user.email)
    ensure_profile_row(user)
    log_event(actor_type="user", action=EVENT_LOGIN, actor_id=user.id, target="google_oauth")
    st.query_params.clear()
    return user


# ---------------------------------------------------------------------------
# Sign out
# ---------------------------------------------------------------------------

def sign_out() -> None:
    """Real sign-out: invalidates the refresh token server-side via
    Supabase, THEN clears local session state. Order matters — clearing
    local state first and letting the server call fail silently would
    leave a still-valid token the app just forgot about."""
    user = get_current_user()
    try:
        client = _client()
        client.auth.sign_out()
    except Exception:
        logger.exception("sign_out: Supabase sign_out call failed (clearing local session anyway)")
    finally:
        st.session_state.pop(SESSION_KEY, None)
    if user:
        log_event(actor_type="user", action=EVENT_LOGOUT, actor_id=user.id)


# ---------------------------------------------------------------------------
# Error message mapping — never leak raw exception text to the user
# ---------------------------------------------------------------------------

def _friendly_auth_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "already registered" in text or "already exists" in text or "duplicate" in text:
        return "An account with that email already exists. Try logging in instead."
    if "invalid login credentials" in text or "invalid email or password" in text:
        return "Incorrect email or password."
    if "password" in text and ("short" in text or "weak" in text or "least" in text):
        return "That password doesn't meet the minimum requirements. Please choose a longer password."
    if "rate limit" in text or "too many" in text:
        return "Too many attempts. Please wait a moment and try again."
    if "network" in text or "timeout" in text or "connection" in text:
        return "Couldn't reach the authentication service. Please check your connection and try again."
    logger.warning("Unmapped auth error (showing generic message to user): %r", exc)
    return "Something went wrong signing you in. Please try again."


def _mask_email(email: str) -> str:
    """For audit_log `target` only — never store a full email verbatim in
    a security log we intend to keep readable without becoming a second
    copy of user PII."""
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    masked_local = (local[0] + "***") if local else "***"
    return f"{masked_local}@{domain}"
