"""
streamlit_app.py
------------------
Sahay AI — main Streamlit entrypoint.

PHASE 2: real Supabase Auth (email/password + Google OAuth) now gates the
app shell, alongside Phase 1's Demo Mode (kept as an explicit, clearly
separated, no-account preview path — see components/landing.py and
PHASE2_IMPLEMENTATION_REPORT.md §9). No OpenRouter, mood analysis,
conversation storage, or AI logic exists yet — those remain Phase 3+.

AUTH GATE (see backend/auth.py, PHASE2_ARCHITECTURE_AUDIT.md §4.3):
Authentication is checked ONCE here, centrally, rather than per-page.
st.session_state["sahay_view"] is UI routing, not the security boundary
— the actual boundary is backend.auth.get_current_user(), which
re-validates the session against Supabase on every run rather than
trusting a locally-set flag.

Run locally:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from config import APP_CONFIG, SUPABASE_USER_CONFIG
from backend.logging_config import get_logger
from backend import auth
from components.theme import inject_css
from components.landing import render_landing_page
from components.sidebar import render_sidebar, ALL_PAGE_KEYS, DEFAULT_PAGE
from components.topbar import render_topbar
from components.chatbot_launcher import render_chatbot_launcher

from pages import (
    overview, companion, mood_checkin, relaxation, wellness_dashboard,
    resources, human_help, government_services, conversations,
    mood_history, reports, profile, privacy, settings,
)

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{APP_CONFIG.app_name} | Student Wellness Companion",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("sahay_dark_mode", False)
st.session_state.setdefault("sahay_view", "landing")   # "landing" | "app"
st.session_state.setdefault("sahay_demo_mode", False)
inject_css(dark_mode=st.session_state["sahay_dark_mode"])

PAGE_TITLES = {
    "overview": "Home",
    "companion": "AI Companion",
    "mood_checkin": "Mood Check-in",
    "relaxation": "Relaxation",
    "wellness_dashboard": "Wellness Dashboard",
    "resources": "Support Resources",
    "human_help": "Human Help",
    "government_services": "Government & Student Services",
    "conversations": "Conversation History",
    "mood_history": "Mood History",
    "reports": "Reports",
    "profile": "Profile",
    "privacy": "Privacy",
    "settings": "Settings",
}

PAGE_RENDERERS = {
    "overview": overview.render,
    "companion": companion.render,
    "mood_checkin": mood_checkin.render,
    "relaxation": relaxation.render,
    "wellness_dashboard": wellness_dashboard.render,
    "resources": resources.render,
    "human_help": human_help.render,
    "government_services": government_services.render,
    "conversations": conversations.render,
    "mood_history": mood_history.render,
    "reports": reports.render,
    "profile": profile.render,
    "privacy": privacy.render,
    "settings": settings.render,
}

assert set(PAGE_RENDERERS.keys()) == set(ALL_PAGE_KEYS), (
    "Navigation model in components/sidebar.py and the page router in "
    "streamlit_app.py have drifted out of sync."
)


def _handle_oauth_callback() -> None:
    """If the user was just redirected back from Google via Supabase,
    complete the sign-in. No-op on any normal page load. Any failure is
    shown as a friendly landing-page notice, never a raw traceback."""
    if not SUPABASE_USER_CONFIG.is_configured:
        return
    try:
        user = auth.complete_oauth_from_query_params()
        if user is not None:
            st.session_state["sahay_view"] = "app"
            st.session_state["sahay_demo_mode"] = False
            st.rerun()
    except auth.AuthError as exc:
        st.session_state["sahay_auth_error"] = str(exc)


def main() -> None:
    _handle_oauth_callback()

    # ------------------------------------------------------------------
    # AUTH GATE — the real security boundary (see module docstring).
    # A real signed-in user always wins over a stale Demo Mode flag.
    # ------------------------------------------------------------------
    current_user = None
    if SUPABASE_USER_CONFIG.is_configured:
        current_user = auth.get_current_user()

    is_demo = st.session_state["sahay_demo_mode"] and current_user is None
    authenticated = current_user is not None

    if not authenticated and not is_demo:
        st.session_state["sahay_view"] = "landing"
        render_landing_page()
        return

    # ------------------------------------------------------------------
    # APP SHELL — either a real authenticated session, or Demo Mode.
    # Demo Mode NEVER touches Supabase (see components/*, pages/* — none
    # of Phase 1/2's page modules make a Supabase call themselves; only
    # backend/auth.py does, and only when authenticated is True).
    # ------------------------------------------------------------------
    st.session_state["sahay_view"] = "app"
    current_page = render_sidebar(authenticated=authenticated, user=current_user)
    render_topbar(PAGE_TITLES.get(current_page, "Sahay AI"))

    renderer = PAGE_RENDERERS.get(current_page, PAGE_RENDERERS[DEFAULT_PAGE])
    try:
        renderer()
    except Exception as exc:  # noqa: BLE001 - top-level safety net, mirrors LearnMate's pattern
        logger.exception("Unhandled error rendering page '%s'", current_page)
        st.error("Something went wrong displaying this page. Please try again.")
        st.caption(f"Technical detail (visible in dev preview only): {exc}")

    render_chatbot_launcher()


main()
