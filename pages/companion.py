"""
pages/companion.py
---------------------
PHASE 4/5 IMPLEMENTATION.

For an AUTHENTICATED user: real persisted conversation history via
backend/conversations.py — New Conversation, conversation list grouped
by Today/Yesterday/Older, rename, delete, clear-current-conversation,
copy (via st.code's built-in copy icon), a non-clinical mood indicator
per turn, mood events logged to mood_events, and (Phase 5) a dismissible
"Try this now" wellness-suggestion card after the model's reply.

For DEMO MODE (no real session): falls back to exactly the Phase 1/2/3
session-only behavior — no Supabase call of any kind. This module never
imports backend.conversations unless `auth.get_current_user()` returns a
real user, so Demo Mode structurally cannot reach persisted/private data,
per your Phase 4 instruction.

The floating launcher (components/chatbot_launcher.py) remains a
separate, lightweight, session-only quick-chat surface — not wired to
persisted conversations, by design, to keep it simple and available
everywhere without needing a "which conversation is this" decision. This
page is the full, persisted experience.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from components.theme import sahay_icon_html
from components.cards import safety_note
from components.chatbot_launcher import send_message, render_suggestion_chips, render_suggestion_card
from config import OPENROUTER_CONFIG
from backend import auth
from chatbot.mood_analyzer import MOOD_EMOJI

LANGUAGES = ["English", "Hindi", "Hinglish"]


def render() -> None:
    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None

    header_col, lang_col = st.columns([4, 1])
    with header_col:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;'>"
            f"{sahay_icon_html(34)}<h2 style='margin:0;'>Sahay</h2></div>",
            unsafe_allow_html=True,
        )
    with lang_col:
        st.session_state.setdefault("sahay_language", "English")
        chosen = st.selectbox(
            "Language", LANGUAGES,
            index=LANGUAGES.index(st.session_state["sahay_language"]),
            label_visibility="collapsed",
        )
        st.session_state["sahay_language"] = chosen

    st.caption("Your AI wellness companion — calm, supportive, non-judgmental.")
    safety_note(
        "Sahay never diagnoses, prescribes, or claims to be a medical "
        "professional. If you're in crisis, see Human Help in the sidebar."
    )
    if not OPENROUTER_CONFIG.is_configured:
        st.info(
            "Sahay's AI conversation engine isn't connected in this environment yet "
            "(OpenRouter isn't configured) — you'll see a friendly placeholder reply "
            "instead of a generated one until it is."
        )

    if user is not None:
        _render_authenticated(user)
    else:
        _render_demo()


# ---------------------------------------------------------------------------
# Demo Mode — unchanged session-only behavior from Phase 1/2/3
# ---------------------------------------------------------------------------

def _render_demo() -> None:
    st.session_state.setdefault("sahay_fullpage_history", [])

    for turn in st.session_state["sahay_fullpage_history"]:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    render_suggestion_card("sahay_fullpage_history", key_prefix="companion_demo")

    if not st.session_state["sahay_fullpage_history"]:
        st.caption("Try one of these, or type your own message below.")
        render_suggestion_chips("sahay_fullpage_history", key_prefix="companion")

    user_msg = st.chat_input("Message Sahay")
    if user_msg:
        send_message("sahay_fullpage_history", user_msg)
        st.rerun()

    if st.session_state["sahay_fullpage_history"]:
        if st.button("New conversation", key="fullpage_new_convo"):
            st.session_state["sahay_fullpage_history"] = []
            st.rerun()

    st.caption("💡 Sign in to save your conversation history across visits.")


# ---------------------------------------------------------------------------
# Authenticated — real persisted conversations
# ---------------------------------------------------------------------------

def _render_authenticated(user) -> None:
    from backend import conversations as conv_db
    from chatbot.response_generator import generate_response

    try:
        convo_list = conv_db.list_conversations(user)
    except Exception as exc:  # noqa: BLE001
        st.error("Couldn't load your conversation history right now. Please try again.")
        st.caption(f"Technical detail (dev preview only): {exc}")
        return

    history_col, chat_col = st.columns([1, 2.5])

    with history_col:
        _render_history_panel(user, conv_db, convo_list)

    with chat_col:
        _render_active_conversation(user, conv_db, generate_response, convo_list)


def _render_history_panel(user, conv_db, convo_list: list[dict]) -> None:
    st.markdown("##### Recent Conversations")

    if st.button("+ New Conversation", key="companion_new_conversation", use_container_width=True):
        new_convo = conv_db.create_conversation(user)
        st.session_state["sahay_active_conversation_id"] = new_convo["id"]
        st.rerun()

    if not convo_list:
        st.caption("No conversations yet — start one below.")
        return

    groups = _group_by_recency(convo_list)
    for group_label, items in groups:
        if not items:
            continue
        st.caption(group_label)
        for c in items:
            active = st.session_state.get("sahay_active_conversation_id") == c["id"]
            row_col, del_col = st.columns([4, 1])
            with row_col:
                if st.button(
                    c["title"] or "New conversation",
                    key=f"open_convo_{c['id']}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    st.session_state["sahay_active_conversation_id"] = c["id"]
                    st.rerun()
            with del_col:
                if st.button("🗑️", key=f"delete_convo_{c['id']}", help="Delete this conversation"):
                    conv_db.delete_conversation(user, c["id"])
                    if st.session_state.get("sahay_active_conversation_id") == c["id"]:
                        st.session_state.pop("sahay_active_conversation_id", None)
                    st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Clear all history", key="companion_clear_all_history"):
        st.session_state["sahay_confirm_clear_all"] = True
    if st.session_state.get("sahay_confirm_clear_all"):
        st.warning("This deletes every saved conversation. This can't be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, delete all", key="companion_confirm_clear_all"):
                conv_db.delete_all_conversations(user)
                st.session_state.pop("sahay_active_conversation_id", None)
                st.session_state["sahay_confirm_clear_all"] = False
                st.rerun()
        with c2:
            if st.button("Cancel", key="companion_cancel_clear_all"):
                st.session_state["sahay_confirm_clear_all"] = False
                st.rerun()


def _group_by_recency(convo_list: list[dict]) -> list[tuple[str, list[dict]]]:
    today = datetime.now(timezone.utc).date()
    groups = {"Today": [], "Yesterday": [], "Older": []}
    for c in convo_list:
        try:
            updated = datetime.fromisoformat(c["updated_at"].replace("Z", "+00:00")).date()
        except Exception:  # noqa: BLE001
            updated = today
        delta = (today - updated).days
        if delta <= 0:
            groups["Today"].append(c)
        elif delta == 1:
            groups["Yesterday"].append(c)
        else:
            groups["Older"].append(c)
    return [("Today", groups["Today"]), ("Yesterday", groups["Yesterday"]), ("Older", groups["Older"])]


def _render_active_conversation(user, conv_db, generate_response, convo_list: list[dict]) -> None:
    active_id = st.session_state.get("sahay_active_conversation_id")

    if active_id and not any(c["id"] == active_id for c in convo_list):
        active_id = None
        st.session_state.pop("sahay_active_conversation_id", None)

    if not active_id:
        if convo_list:
            active_id = convo_list[0]["id"]
            st.session_state["sahay_active_conversation_id"] = active_id
        else:
            st.info("Start a new conversation to begin chatting with Sahay.")
            render_suggestion_chips_authenticated(user, conv_db, generate_response)
            return

    try:
        messages = conv_db.list_messages(user, active_id)
    except Exception as exc:  # noqa: BLE001
        st.error("Couldn't load this conversation. Please try again.")
        st.caption(f"Technical detail (dev preview only): {exc}")
        return

    for m in messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m["role"] == "assistant":
                with st.expander("Copy", expanded=False):
                    st.code(m["content"], language=None)

    last_mood = st.session_state.get("sahay_last_mood")
    if last_mood:
        emoji = MOOD_EMOJI.get(last_mood.get("mood"), "🙂")
        st.caption(f"{emoji} Approximate mood signal: {last_mood.get('mood', 'Neutral')} (non-clinical, AI-generated)")

    _render_authenticated_suggestion_card(active_id, len(messages))

    if not messages:
        st.caption("Try one of these, or type your own message below.")
        render_suggestion_chips_authenticated(user, conv_db, generate_response)

    user_msg = st.chat_input("Message Sahay")
    if user_msg:
        _send_authenticated_message(user, conv_db, generate_response, active_id, user_msg)
        st.rerun()

    if messages:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Clear this conversation", key="companion_clear_current"):
                conv_db.clear_conversation_messages(user, active_id)
                st.rerun()
        with st.expander("Rename conversation"):
            title_input = st.text_input("Title", value=next((c["title"] for c in convo_list if c["id"] == active_id), ""), key="companion_rename_field")
            if st.button("Save title", key="companion_save_title"):
                conv_db.rename_conversation(user, active_id, title_input.strip() or "New conversation")
                st.rerun()


def _render_authenticated_suggestion_card(active_id: str, message_count: int) -> None:
    """PHASE 5: mirrors components.chatbot_launcher.render_suggestion_card,
    but for the authenticated/persisted path — there, the suggestion isn't
    stored on a message row (no schema change for an ephemeral UI hint;
    see chatbot/response_generator.py's docstring), it's kept in
    session_state alongside sahay_last_mood, tagged with the conversation
    it belongs to so switching conversations doesn't show a stale card."""
    if st.session_state.get("sahay_last_suggestion_convo_id") != active_id:
        return
    suggestion = st.session_state.get("sahay_last_suggestion")
    if not suggestion:
        return

    dismissed_key = "companion_auth_dismissed_suggestions"
    st.session_state.setdefault(dismissed_key, set())
    dismiss_token = (active_id, message_count)
    if dismiss_token in st.session_state[dismissed_key]:
        return

    from chatbot.mood_analyzer import MOOD_EMOJI
    mood = st.session_state.get("sahay_last_mood") or {}
    emoji = MOOD_EMOJI.get(mood.get("mood"), "💡")

    with st.container(border=True):
        st.markdown(f"{emoji} **Try this now**")
        st.write(suggestion["text"])
        c1, c2 = st.columns([1, 1])
        with c1:
            if suggestion.get("activity_key") and st.button("Open Relaxation", key="companion_auth_suggestion_open", use_container_width=True):
                st.session_state["sahay_page"] = "relaxation"
                st.rerun()
        with c2:
            if st.button("Dismiss", key="companion_auth_suggestion_dismiss", use_container_width=True):
                st.session_state[dismissed_key].add(dismiss_token)
                st.rerun()


def render_suggestion_chips_authenticated(user, conv_db, generate_response) -> None:
    from components.chatbot_launcher import SUGGESTION_CHIPS
    cols = st.columns(len(SUGGESTION_CHIPS))
    for i, chip in enumerate(SUGGESTION_CHIPS):
        with cols[i]:
            if st.button(chip, key=f"auth_companion_chip_{i}", use_container_width=True):
                active_id = st.session_state.get("sahay_active_conversation_id")
                if not active_id:
                    new_convo = conv_db.create_conversation(user)
                    active_id = new_convo["id"]
                    st.session_state["sahay_active_conversation_id"] = active_id
                _send_authenticated_message(user, conv_db, generate_response, active_id, chip)
                st.rerun()


def _send_authenticated_message(user, conv_db, generate_response, conversation_id: str, text: str) -> None:
    conv_db.add_message(user, conversation_id, "user", text)

    history = conv_db.list_messages(user, conversation_id)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]  # exclude the just-added user turn
    language = st.session_state.get("sahay_language", "English")

    with st.spinner("Sahay is thinking..."):
        result = generate_response(text, chat_history=chat_history, language=language)

    conv_db.add_message(user, conversation_id, "assistant", result["reply"])
    st.session_state["sahay_last_mood"] = result.get("mood")
    st.session_state["sahay_last_suggestion"] = result.get("suggestion")
    st.session_state["sahay_last_suggestion_convo_id"] = conversation_id

    # Auto-title a brand-new conversation from the first message, so the
    # history list isn't full of "New conversation" entries.
    convo = conv_db.get_conversation(user, conversation_id)
    if convo and convo.get("title") == "New conversation":
        auto_title = text.strip()[:60] + ("…" if len(text.strip()) > 60 else "")
        conv_db.rename_conversation(user, conversation_id, auto_title)

    # Log the mood event (non-clinical signal only — see chatbot/mood_analyzer.py).
    mood = result.get("mood")
    if mood:
        try:
            conv_db.log_mood_event(user, mood, source="chat", conversation_id=conversation_id)
        except Exception:  # noqa: BLE001 - mood logging must never break the chat turn
            pass
