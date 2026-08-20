"""
components/cards.py
--------------------
Reusable presentational cards. Pure UI — no data fetching, no AI/DB calls.
"""

from __future__ import annotations

import streamlit as st


def metric_card(label: str, value: str, caption: str = "") -> None:
    st.markdown(
        f"""
        <div class="sahay-card">
            <div class="sahay-card-muted-label">{label}</div>
            <p class="sahay-card-metric">{value}</p>
            <div class="sahay-card-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def accent_card(title: str, body: str, cta_label: str | None = None) -> bool:
    """Dark gradient card used for Sahay-branded callouts. Returns True if
    the optional CTA button was clicked this run."""
    st.markdown(
        f"""
        <div class="sahay-accent-card">
            <div class="sahay-card-muted-label" style="color:rgba(255,255,255,0.75);">SAHAY</div>
            <p style="font-size:19px;font-weight:700;margin:2px 0 6px 0;">{title}</p>
            <div class="sahay-card-caption">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label:
        return st.button(cta_label, key=f"accent_cta_{title}")
    return False


def empty_state(icon: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="sahay-card" style="text-align:center;padding:40px 20px;">
            <div style="font-size:34px;margin-bottom:10px;">{icon}</div>
            <div style="color:#6B7280;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def safety_note(text: str) -> None:
    """Small, consistent disclaimer strip — used wherever the app needs to
    state 'this is not a medical assessment/diagnosis' per the master spec."""
    st.markdown(f"<div class='sahay-safety-note'>{text}</div>", unsafe_allow_html=True)
