"""pages/profile.py — PHASE 2: reads/updates the real `profiles` row for a
signed-in user via the anon-key client (RLS-scoped to auth.uid()). In
Demo Mode (no real session), falls back to Phase 1's disabled placeholder
fields — Demo Mode never reads or writes Supabase."""

from __future__ import annotations

import streamlit as st

from backend import auth


def render() -> None:
    st.markdown("### Profile")

    user = auth.get_current_user() if st.session_state.get(
        "sahay_supabase_session"
    ) else None

    if user is None:
        st.text_input("Display name", placeholder="Not available in Demo Mode", disabled=True)
        st.selectbox("Preferred language", ["English", "Hindi", "Hinglish"], disabled=True)
        st.caption("Sign in (see the landing page) to create and edit a real profile.")
        return

    try:
        profile = auth.get_profile(user)
    except Exception as exc:  # noqa: BLE001
        st.error("Couldn't load your profile right now. Please try again.")
        st.caption(f"Technical detail (dev preview only): {exc}")
        return

    if profile is None:
        st.warning("No profile found for your account yet. Try refreshing the page.")
        return

    st.caption(f"Signed in as {user.email}")

    with st.form("profile_form"):
        display_name = st.text_input("Display name", value=profile.get("display_name") or "")
        languages = ["English", "Hindi", "Hinglish"]
        current_lang_code = profile.get("preferred_language") or "en"
        lang_labels = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
        current_label = lang_labels.get(current_lang_code, "English")
        preferred_language = st.selectbox(
            "Preferred language", languages,
            index=languages.index(current_label) if current_label in languages else 0,
        )
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        lang_code = {"English": "en", "Hindi": "hi", "Hinglish": "hinglish"}[preferred_language]
        try:
            client = auth.get_client_for_current_user()
            client.table("profiles").update({
                "display_name": display_name,
                "preferred_language": lang_code,
            }).eq("id", user.id).execute()
            st.success("Profile updated.")
        except Exception as exc:  # noqa: BLE001
            st.error("Couldn't save your changes right now. Please try again.")
            st.caption(f"Technical detail (dev preview only): {exc}")
