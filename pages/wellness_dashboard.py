"""pages/wellness_dashboard.py — PHASE 4/5: real non-clinical aggregates for
authenticated users (conversation count, mood check-ins, mood
distribution + stress/energy/sleep trend charts, activities completed —
all from mood_events/wellness_activity_logs/conversations). Demo Mode
shows "not enough activity yet" rather than inventing numbers. Resource
views are deliberately NOT tracked (Phase 5 privacy decision — logging
which support topics someone reads is more revealing than a breathing-
exercise completion) — that card is honestly labeled, not hidden."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import streamlit as st

from components.cards import metric_card, safety_note
from backend import auth


def render() -> None:
    st.markdown("### Wellness Dashboard")
    safety_note(
        "This dashboard is for personal wellness reflection only. It is not a "
        "medical assessment or diagnosis."
    )

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None

    if user is None:
        st.info("Sign in to see your own wellness activity here. Showing an example layout below.")
        c1, c2 = st.columns(2)
        with c1:
            metric_card("Conversations this week", "Not enough activity yet", "")
        with c2:
            metric_card("Mood check-ins", "Not enough activity yet", "")
        c3, c4 = st.columns(2)
        with c3:
            metric_card("Relaxation activities completed", "Not enough activity yet", "")
        with c4:
            metric_card("Support resources viewed", "Not tracked (by design)", "")
        return

    from backend import conversations as conv_db

    try:
        convo_list = conv_db.list_conversations(user)
        mood_events = conv_db.list_mood_events(user, limit=200)
        activity_logs = conv_db.list_wellness_activity_logs(user, limit=200)
    except Exception as exc:  # noqa: BLE001
        st.error("Couldn't load your dashboard right now. Please try again.")
        st.caption(f"Technical detail (dev preview only): {exc}")
        return

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    def _since(items: list[dict], field: str) -> list[dict]:
        result = []
        for item in items:
            try:
                ts = datetime.fromisoformat(item[field].replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if ts >= week_ago:
                result.append(item)
        return result

    convos_this_week = _since(convo_list, "created_at")
    checkins = [m for m in mood_events if m.get("source") == "checkin"]
    checkins_this_week = _since(checkins, "created_at")
    activities_this_week = _since(activity_logs, "completed_at")

    c1, c2 = st.columns(2)
    with c1:
        metric_card(
            "Conversations this week",
            str(len(convos_this_week)) if convo_list else "Not enough activity yet",
            "Based on your saved conversations",
        )
    with c2:
        metric_card(
            "Mood check-ins this week",
            str(len(checkins_this_week)) if checkins else "Not enough activity yet",
            "From the Mood Check-in page",
        )

    c3, c4 = st.columns(2)
    with c3:
        metric_card(
            "Relaxation activities completed",
            str(len(activities_this_week)) if activity_logs else "Not enough activity yet",
            "This week",
        )
    with c4:
        metric_card("Support resources viewed", "Not tracked (by design)", "Sahay doesn't log which resources you view, to protect your privacy")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if mood_events:
        most_common_mood, most_common_count = Counter(m["mood"] for m in mood_events if m.get("mood")).most_common(1)[0]
        metric_card("Most frequently recorded mood", most_common_mood, f"Recorded {most_common_count} time(s)")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("##### Approximate mood distribution")
    st.caption("A non-clinical signal based on your recent chats and check-ins — not a diagnosis.")
    if mood_events:
        counts = Counter(m["mood"] for m in mood_events if m.get("mood"))
        st.bar_chart(dict(counts.most_common()))
    else:
        st.caption("Not enough activity yet.")

    stress_vals = [m["stress_level"] for m in reversed(mood_events) if m.get("stress_level") is not None]
    energy_vals = [m["energy_level"] for m in reversed(mood_events) if m.get("energy_level") is not None]
    sleep_vals = [m["sleep_quality"] for m in reversed(mood_events) if m.get("sleep_quality") is not None]

    if stress_vals or energy_vals or sleep_vals:
        st.markdown("##### Self-reported wellness trends")
        st.caption(
            "These indicators reflect your own activity and self-reported information. "
            "They are not medical measurements or diagnoses."
        )
        cols = st.columns(3)
        with cols[0]:
            if stress_vals:
                st.caption("Stress (1-5)")
                st.line_chart(stress_vals)
        with cols[1]:
            if energy_vals:
                st.caption("Energy (1-5)")
                st.line_chart(energy_vals)
        with cols[2]:
            if sleep_vals:
                st.caption("Sleep quality (1-5)")
                st.line_chart(sleep_vals)
    else:
        st.caption("Add stress/energy/sleep to a check-in to see trends here.")
