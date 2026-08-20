"""pages/mood_checkin.py — PHASE 5: adds optional stress/energy/sleep
1-5 scales (010_wellness_scales.sql) alongside the existing Phase 4
mood + note check-in. Same authenticated/demo-mode split as before:
real persistence for signed-in users, session-only preview otherwise."""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note
from backend import auth
from chatbot.mood_analyzer import VALID_MOODS, MOOD_EMOJI

MOODS_ORDERED = ["Happy", "Calm", "Neutral", "Sad", "Anxious", "Stressed", "Lonely", "Angry", "Overwhelmed"]
assert set(MOODS_ORDERED) == VALID_MOODS  # keep this page in sync with the mood analyzer's vocabulary

SCALE_LABELS = {1: "Very low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very high"}
SLEEP_LABELS = {1: "Very poor", 2: "Poor", 3: "Okay", 4: "Good", 5: "Great"}


def render() -> None:
    st.markdown("### How are you feeling today?")
    safety_note(
        "This is a personal wellness check-in, not a medical assessment. Stress, "
        "energy, and sleep are self-reported and non-clinical — Sahay does not "
        "interpret them as a diagnosis of any kind."
    )

    labels = [f"{MOOD_EMOJI[m]} {m}" for m in MOODS_ORDERED]
    choice_label = st.radio("Pick what feels closest", labels, index=None, horizontal=True)
    choice = MOODS_ORDERED[labels.index(choice_label)] if choice_label else None

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.caption("Optional — skip any of these if you'd rather not answer.")

    c1, c2, c3 = st.columns(3)
    with c1:
        stress = st.select_slider("Stress level", options=[1, 2, 3, 4, 5], value=3, format_func=lambda v: SCALE_LABELS[v], key="checkin_stress")
        stress_answered = st.checkbox("Include stress", value=False, key="checkin_stress_include")
    with c2:
        energy = st.select_slider("Energy level", options=[1, 2, 3, 4, 5], value=3, format_func=lambda v: SCALE_LABELS[v], key="checkin_energy")
        energy_answered = st.checkbox("Include energy", value=False, key="checkin_energy_include")
    with c3:
        sleep = st.select_slider("Sleep quality", options=[1, 2, 3, 4, 5], value=3, format_func=lambda v: SLEEP_LABELS[v], key="checkin_sleep")
        sleep_answered = st.checkbox("Include sleep", value=False, key="checkin_sleep_include")

    note = st.text_area(
        "Would you like to tell Sahay a little more? (optional)",
        placeholder="Anything you'd like to add...",
    )

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None

    if st.button("Save check-in", type="primary", key="mood_checkin_save"):
        if not choice:
            st.warning("Pick an option above first, or skip this if you'd rather not.")
            return

        mood_result = {"mood": choice, "sentiment": None, "confidence": None, "risk_level": None}
        stress_val = stress if stress_answered else None
        energy_val = energy if energy_answered else None
        sleep_val = sleep if sleep_answered else None

        if user is not None:
            from backend import conversations as conv_db
            try:
                conv_db.log_mood_event(
                    user, mood_result, source="checkin", note=note or None,
                    stress_level=stress_val, energy_level=energy_val, sleep_quality=sleep_val,
                )
                st.success(f"Noted: {choice}. Thanks for checking in.")
            except Exception as exc:  # noqa: BLE001
                st.error("Couldn't save your check-in right now. Please try again.")
                st.caption(f"Technical detail (dev preview only): {exc}")
        else:
            st.success(f"Noted: {choice}. (Demo Mode preview — sign in to save your check-ins.)")
