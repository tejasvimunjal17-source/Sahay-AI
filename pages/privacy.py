"""pages/privacy.py — PHASE 4: real privacy explanation + data-control
actions (delete conversations, mood history, or request account
deletion) for authenticated users. Demo Mode shows the explanation only —
there's no real data to control since Demo Mode never touches Supabase."""

from __future__ import annotations

import streamlit as st

from backend import auth


def render() -> None:
    st.markdown("### Privacy")

    st.markdown("##### What Sahay AI stores")
    st.write(
        "If you sign in, Sahay AI stores: your profile (display name, preferred "
        "language), your conversations and messages, mood signals from your chats "
        "and check-ins (including any stress, energy, or sleep-quality levels you "
        "choose to record), and which relaxation activities you've completed. This "
        "is stored so your conversation history and reflections are available when "
        "you come back — it is never shared with other users, and access is "
        "restricted at the database level to your own account (Row Level Security), "
        "not just hidden in the app's interface."
    )

    st.markdown("##### What Sahay AI deliberately does NOT store")
    st.write(
        "Sahay AI does not track which individual support-resource topics you view "
        "(for example, whether you opened 'Loneliness' vs. 'Exam stress' in Support "
        "Resources) — that's a deliberate choice, since which topics someone reads "
        "can be more personally revealing than simply using the app."
    )

    st.markdown("##### Why mood and wellness signals are stored")
    st.write(
        "Mood/sentiment signals, and any stress/energy/sleep levels you record, let "
        "Sahay show you your own approximate history for personal reflection. They "
        "are self-reported or AI-generated, non-clinical signals — never a "
        "diagnosis, never used to infer a clinical condition, and never reviewed by "
        "a person unless you choose to share them."
    )

    st.markdown("##### Demo Mode vs. signing in")
    st.write(
        "In Demo Mode, nothing is sent to or stored in Sahay's database at all — "
        "your conversation and any check-ins exist only in your current browser "
        "session and disappear when it ends. Signing in switches to real, private, "
        "persisted storage as described above."
    )

    st.markdown("##### What Sahay AI does NOT do")
    st.write(
        "Sahay AI is not a therapist, psychologist, psychiatrist, or doctor, and "
        "does not replace professional mental-health care. It does not share your "
        "conversations with anyone else, and administrators do not see your "
        "private conversation content by default."
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("##### Your data controls")

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None
    if user is None:
        st.info("Sign in to manage your own conversation and mood data here. Demo Mode doesn't store anything to manage.")
        return

    from backend import conversations as conv_db

    st.write("You can delete your data at any time:")

    if st.button("Delete all conversation history", key="privacy_delete_conversations"):
        st.session_state["privacy_confirm_convos"] = True
    if st.session_state.get("privacy_confirm_convos"):
        st.warning("This permanently deletes every saved conversation and its messages.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, delete", key="privacy_confirm_convos_yes"):
                conv_db.delete_all_conversations(user)
                st.session_state["privacy_confirm_convos"] = False
                st.success("Conversation history deleted.")
        with c2:
            if st.button("Cancel", key="privacy_confirm_convos_cancel"):
                st.session_state["privacy_confirm_convos"] = False
                st.rerun()

    if st.button("Delete mood history", key="privacy_delete_moods"):
        st.session_state["privacy_confirm_moods"] = True
    if st.session_state.get("privacy_confirm_moods"):
        st.warning("This permanently deletes your mood check-ins and chat-derived mood signals.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, delete", key="privacy_confirm_moods_yes"):
                conv_db.delete_all_mood_events(user)
                st.session_state["privacy_confirm_moods"] = False
                st.success("Mood history deleted.")
        with c2:
            if st.button("Cancel", key="privacy_confirm_moods_cancel"):
                st.session_state["privacy_confirm_moods"] = False
                st.rerun()
    st.caption("To delete a single mood or check-in entry instead of everything, use the 🗑️ button next to it on the Mood History page.")

    st.caption(
        "To delete your account entirely (profile + all associated data), "
        "contact the app administrator — full self-service account deletion "
        "isn't available in this environment yet, though your account's "
        "profile row is set up to be removed automatically if the underlying "
        "Supabase Auth user is ever deleted."
    )
