"""pages/human_help.py — PHASE 5: restructured into two visually distinct
tiers (Normal Support / Urgent Support) per the approved audit, calm
visual hierarchy — the normal-support section stays low-key; the urgent
section is the only place with any warning styling, so the rest of the
app never looks like an emergency screen. Crisis resources still render
from content/crisis_resources.py (still empty by default — nothing
invented), same graceful-empty-list handling as chatbot/safety.py."""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note
from content.crisis_resources import CRISIS_RESOURCES

NORMAL_SUPPORT = [
    ("A trusted friend", "When you just need someone to listen, or to not feel alone with something."),
    ("Family member", "When you want support from someone who knows you well."),
    ("Teacher or college mentor", "When academic stress, deadlines, or a specific class is the main issue."),
    ("College support service", "For academic accommodations, advising, or campus-specific resources."),
    ("Counselor or qualified mental-health professional", "When feelings are lasting, intense, or affecting daily life — they can help in ways Sahay can't."),
]

URGENT_SUPPORT = [
    ("Immediate danger to yourself", "Contact local emergency services or a trusted person right now — don't wait."),
    ("Thoughts of self-harm or suicide", "Reach out immediately to emergency services, a crisis line, or someone you trust."),
    ("Risk of harm to someone else", "Contact local emergency services immediately."),
    ("A serious medical emergency", "Contact local emergency services or go to the nearest emergency room."),
]


def render() -> None:
    st.markdown("### Human Help")
    safety_note(
        "Sahay AI is an AI wellness companion — not a therapist, doctor, or crisis "
        "service — and does not replace professional or emergency support."
    )

    st.markdown("##### Normal support — when you'd like someone to talk to")
    for who, when in NORMAL_SUPPORT:
        with st.container(border=True):
            st.markdown(f"**{who}**")
            st.caption(when)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("##### 🚨 Urgent support — if there's immediate danger")
    st.error(
        "If you are in immediate danger, please contact local emergency services "
        "or a trusted person right away — this is the one part of Sahay that's "
        "meant to stand out."
    )
    for situation, action in URGENT_SUPPORT:
        with st.container(border=True):
            st.markdown(f"**{situation}**")
            st.caption(action)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("##### Crisis & support resources")

    if CRISIS_RESOURCES:
        for r in CRISIS_RESOURCES:
            with st.container(border=True):
                st.markdown(f"**{r['name']}**")
                st.write(r.get("description", ""))
                st.caption(f"{r.get('contact', '')} · {r.get('availability', '')} · {r.get('region', '')}")
    else:
        st.warning(
            "Verified crisis and counseling resources will be added here once "
            "confirmed from official sources — none are populated yet, to avoid "
            "displaying unverified information. If you're a student in India, "
            "your campus counseling office or a trusted teacher, family member, "
            "or friend is a good place to start right now."
        )
