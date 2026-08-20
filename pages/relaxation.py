"""pages/relaxation.py — PHASE 4: full activity detail (instructions,
duration, timer, completion), with completion logged to
wellness_activity_logs for authenticated users; Demo Mode shows the same
activities but doesn't log completion anywhere."""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note
from backend import auth

ACTIVITIES = [
    {
        "key": "breathing_4_4",
        "icon": "🌬️",
        "title": "4-4 Breathing",
        "duration": "2 minutes",
        "description": "A simple steady-breathing exercise to help you settle.",
        "instructions": [
            "Sit comfortably and relax your shoulders.",
            "Breathe in slowly through your nose for 4 counts.",
            "Breathe out slowly through your mouth for 4 counts.",
            "Repeat for about 2 minutes, or as long as feels helpful.",
        ],
    },
    {
        "key": "box_breathing",
        "icon": "🔲",
        "title": "Box Breathing",
        "duration": "3 minutes",
        "description": "A four-part breathing pattern used to steady a racing mind.",
        "instructions": [
            "Breathe in for 4 counts.",
            "Hold for 4 counts.",
            "Breathe out for 4 counts.",
            "Hold for 4 counts.",
            "Repeat the cycle for a few minutes.",
        ],
    },
    {
        "key": "grounding_54321",
        "icon": "🧭",
        "title": "5-4-3-2-1 Grounding",
        "duration": "3 minutes",
        "description": "A sensory grounding exercise for when things feel overwhelming.",
        "instructions": [
            "Name 5 things you can see around you.",
            "Name 4 things you can touch.",
            "Name 3 things you can hear.",
            "Name 2 things you can smell.",
            "Name 1 thing you can taste.",
        ],
    },
    {
        "key": "mindful_pause",
        "icon": "🧘",
        "title": "Short Mindful Pause",
        "duration": "1 minute",
        "description": "A brief pause to notice how you're feeling right now, without judgment.",
        "instructions": [
            "Close your eyes if that feels comfortable.",
            "Notice your breath without trying to change it.",
            "Notice any tension in your body, and let your shoulders drop.",
            "Open your eyes when you're ready.",
        ],
    },
    {
        "key": "journaling_prompt",
        "icon": "📓",
        "title": "Journaling Prompt",
        "duration": "5 minutes",
        "description": "A prompt to help you reflect in writing.",
        "instructions": [
            "Find a quiet moment and something to write with.",
            "Prompt: \"What's one thing that's been on my mind today, and what's one small step I could take about it?\"",
            "Write freely for a few minutes — there's no right answer.",
        ],
    },
    {
        "key": "study_break",
        "icon": "☕",
        "title": "Study Break",
        "duration": "5-10 minutes",
        "description": "A structured short break between study sessions.",
        "instructions": [
            "Step away from your desk or screen.",
            "Stretch, get some water, or look outside for a moment.",
            "Avoid switching straight to another screen if you can.",
            "Return to studying once the break ends.",
        ],
    },
    {
        "key": "light_movement",
        "icon": "🚶",
        "title": "Light Movement",
        "duration": "5 minutes",
        "description": "A quick stretch or short walk to reset your body and mind.",
        "instructions": [
            "Stand up and stretch your arms, neck, and back gently.",
            "If you can, take a short walk — even a few minutes helps.",
            "Notice how your body feels afterward.",
        ],
    },
    {
        "key": "sleep_wind_down",
        "icon": "😴",
        "title": "Sleep Wind-Down",
        "duration": "10 minutes",
        "description": "Gentle tips for an easier transition to sleep.",
        "instructions": [
            "Dim the lights and step away from bright screens if you can.",
            "Try a few slow, deep breaths.",
            "Jot down anything on your mind so it doesn't have to keep you awake.",
            "Keep your room cool and comfortable.",
        ],
    },
]


def render() -> None:
    st.markdown("### Relaxation Center")
    safety_note(
        "These are general wellness activities for your own use — not medical "
        "treatment, and not a cure for anxiety, depression, or any condition."
    )

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None
    st.session_state.setdefault("sahay_completed_activities", set())

    cols = st.columns(2)
    for i, activity in enumerate(ACTIVITIES):
        with cols[i % 2]:
            _render_activity_card(activity, user)


def _render_activity_card(activity: dict, user) -> None:
    key = activity["key"]
    with st.container(border=True):
        st.markdown(f"**{activity['icon']} {activity['title']}**")
        st.caption(f"{activity['duration']} · {activity['description']}")

        expanded_key = f"relax_expanded_{key}"
        if st.button("Start", key=f"relax_start_{key}", use_container_width=True):
            st.session_state[expanded_key] = True

        if st.session_state.get(expanded_key):
            for step in activity["instructions"]:
                st.markdown(f"- {step}")
            already_done = key in st.session_state["sahay_completed_activities"]
            if already_done:
                st.success("Completed ✓")
            else:
                if st.button("Mark complete", key=f"relax_complete_{key}"):
                    st.session_state["sahay_completed_activities"].add(key)
                    if user is not None:
                        from backend import conversations as conv_db
                        try:
                            conv_db.log_wellness_activity(user, key)
                        except Exception:  # noqa: BLE001 - completion marking must never crash the page
                            pass
                    st.rerun()
