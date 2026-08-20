"""
backend/supabase_client.py
----------------------------
PHASE 2 IMPLEMENTATION.

The ANON-KEY, RLS-enforced Supabase client used for all user-owned data.
Per the approved architecture (PHASE0_AUDIT.md §C, PHASE2_ARCHITECTURE_AUDIT.md §8),
this module must NEVER use the service-role key — that key belongs only
in backend/supabase_admin_client.py, imported only by admin-only code
paths (currently: backend/audit_log.py).

This client authenticates as whatever user is currently signed in (via
`set_session`), so every query it makes is subject to the RLS policies
in database/migrations/002_rls_policies.sql — there is no way for code
using this client to read another user's `profiles` row, even if the
calling Python code has a bug.
"""

from __future__ import annotations

import streamlit as st

from config import SUPABASE_USER_CONFIG


class SupabaseNotConfiguredError(RuntimeError):
    """Raised when SUPABASE_URL / SUPABASE_ANON_KEY are missing."""


@st.cache_resource(show_spinner=False)
def _base_client():
    """A single cached anon-key client, shared across reruns within one
    Streamlit process. This is the *unauthenticated* base client — each
    caller must attach the current user's session (see get_user_client)
    before making a request that relies on RLS treating them as
    `authenticated` rather than `anon`."""
    if not SUPABASE_USER_CONFIG.is_configured:
        raise SupabaseNotConfiguredError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set (via .env, "
            ".streamlit/secrets.toml, or Streamlit Cloud secrets) before "
            "any Supabase-backed feature can be used."
        )
    from supabase import create_client
    return create_client(SUPABASE_USER_CONFIG.url, SUPABASE_USER_CONFIG.anon_key)


def get_user_client(access_token: str | None = None, refresh_token: str | None = None):
    """Return the anon-key client, with the current user's session attached
    if tokens are provided. Called by backend/auth.py after a successful
    sign-in, and by any future page needing to read/write the current
    user's own data.

    Without a session attached, requests execute as Postgres role `anon`,
    which has NO policies granted on `profiles` or `audit_logs` at all
    (see 002_rls_policies.sql) — so an unauthenticated caller using this
    function gets empty results / permission errors, never another
    user's data.
    """
    client = _base_client()
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client
