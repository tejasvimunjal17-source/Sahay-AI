"""pages/conversations.py — PHASE 4: full conversation list (same data as
the Sahay Companion page's history panel), with a link to open each in
the Companion page. Kept as a separate nav destination since the master
spec lists "Conversation History" as its own sidebar item."""

from __future__ import annotations

import streamlit as st

from components.cards import empty_state
from backend import auth


def render() -> None:
    st.markdown("### Conversation History")

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None
    if user is None:
        empty_state("🗂️", "Sign in to save and revisit your conversations. In Demo Mode, conversations aren't saved.")
        return

    from backend import conversations as conv_db
    try:
        convo_list = conv_db.list_conversations(user)
    except Exception as exc:  # noqa: BLE001
        st.error("Couldn't load your conversations right now. Please try again.")
        st.caption(f"Technical detail (dev preview only): {exc}")
        return

    if not convo_list:
        empty_state("🗂️", "No conversations yet — start one from the Sahay Companion page.")
        return

    for c in convo_list:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{c['title'] or 'New conversation'}**")
                st.caption(f"Last updated {c['updated_at'][:10]}")
            with col2:
                if st.button("Open", key=f"convlist_open_{c['id']}", use_container_width=True):
                    st.session_state["sahay_active_conversation_id"] = c["id"]
                    st.session_state["sahay_page"] = "companion"
                    st.rerun()
