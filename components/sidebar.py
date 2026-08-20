"""
components/sidebar.py
----------------------
Custom collapsible left navigation for Sahay AI.

Interaction pattern (expand/collapse + active-page highlighting) is adapted
from LearnMate AI's frontend/custom_sidebar.py drawer mechanism — see
/PHASE0_AUDIT.md section B. Visual hierarchy (a bottom profile row, grouped
nav sections) is adapted from the Fitly UX reference — see
/PHASE0_AUDIT.md section D. Branding, copy, and colors are original to
Sahay AI.

PHASE 1 VALIDATION UPDATE: nav groups restructured to MAIN / WELLNESS /
SUPPORT / ACCOUNT per the Phase 1 validation pass (previous grouping used
different labels — this is a content/grouping fix, not a new feature).
Government Services remains its own top-level destination inside SUPPORT,
still never mixed into the chatbot/companion page.

PHASE 2 UPDATE: bottom profile row now reflects real auth state
(backend.auth.AuthUser) when present, falling back to the Demo Mode
status Phase 1 already had. render_sidebar() takes the auth state as a
parameter rather than importing backend.auth itself, keeping this module
free of any Supabase dependency — it only ever displays what
streamlit_app.py already determined.
"""

from __future__ import annotations

import streamlit as st

from components.theme import sahay_icon_html

# ---------------------------------------------------------------------------
# Navigation model
# ---------------------------------------------------------------------------
NAV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Main", [
        ("Overview", "overview"),
        ("Sahay Companion", "companion"),
        ("Mood Check-in", "mood_checkin"),
        ("Wellness Dashboard", "wellness_dashboard"),
    ]),
    ("Wellness", [
        ("Relaxation", "relaxation"),
        ("Mood History", "mood_history"),
        ("Conversations", "conversations"),
        ("Resources", "resources"),
    ]),
    ("Support", [
        ("Government Services", "government_services"),
        ("Human Help", "human_help"),
    ]),
    ("Account", [
        ("Reports", "reports"),
        ("Profile", "profile"),
        ("Privacy", "privacy"),
        ("Settings", "settings"),
    ]),
]

ALL_PAGE_KEYS = [key for _, items in NAV_GROUPS for _, key in items]

DEFAULT_PAGE = "overview"


def _init_state() -> None:
    st.session_state.setdefault("sahay_page", DEFAULT_PAGE)
    st.session_state.setdefault("sahay_sidebar_open", True)


def render_sidebar(authenticated: bool = False, user=None) -> str:
    """Render the sidebar and return the currently selected page key.

    `authenticated`/`user` come from streamlit_app.py's auth gate — this
    function never calls backend.auth itself (see module docstring).

    Collapse/expand state lives in st.session_state["sahay_sidebar_open"].
    Streamlit's own sidebar already collapses into an off-canvas drawer on
    narrow viewports (its built-in responsive behavior) — this adds a
    *content* density toggle (icons-only vs. icons+labels) on top of that,
    and the main content area reclaims the freed width automatically
    because collapsing this control does not resize Streamlit's own
    sidebar container, only what's rendered inside it.
    """
    _init_state()

    with st.sidebar:
        collapsed = not st.session_state["sahay_sidebar_open"]

        top_l, top_r = st.columns([5, 1])
        with top_l:
            if collapsed:
                st.markdown(sahay_icon_html(30), unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;'>"
                    f"{sahay_icon_html(28)}"
                    f"<span class='sahay-display' style='font-size:19px;font-weight:700;'>Sahay AI</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        with top_r:
            toggle_label = "»" if collapsed else "«"
            if st.button(toggle_label, key="sidebar_collapse_toggle", help="Collapse/expand navigation"):
                st.session_state["sahay_sidebar_open"] = collapsed
                st.rerun()

        st.markdown("---")

        for group_label, items in NAV_GROUPS:
            if not collapsed:
                st.markdown(
                    f"<div class='sahay-sidebar-group-label'>{group_label}</div>",
                    unsafe_allow_html=True,
                )
            for label, key in items:
                active = st.session_state["sahay_page"] == key
                btn_label = _icon_for(key) if collapsed else f"{_icon_for(key)}  {label}"
                if st.button(
                    btn_label,
                    key=f"nav_{key}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                    help=label if collapsed else None,
                ):
                    st.session_state["sahay_page"] = key
                    st.rerun()

        # ---- Bottom profile / auth-status row (Fitly-inspired placement) ----
        st.markdown("<div class='sahay-sidebar-profile'></div>", unsafe_allow_html=True)
        if collapsed:
            st.markdown("👤")
            if st.button("⏻", key="sidebar_signout_collapsed", help="Log out"):
                _sign_out(authenticated)
        else:
            if authenticated and user is not None:
                label = user.email or "Signed in"
                st.markdown(
                    f"**{label}**  \n"
                    f"<span style='font-size:12px;color:#6B7280;'>Signed in</span>",
                    unsafe_allow_html=True,
                )
                if st.button("Log Out", key="sidebar_signout", use_container_width=True):
                    _sign_out(authenticated)
            else:
                st.markdown(
                    "**Student**  \n"
                    "<span style='font-size:12px;color:#6B7280;'>Demo Mode</span>",
                    unsafe_allow_html=True,
                )
                if st.button("Exit Demo Mode", key="sidebar_exit_demo", use_container_width=True):
                    _sign_out(authenticated)
                st.caption("Sign in for a real, private account.")

    return st.session_state["sahay_page"]


def _sign_out(authenticated: bool) -> None:
    if authenticated:
        from backend import auth
        auth.sign_out()
    st.session_state["sahay_view"] = "landing"
    st.session_state["sahay_demo_mode"] = False
    st.session_state["sahay_page"] = DEFAULT_PAGE
    st.rerun()


def _icon_for(page_key: str) -> str:
    icons = {
        "overview": "🏠",
        "companion": "💬",
        "mood_checkin": "🙂",
        "relaxation": "🧘",
        "wellness_dashboard": "📊",
        "resources": "📚",
        "human_help": "🤝",
        "government_services": "🇮🇳",
        "conversations": "🗂️",
        "mood_history": "📈",
        "reports": "📄",
        "profile": "👤",
        "privacy": "🔒",
        "settings": "⚙️",
    }
    return icons.get(page_key, "•")
