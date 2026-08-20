"""
config.py
---------
Centralized, secure configuration loader for Sahay AI.

Pattern adapted from the LearnMate AI reference project (env var / Streamlit
secrets loader with per-service frozen dataclasses and an `.is_configured`
property) — see /PHASE0_AUDIT.md section B for the audit that identified
this as a reusable pattern.

PHASE 1 NOTE: No Supabase or OpenRouter calls are made anywhere in this
codebase yet. This module only defines the *shape* configuration will take
in Phase 2/3 so later phases don't need to redesign config loading. Running
the app today with no `.env` / secrets present is expected and supported —
every `.is_configured` check below will simply read False.

SECURITY NOTE (do not change without re-reading PHASE0_AUDIT.md §C):
SupabaseConfig is split into an anon-key config (safe for RLS-enforced,
user-scoped access — used by backend/supabase_client.py in Phase 2) and a
service-role config (admin-only, must never be imported from anything under
pages/ or components/). This is a deliberate correction of the LearnMate
reference, which used the service-role key for all user-facing reads/writes
and bypassed Row Level Security by design.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_ENV_PATH, override=False)
except ImportError:
    # python-dotenv is a Phase 1 requirement (see requirements.txt), but the
    # loader degrades gracefully rather than crashing the app if it's
    # somehow missing from the environment.
    pass


def _get_env(key: str, default: str | None = None) -> str:
    """Fetch an environment variable, falling back to Streamlit secrets."""
    value = os.getenv(key, default)
    if not value:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and key in st.secrets:
                value = str(st.secrets[key])
        except Exception:
            pass
    return value or ""


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    companion_name: str
    app_env: str

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@dataclass(frozen=True)
class SupabaseUserConfig:
    """Anon-key config — RLS-enforced, used for all user-owned data.

    NOT configured or used in Phase 1. Defined here so Phase 2 doesn't
    require touching this file's shape.
    """
    url: str
    anon_key: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.anon_key)


@dataclass(frozen=True)
class SupabaseAdminConfig:
    """Service-role config — admin-only, aggregate queries only.

    Must only ever be imported by backend/supabase_admin_client.py.
    Never configured or used in Phase 1.
    """
    url: str
    service_role_key: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.service_role_key)


@dataclass(frozen=True)
class OpenRouterConfig:
    """Not configured or used in Phase 1/2 — implemented in Phase 3."""
    api_key: str
    base_url: str
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


@dataclass(frozen=True)
class GoogleOAuthConfig:
    """Not configured or used in Phase 1 — placeholder for Phase 2."""
    client_id: str
    redirect_url: str

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.redirect_url)


def load_app_config() -> AppConfig:
    return AppConfig(
        app_name=_get_env("APP_NAME", default="Sahay AI"),
        companion_name=_get_env("COMPANION_NAME", default="Sahay"),
        app_env=_get_env("APP_ENV", default="development"),
    )


def load_supabase_user_config() -> SupabaseUserConfig:
    return SupabaseUserConfig(
        url=_get_env("SUPABASE_URL"),
        anon_key=_get_env("SUPABASE_ANON_KEY"),
    )


def load_supabase_admin_config() -> SupabaseAdminConfig:
    return SupabaseAdminConfig(
        url=_get_env("SUPABASE_URL"),
        service_role_key=_get_env("SUPABASE_SERVICE_ROLE_KEY"),
    )


def load_openrouter_config() -> OpenRouterConfig:
    return OpenRouterConfig(
        api_key=_get_env("OPENROUTER_API_KEY"),
        base_url=_get_env("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1"),
        model=_get_env("OPENROUTER_MODEL", default="openai/gpt-4o-mini"),
    )


def load_google_oauth_config() -> GoogleOAuthConfig:
    return GoogleOAuthConfig(
        client_id=_get_env("GOOGLE_OAUTH_CLIENT_ID"),
        redirect_url=_get_env("GOOGLE_OAUTH_REDIRECT_URL"),
    )


APP_CONFIG = load_app_config()
SUPABASE_USER_CONFIG = load_supabase_user_config()
SUPABASE_ADMIN_CONFIG = load_supabase_admin_config()
OPENROUTER_CONFIG = load_openrouter_config()
GOOGLE_OAUTH_CONFIG = load_google_oauth_config()
