"""pages/overview.py — Home dashboard.

PHASE 1 VALIDATION UPDATE: replaced empty "—" metric placeholders with
clearly-labeled sample/demo figures so the dashboard reads as an
interactive product preview rather than a grid of blank boxes. Every
card is explicitly captioned "Demo data" — nothing here is a real user's
data, and no health/mood statistic is implied to be clinically meaningful.
"""

from __future__ import annotations

import streamlit as st

from components.cards import metric_card, accent_card, safety_note


def render() -> None:
    st.markdown("### Good to see you.")
    st.write("This is a reflection space — not a medical assessment or diagnosis.")
    safety_note(
        "Sahay is an AI wellness companion for student support and guidance. "
        "It is not a therapist, psychologist, psychiatrist, or doctor, and it "
        "does not replace professional care."
    )

    st.caption("📊 Sample/demo data shown below — not connected to a real account yet.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Today's Check-in", "Not yet done", "Demo data · visit Mood Check-in")
    with c2:
        metric_card("Conversations", "3", "Demo data · this week")
    with c3:
        metric_card("Wellness Activities", "2", "Demo data · breathing, journaling")
    with c4:
        metric_card("Support Resources", "1", "Demo data · viewed this week")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    clicked = accent_card(
        "Talk to Sahay",
        "Your companion is ready to listen whenever you are. Open the panel "
        "in the bottom-right corner, or head to the full Sahay Companion page.",
        cta_label="Open Sahay Companion",
    )
    if clicked:
        st.session_state["sahay_page"] = "companion"
        st.rerun()
