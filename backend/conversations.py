"""
backend/conversations.py
---------------------------
PHASE 4 IMPLEMENTATION.

CRUD for conversations/messages/mood_events/wellness_activity_logs.
Every function here takes an AuthUser and uses
backend.auth.get_client_for_current_user() — the anon-key, RLS-scoped
client — never the service-role client. There is no code path in this
module that can read or write another user's data: RLS enforces
`auth.uid() = user_id` at the database layer regardless of what `user_id`
a caller passes in, so even a bug here (e.g. accidentally passing the
wrong user_id) cannot leak across accounts — Postgres would simply
return zero rows or reject the write.

Message content, mood notes, and everything else in this module flows
through Supabase exactly as typed — no system prompt, no chain-of-thought,
no API key is ever passed to any function here (chatbot/response_generator.py
never returns any of those to its callers in the first place).
"""

from __future__ import annotations

from backend.auth import AuthUser, get_client_for_current_user
from backend.logging_config import get_logger

logger = get_logger(__name__)

VALID_MESSAGE_ROLES = {"user", "assistant"}
VALID_MOOD_SOURCES = {"chat", "checkin"}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def list_conversations(user: AuthUser) -> list[dict]:
    client = get_client_for_current_user()
    resp = (
        client.table("conversations")
        .select("*")
        .eq("user_id", user.id)
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


def create_conversation(user: AuthUser, title: str = "New conversation") -> dict:
    client = get_client_for_current_user()
    resp = client.table("conversations").insert({"user_id": user.id, "title": title}).execute()
    return resp.data[0]


def get_conversation(user: AuthUser, conversation_id: str) -> dict | None:
    client = get_client_for_current_user()
    resp = (
        client.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user.id)  # belt-and-suspenders on top of RLS, not a substitute for it
        .execute()
    )
    return resp.data[0] if resp.data else None


def rename_conversation(user: AuthUser, conversation_id: str, title: str) -> None:
    client = get_client_for_current_user()
    client.table("conversations").update({"title": title}).eq("id", conversation_id).eq("user_id", user.id).execute()


def delete_conversation(user: AuthUser, conversation_id: str) -> None:
    """Deletes the conversation; messages cascade via the FK's
    ON DELETE CASCADE (004_conversations.sql / 005_messages.sql)."""
    client = get_client_for_current_user()
    client.table("conversations").delete().eq("id", conversation_id).eq("user_id", user.id).execute()


def delete_all_conversations(user: AuthUser) -> None:
    """Used by the privacy/data-control UI's 'clear all conversation
    history' action. Deletes every conversation this user owns; messages
    cascade automatically."""
    client = get_client_for_current_user()
    client.table("conversations").delete().eq("user_id", user.id).execute()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def list_messages(user: AuthUser, conversation_id: str) -> list[dict]:
    client = get_client_for_current_user()
    resp = (
        client.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user.id)
        .order("created_at")
        .execute()
    )
    return resp.data or []


def add_message(user: AuthUser, conversation_id: str, role: str, content: str) -> dict:
    if role not in VALID_MESSAGE_ROLES:
        raise ValueError(f"Invalid message role: {role!r} (must be 'user' or 'assistant')")
    client = get_client_for_current_user()
    resp = client.table("messages").insert({
        "conversation_id": conversation_id,
        "user_id": user.id,
        "role": role,
        "content": content,
    }).execute()
    # Touch the parent conversation's updated_at so it sorts to the top of
    # the history list — a plain no-op field update is enough to fire the
    # set_updated_at trigger from 001_initial_schema.sql... but that
    # trigger is only attached to conversations (004's own trigger), so an
    # explicit update is needed here since we're not otherwise writing to
    # the conversations row on every message.
    client.table("conversations").update({}).eq("id", conversation_id).eq("user_id", user.id).execute()
    return resp.data[0]


def clear_conversation_messages(user: AuthUser, conversation_id: str) -> None:
    """'Clear current conversation' — deletes all messages but keeps the
    conversation row (and its title) intact, matching common chat-app
    semantics of clearing content without deleting the thread itself."""
    client = get_client_for_current_user()
    client.table("messages").delete().eq("conversation_id", conversation_id).eq("user_id", user.id).execute()


# ---------------------------------------------------------------------------
# Mood events
# ---------------------------------------------------------------------------

def log_mood_event(
    user: AuthUser,
    mood_result: dict,
    source: str,
    conversation_id: str | None = None,
    note: str | None = None,
    stress_level: int | None = None,
    energy_level: int | None = None,
    sleep_quality: int | None = None,
) -> dict:
    """PHASE 5: stress_level/energy_level/sleep_quality are optional
    self-reported 1-5 scales (see 010_wellness_scales.sql). None of these
    are clinical measurements — callers must not infer a diagnosis from
    any combination of them. Validated here (not just by the DB check
    constraint) so a bad value fails fast with a clear error rather than
    a generic Postgres constraint-violation message reaching the UI."""
    if source not in VALID_MOOD_SOURCES:
        raise ValueError(f"Invalid mood source: {source!r}")
    for name, value in (("stress_level", stress_level), ("energy_level", energy_level), ("sleep_quality", sleep_quality)):
        if value is not None and not (1 <= value <= 5):
            raise ValueError(f"{name} must be between 1 and 5, got {value!r}")
    client = get_client_for_current_user()
    resp = client.table("mood_events").insert({
        "user_id": user.id,
        "conversation_id": conversation_id,
        "source": source,
        "mood": mood_result.get("mood"),
        "sentiment": mood_result.get("sentiment"),
        "confidence": mood_result.get("confidence"),
        "risk_level": mood_result.get("risk_level"),
        "note": note,
        "stress_level": stress_level,
        "energy_level": energy_level,
        "sleep_quality": sleep_quality,
    }).execute()
    return resp.data[0]


def list_mood_events(user: AuthUser, limit: int = 100) -> list[dict]:
    client = get_client_for_current_user()
    resp = (
        client.table("mood_events")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def delete_all_mood_events(user: AuthUser) -> None:
    client = get_client_for_current_user()
    client.table("mood_events").delete().eq("user_id", user.id).execute()


def delete_mood_event(user: AuthUser, mood_event_id: str) -> None:
    """PHASE 5: per-record deletion for pages/mood_history.py, alongside
    the existing delete-everything control on pages/privacy.py."""
    client = get_client_for_current_user()
    client.table("mood_events").delete().eq("id", mood_event_id).eq("user_id", user.id).execute()


# ---------------------------------------------------------------------------
# Wellness activity logs
# ---------------------------------------------------------------------------

def log_wellness_activity(user: AuthUser, activity_key: str) -> dict:
    client = get_client_for_current_user()
    resp = client.table("wellness_activity_logs").insert({
        "user_id": user.id,
        "activity_key": activity_key,
    }).execute()
    return resp.data[0]


def list_wellness_activity_logs(user: AuthUser, limit: int = 200) -> list[dict]:
    client = get_client_for_current_user()
    resp = (
        client.table("wellness_activity_logs")
        .select("*")
        .eq("user_id", user.id)
        .order("completed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []
