"""
backend/audit_log.py
----------------------
PHASE 2 IMPLEMENTATION.

The ONLY writer of the audit_logs table, and the ONLY other module in
this codebase (besides backend/supabase_admin_client.py itself) that
imports the service-role client. Every call site elsewhere in the app
should call log_event(...) from here, never touch
backend.supabase_admin_client directly.

Logs identifiers and event names only — see SENSITIVE constraints below.
Never pass message content, passwords, tokens, or full request/response
bodies into `action` or `target`.
"""

from __future__ import annotations

from backend.logging_config import get_logger
from backend.supabase_admin_client import get_admin_client, SupabaseAdminNotConfiguredError

logger = get_logger(__name__)

# Recognized event names — keeps `action` values consistent and greppable.
# Not database-enforced (audit_logs.action is a plain text column), but
# centralizing the list here catches typos in review.
EVENT_SIGNUP = "signup"
EVENT_LOGIN = "login"
EVENT_LOGIN_FAILED = "login_failed"
EVENT_LOGOUT = "logout"
EVENT_PASSWORD_RESET_REQUESTED = "password_reset_requested"
EVENT_ROLE_CHANGE_DENIED = "role_change_denied"
EVENT_ACCOUNT_DELETION_REQUESTED = "account_deletion_requested"
EVENT_PROFILE_CREATED = "profile_created"


def log_event(
    actor_type: str,
    action: str,
    actor_id: str | None = None,
    target: str | None = None,
) -> None:
    """Best-effort audit write. NEVER raises into the caller — a logging
    failure must not block a login/signup/logout for the user. Failures
    are logged locally (via the app's own logger, not re-raised) so an
    operator can notice a broken audit pipeline without users being
    affected by it.

    SENSITIVE DATA RULE: `action` must be one of the EVENT_* constants
    above (or an equally short, non-content identifier); `target` must be
    a short reference (e.g. a table name or a truncated id), never raw
    user input, message content, tokens, or credentials.
    """
    if actor_type not in ("user", "admin", "system"):
        raise ValueError("actor_type must be 'user', 'admin', or 'system'")

    try:
        client = get_admin_client()
        client.table("audit_logs").insert({
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action": action,
            "target": target,
        }).execute()
    except SupabaseAdminNotConfiguredError:
        # Expected in any environment without SUPABASE_SERVICE_ROLE_KEY set
        # (e.g. local dev before Supabase is configured). Not an error the
        # user should ever see.
        logger.info("Audit log skipped (service-role client not configured): %s", action)
    except Exception:  # noqa: BLE001 - audit logging must never break the caller
        logger.exception("Failed to write audit log event: %s", action)
