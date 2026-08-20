"""
components/topbar.py
---------------------
Minimal top utility bar — date/time context + placeholder account controls.
No auth or notification data is real yet (Phase 1 scope: layout only).
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st


def render_topbar(page_title: str) -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"<span style='color:#6B7280;font-size:13px;'>"
            f"{datetime.now().strftime('%A, %d %B %Y')}</span>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            "<div style='text-align:right;color:#6B7280;font-size:13px;'>"
            "🔔 &nbsp; 👤</div>",
            unsafe_allow_html=True,
        )
    st.markdown(f"## {page_title}")
