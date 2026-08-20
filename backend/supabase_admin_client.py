"""
backend/supabase_admin_client.py
-----------------------------------
PHASE 2 IMPLEMENTATION.

The SERVICE-ROLE Supabase client. Bypasses RLS by Postgres/Supabase
design — reserved strictly for the genuinely privileged operations
identified in PHASE2_ARCHITECTURE_AUDIT.md:

  - writing to audit_logs (the only table with zero anon/authenticated
    RLS policies — this is the sole intended writer)

ARCHITECTURAL RULE (enforced by import-guard test, see
tests/test_no_admin_client_leakage.py):
  - This module must NEVER be imported from pages/, components/, or
    chatbot/. Only backend/audit_log.py imports it in this codebase.
  - Must never be used to read/write a specific user's private data.
  - The service-role key must never reach the browser — Streamlit only
    executes this module's code server-side, and the key itself lives
    only in .streamlit/secrets.toml / Streamlit Cloud secrets / .env,
    never in any file that ships to the client.
"""

from __future__ import annotations

import streamlit as st

from config import SUPABASE_ADMIN_CONFIG


class SupabaseAdminNotConfiguredError(RuntimeError):
    """Raised when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are missing."""


@st.cache_resource(show_spinner=False)
def get_admin_client():
    if not SUPABASE_ADMIN_CONFIG.is_configured:
        raise SupabaseAdminNotConfiguredError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set before "
            "any admin-only operation (e.g. audit logging) can run."
        )
    from supabase import create_client
    return create_client(SUPABASE_ADMIN_CONFIG.url, SUPABASE_ADMIN_CONFIG.service_role_key)
