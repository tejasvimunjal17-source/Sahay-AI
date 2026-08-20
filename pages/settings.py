"""pages/settings.py — PHASE 1: dark mode toggle only (the one setting that
is genuinely functional this phase); everything else is a disabled preview."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.markdown("### Settings")
    dark = st.toggle("Dark mode", value=st.session_state.get("sahay_dark_mode", False))
    if dark != st.session_state.get("sahay_dark_mode", False):
        st.session_state["sahay_dark_mode"] = dark
        st.rerun()
    st.selectbox("Notification preferences", ["Email", "None"], disabled=True)
    st.caption("Additional settings connect to a real profile in Phase 2.")
