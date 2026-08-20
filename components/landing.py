"""
components/landing.py
------------------------
Pre-authentication landing page.

PHASE 2 UPDATE: real email/password sign-up, log-in, and forgot-password
forms now call backend/auth.py. "Continue with Google" is wired to a real
Supabase/Google OAuth redirect when GOOGLE_OAUTH_CONFIG is configured —
see PHASE2_IMPLEMENTATION_REPORT.md for what has and hasn't been
live-tested. When OAuth isn't configured (the default — no secrets set),
the button still shows the same friendly "not available yet" notice
Phase 1 had, rather than erroring.

"Continue in Demo Mode" is KEPT, per your Phase 2 instructions, as an
explicit, clearly-labeled, no-account preview path — see
streamlit_app.py's auth gate and components/sidebar.py for how it stays
visually and functionally separate from a real signed-in session (never
touches Supabase, never reads/writes profiles).

Design lineage (see PHASE0_AUDIT.md §D): step-indicator-style hero,
oversized two-line headline, primary CTA as a pill button — structurally
inspired by the Fitly UX reference, with Sahay's own palette, copy, icon.
"""

from __future__ import annotations

import streamlit as st

from components.theme import sahay_icon_html, COLORS
from config import GOOGLE_OAUTH_CONFIG, SUPABASE_USER_CONFIG

FEATURES = [
    ("💬", "Talk it through", "A calm, judgment-free space to reflect on how your day or week is going."),
    ("🙂", "Check in with yourself", "A quick, optional mood check-in — never mandatory, never a diagnosis."),
    ("🧘", "Reset when you need to", "Short breathing, grounding, and study-break exercises you can use anytime."),
    ("🤝", "Find real support", "Clear pointers to campus, professional, and government resources when you want more than a chat."),
]


def render_landing_page() -> None:
    _auth_error_banner()
    _hero()
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    _auth_forms()
    st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)
    _feature_grid()
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    _safety_notice()
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    _footer()


def _auth_error_banner() -> None:
    error = st.session_state.pop("sahay_auth_error", None)
    if error:
        st.error(error)


def _hero() -> None:
    left, right = st.columns([3, 2])
    with left:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:18px;'>"
            f"{sahay_icon_html(30)}"
            f"<span style='font-weight:700;font-size:18px;'>Sahay AI</span>"
            f"<span style='background:{COLORS['soft_teal']}22;color:{COLORS['soft_teal']};"
            f"padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;'>BETA</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h1 class='sahay-display' style='font-size:44px;line-height:1.15;margin-bottom:4px;'>"
            "Your AI Companion<br>for Student Wellbeing.</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='font-size:16px;color:#6B7280;max-width:520px;margin-top:10px;'>"
            "Reflect on how you're feeling, manage everyday student stress, explore "
            "wellness activities, and find appropriate support when you need it.</p>",
            unsafe_allow_html=True,
        )
        st.caption("Secure sign-in via Supabase Auth · No judgment · Your data stays yours")

    with right:
        st.markdown(
            f"""
            <div class="sahay-accent-card" style="height:100%;display:flex;
                 flex-direction:column;justify-content:center;text-align:center;padding:48px 24px;">
                {sahay_icon_html(56)}
                <p style="font-size:20px;font-weight:700;margin:14px 0 4px 0;">Meet Sahay</p>
                <p class="sahay-card-caption">A calm, supportive AI wellness companion —
                not a therapist, doctor, or diagnosis tool.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _auth_forms() -> None:
    with st.container(border=True):
        _google_button()
        st.markdown("<div style='text-align:center;color:#9CA3AF;font-size:12px;margin:10px 0;'>or</div>", unsafe_allow_html=True)

        tab_login, tab_signup, tab_reset = st.tabs(["Log In", "Sign Up", "Forgot Password"])

        with tab_login:
            _login_form()

        with tab_signup:
            _signup_form()

        with tab_reset:
            _reset_form()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Continue in Demo Mode →", key="landing_demo_btn"):
            st.session_state["sahay_view"] = "app"
            st.session_state["sahay_demo_mode"] = True
            st.rerun()
        st.caption("No account needed — a preview with sample data only. Nothing you do in Demo Mode is saved.")


def _google_button() -> None:
    if not (SUPABASE_USER_CONFIG.is_configured and GOOGLE_OAUTH_CONFIG.is_configured):
        if st.button("🔵  Continue with Google", key="landing_google_btn", use_container_width=True):
            st.info("Google Sign-In will be available once Supabase and Google OAuth are configured. See PHASE2_IMPLEMENTATION_REPORT.md for setup steps.")
        return

    from backend import auth
    try:
        url = auth.get_google_sign_in_url()
        st.link_button("🔵  Continue with Google", url, use_container_width=True)
        st.caption("Google Sign-In is configured but has not been live-tested in this environment (no network access). Please verify it end-to-end yourself.")
    except auth.AuthError as exc:
        st.button("🔵  Continue with Google", key="landing_google_btn_err", use_container_width=True, disabled=True)
        st.caption(str(exc))


def _login_form() -> None:
    with st.form("login_form", border=False):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")
    if submitted:
        if not email or not password:
            st.warning("Please enter both your email and password.")
            return
        from backend import auth
        try:
            auth.sign_in_with_password(email, password)
            st.session_state["sahay_view"] = "app"
            st.session_state["sahay_demo_mode"] = False
            st.rerun()
        except auth.AuthError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 - Supabase not configured, etc.
            st.error("Sign-in isn't available right now. Please try again later.")
            st.caption(f"Technical detail (dev preview only): {exc}")


def _signup_form() -> None:
    with st.form("signup_form", border=False):
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password", help="At least 8 characters.")
        confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
        submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
    if submitted:
        if not email or not password:
            st.warning("Please enter an email and password.")
            return
        if password != confirm:
            st.warning("Passwords don't match.")
            return
        from backend import auth
        try:
            auth.sign_up(email, password)
            st.success("Account created. Check your email if verification is required, then log in.")
        except auth.AuthError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error("Sign-up isn't available right now. Please try again later.")
            st.caption(f"Technical detail (dev preview only): {exc}")


def _reset_form() -> None:
    with st.form("reset_form", border=False):
        email = st.text_input("Email", key="reset_email")
        submitted = st.form_submit_button("Send Reset Link", use_container_width=True)
    if submitted:
        if not email:
            st.warning("Please enter your email.")
            return
        from backend import auth
        try:
            auth.reset_password_for_email(email)
            st.success("If an account exists for that email, a reset link is on its way.")
        except Exception as exc:  # noqa: BLE001
            st.error("Couldn't send a reset link right now. Please try again later.")
            st.caption(f"Technical detail (dev preview only): {exc}")


def _feature_grid() -> None:
    st.markdown("#### What Sahay can help with")
    cols = st.columns(4)
    for i, (icon, title, desc) in enumerate(FEATURES):
        with cols[i]:
            st.markdown(
                f"""
                <div class="sahay-card" style="min-height:150px;">
                    <div style="font-size:24px;margin-bottom:8px;">{icon}</div>
                    <div style="font-weight:700;margin-bottom:4px;">{title}</div>
                    <div class="sahay-card-caption">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _safety_notice() -> None:
    st.markdown(
        f"""
        <div class="sahay-card" style="border-left:4px solid {COLORS['soft_teal']};">
            <div style="font-weight:700;margin-bottom:4px;">🔒 Safety &amp; privacy first</div>
            <div class="sahay-card-caption">
                Sahay is AI-powered student wellness support and guidance — it does not
                diagnose, prescribe, or replace a doctor, therapist, or counselor. If
                you're ever in crisis, the Human Help section connects you to real
                support. Your account data is private to you, protected by
                database-level access rules — not just app-level checks.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _footer() -> None:
    st.markdown(
        "<div style='text-align:center;color:#9CA3AF;font-size:12px;padding:18px 0 6px 0;'>"
        "Sahay AI · Student wellness companion · Edunet Foundation × IBM SkillsBuild internship project"
        "</div>",
        unsafe_allow_html=True,
    )
