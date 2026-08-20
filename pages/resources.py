"""pages/resources.py — PHASE 5: reorganized into the 10 named categories
from the approved Phase 5 scope, each with a practical suggestion and an
optional linked wellness activity (pointing at a pages/relaxation.py
activity key). Still static content, no persistence, no medical claims."""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note

# Each: (category label, icon, description, practical suggestion, optional activity_key)
CATEGORIES = [
    ("Academic stress", "📚", "General workload and academic pressure.",
     "It's normal for workload to feel heavy sometimes. Talking to a teacher or mentor about pacing can help more than struggling silently.",
     "study_break"),
    ("Exam preparation stress", "📝", "Stress specifically around exams and tests.",
     "Break revision into small, specific sessions rather than one long block. Short breaks help concentration more than pushing through.",
     "box_breathing"),
    ("Procrastination", "⏳", "Difficulty starting or continuing tasks.",
     "Starting is often the hardest part — try committing to just 5 minutes on a task rather than the whole thing.",
     None),
    ("Sleep routine", "😴", "Building a more consistent, restful sleep pattern.",
     "A consistent sleep and wake time, and less screen time before bed, are simple things that often help.",
     "sleep_wind_down"),
    ("Loneliness", "🥺", "Feeling disconnected or missing a sense of belonging.",
     "Small, low-pressure social steps — a shared meal, a study group, a club — can help more than waiting to feel 'ready' to connect.",
     None),
    ("Study breaks", "☕", "Using breaks effectively during study sessions.",
     "Short, regular breaks (a walk, stretching, water) tend to help focus more than skipping breaks entirely.",
     "light_movement"),
    ("Time management", "🗓️", "Organizing coursework, deadlines, and daily time.",
     "Writing down just the next 1-2 tasks (instead of a whole overwhelming list) can make starting easier.",
     None),
    ("Motivation", "🔥", "Finding energy and drive for tasks that feel hard to begin.",
     "Motivation often follows action, not the other way around — starting a small step can help build momentum.",
     "mindful_pause"),
    ("Social support", "🤝", "Building and using your support network.",
     "You don't have to share everything at once — even a short conversation with someone you trust can help.",
     None),
    ("Digital wellbeing", "📱", "A healthier relationship with screens and social media.",
     "Short, regular breaks from your phone or laptop — especially before bed — can help with both focus and sleep.",
     "mindful_pause"),
]


def render() -> None:
    st.markdown("### Support Resources")
    safety_note(
        "General, practical guidance for common student experiences — not "
        "medical or clinical advice."
    )

    for label, icon, desc, tip, activity_key in CATEGORIES:
        with st.container(border=True):
            st.markdown(f"**{icon} {label}**")
            st.caption(desc)
            st.write(tip)
            if activity_key:
                if st.button(f"Try a related activity", key=f"resource_activity_{activity_key}_{label}"):
                    st.session_state["sahay_page"] = "relaxation"
                    st.rerun()
