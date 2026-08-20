"""
pages/reports.py
-------------------
PHASE 6 IMPLEMENTATION.

Authenticated users: real Wellness Reflection Report (PDF/DOCX) built
from exports._shared.build_report_data(), bounded to a selectable
7/14/30-day period — never unlimited history.

Demo Mode: a small, clearly-labeled SAMPLE export of the current
session's chat only (via exports._shared.build_demo_report_data()) —
never touches Supabase, never persisted, never implies it's a real
history. This matches the approved Phase 6 decision (see
PHASE6_PRE_IMPLEMENTATION_AUDIT.md §17 / your Phase 6 continuation
instructions).
"""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note, empty_state
from backend import auth
from exports._shared import build_report_data, build_demo_report_data, VALID_PERIOD_DAYS, DEFAULT_PERIOD_DAYS

PERIOD_LABELS = {7: "Last 7 days", 14: "Last 14 days", 30: "Last 30 days"}


def render() -> None:
    st.markdown("### Reports")
    safety_note(
        "Reports are an AI-generated wellness reflection summary for your own use — "
        "not a medical assessment or clinical record."
    )

    user = auth.get_current_user() if st.session_state.get("sahay_supabase_session") else None

    if user is None:
        _render_demo()
    else:
        _render_authenticated(user)


# ---------------------------------------------------------------------------
# Demo Mode — session-only sample export
# ---------------------------------------------------------------------------

def _render_demo() -> None:
    st.info(
        "You're in Demo Mode. You can export a small **sample** report of your "
        "current session's chat — nothing is saved, and this is not a real, "
        "persisted wellness history. Sign in to build and export a real report "
        "over time."
    )

    chat_history = st.session_state.get("sahay_fullpage_history", []) or st.session_state.get("sahay_chat_history", [])
    data = build_demo_report_data(chat_history)

    if not data.has_any_data:
        empty_state("📄", "Chat with Sahay first (on the Companion page) to have something to include in a sample export.")
        return

    st.caption(f"Sample export preview — {data.conversations_summary[0]['message_count']} messages from this session.")
    _download_buttons(data, key_prefix="demo")


# ---------------------------------------------------------------------------
# Authenticated — real bounded report
# ---------------------------------------------------------------------------

def _render_authenticated(user) -> None:
    from backend import conversations as conv_db

    st.session_state.setdefault("reports_period_days", DEFAULT_PERIOD_DAYS)
    period_label = st.selectbox(
        "Report period",
        [PERIOD_LABELS[d] for d in VALID_PERIOD_DAYS],
        index=VALID_PERIOD_DAYS.index(st.session_state["reports_period_days"]),
        key="reports_period_select",
    )
    period_days = {v: k for k, v in PERIOD_LABELS.items()}[period_label]
    st.session_state["reports_period_days"] = period_days

    try:
        profile = auth.get_profile(user)
        display_name = (profile or {}).get("display_name") or None
    except Exception:  # noqa: BLE001 - a profile-fetch hiccup shouldn't block the report
        display_name = None

    with st.spinner("Preparing your report..."):
        try:
            data = build_report_data(user, conv_db, period_days=period_days, display_name=display_name)
        except Exception as exc:  # noqa: BLE001
            st.error("Couldn't prepare your report right now. Please try again.")
            st.caption(f"Technical detail (dev preview only): {exc}")
            return

    if not data.has_any_data:
        empty_state(
            "📄",
            f"No conversations, check-ins, or activities found in the {period_label.lower()}. "
            "Try a longer period, or come back after using Sahay a bit more.",
        )
        return

    st.markdown("##### Preview")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Conversations", len(data.conversations_summary))
    with c2:
        st.metric("Mood entries", len(data.mood_events))
    with c3:
        st.metric("Activities completed", data.activities_completed)
    st.caption(f"Period: {data.period_start} – {data.period_end}")

    _download_buttons(data, key_prefix="auth")


# ---------------------------------------------------------------------------
# Shared download buttons
# ---------------------------------------------------------------------------

def _download_buttons(data, key_prefix: str) -> None:
    from exports.pdf import build_pdf_report, PdfExportError
    from exports.docx import build_docx_report, DocxExportError

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Prepare PDF", key=f"{key_prefix}_prepare_pdf", use_container_width=True):
            try:
                pdf_bytes = build_pdf_report(data)
                st.session_state[f"{key_prefix}_pdf_bytes"] = pdf_bytes
            except PdfExportError as exc:
                st.error(str(exc))
        if st.session_state.get(f"{key_prefix}_pdf_bytes"):
            st.download_button(
                "Download PDF",
                data=st.session_state[f"{key_prefix}_pdf_bytes"],
                file_name="sahay-wellness-report.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_download_pdf",
                use_container_width=True,
            )
    with c2:
        if st.button("Prepare DOCX", key=f"{key_prefix}_prepare_docx", use_container_width=True):
            try:
                docx_bytes = build_docx_report(data)
                st.session_state[f"{key_prefix}_docx_bytes"] = docx_bytes
            except DocxExportError as exc:
                st.error(str(exc))
        if st.session_state.get(f"{key_prefix}_docx_bytes"):
            st.download_button(
                "Download DOCX",
                data=st.session_state[f"{key_prefix}_docx_bytes"],
                file_name="sahay-wellness-report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"{key_prefix}_download_docx",
                use_container_width=True,
            )
