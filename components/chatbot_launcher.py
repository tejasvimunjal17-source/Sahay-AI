"""
components/chatbot_launcher.py
-------------------------------
Floating chatbot launcher + expandable panel.

Composition pattern (inject once near the top of the app, before the
page router, so it persists across every authenticated page) is adapted
from LearnMate AI's render_chatbot_widget() — see /PHASE0_AUDIT.md
section B.

PHASE 3 UPDATE: send_message() now calls the real
chatbot/response_generator.py pipeline (safety screening -> mood
analysis -> OpenRouter -> output screening) instead of a fixed
placeholder string. Still no conversation persistence — history lives
only in st.session_state, exactly as it did in Phase 1/2 (see
PHASE3_PRE_IMPLEMENTATION_AUDIT.md §6 for why that's the right scope for
this phase). Demo Mode still works with zero Supabase/OpenRouter calls —
generate_response() itself degrades to a friendly "not connected yet"
message whenever OPENROUTER_CONFIG isn't configured, so this component
never needs to know or care whether the user is authenticated or in Demo
Mode; it behaves identically either way.
"""

from __future__ import annotations

import streamlit as st

from components.theme import sahay_icon_html

# Shared with pages/companion.py so both surfaces offer the same starting
# points. Clicking a chip sends it through the exact same
# generate_response() pipeline as typed input — no shortcut around
# safety/mood/OpenRouter.
SUGGESTION_CHIPS = [
    "Help me relax",
    "I'm stressed about exams",
    "I feel overwhelmed",
    "I need motivation",
]


def send_message(history_key: str, text: str) -> None:
    """Append a user message + Sahay's real generated reply to the given
    session_state history list. Shared by the launcher panel, the
    full-page companion, and suggestion chips on both.

    Uses st.session_state.get("sahay_language", "English") so a language
    choice made on the full-page companion (see pages/companion.py)
    applies to the floating launcher too, without this module needing
    its own language selector — kept minimal per the "don't redesign the
    UI unnecessarily" instruction.
    """
    from chatbot.response_generator import generate_response  # local import: keeps this UI
    # module free of a hard import-time dependency on the AI engine, matching how
    # backend.auth is only imported where actually needed elsewhere in this codebase.

    st.session_state[history_key].append({"role": "user", "content": text})
    language = st.session_state.get("sahay_language", "English")
    history_before = st.session_state[history_key][:-1]  # exclude the message just added
    result = generate_response(text, chat_history=history_before, language=language)
    st.session_state[history_key].append({
        "role": "assistant",
        "content": result["reply"],
        "mood": result.get("mood"),
        "safety_action": result.get("safety_action"),
        "suggestion": result.get("suggestion"),
    })


def render_suggestion_card(history_key: str, key_prefix: str) -> None:
    """PHASE 5: renders a dismissible 'Try this now' card for the most
    recent assistant turn only — never for every message (the mapping in
    chatbot/mood_analyzer.MOOD_SUGGESTIONS already naturally excludes
    Happy/Calm/Neutral, and this function additionally only ever looks
    at the LAST turn, so even a run of Stressed messages shows the card
    once per new reply, not stacked). Never shown for a crisis/blocked
    turn — chatbot/response_generator.py guarantees `suggestion` is None
    on those paths, so there's nothing to check here beyond "does the
    last turn have one."

    Dismissal is tracked per message index in
    st.session_state[f"{key_prefix}_dismissed_suggestions"], a set —
    once dismissed, that specific turn's card won't reappear, but a
    *new* reply's card (a different index) can still show.
    """
    history = st.session_state.get(history_key, [])
    if not history or history[-1]["role"] != "assistant":
        return
    suggestion = history[-1].get("suggestion")
    if not suggestion:
        return

    dismissed_key = f"{key_prefix}_dismissed_suggestions"
    st.session_state.setdefault(dismissed_key, set())
    turn_index = len(history) - 1
    if turn_index in st.session_state[dismissed_key]:
        return

    from chatbot.mood_analyzer import MOOD_EMOJI
    mood = history[-1].get("mood") or {}
    emoji = MOOD_EMOJI.get(mood.get("mood"), "💡")

    with st.container(border=True):
        st.markdown(f"{emoji} **Try this now**")
        st.write(suggestion["text"])
        c1, c2 = st.columns([1, 1])
        with c1:
            if suggestion.get("activity_key") and st.button(
                "Open Relaxation", key=f"{key_prefix}_suggestion_open_{turn_index}", use_container_width=True
            ):
                st.session_state["sahay_page"] = "relaxation"
                st.rerun()
        with c2:
            if st.button("Dismiss", key=f"{key_prefix}_suggestion_dismiss_{turn_index}", use_container_width=True):
                st.session_state[dismissed_key].add(turn_index)
                st.rerun()


def render_suggestion_chips(history_key: str, key_prefix: str) -> None:
    cols = st.columns(len(SUGGESTION_CHIPS))
    for i, chip in enumerate(SUGGESTION_CHIPS):
        with cols[i]:
            if st.button(chip, key=f"{key_prefix}_chip_{i}", use_container_width=True):
                send_message(history_key, chip)
                st.rerun()


def render_chatbot_launcher() -> None:
    st.session_state.setdefault("sahay_chat_open", False)
    st.session_state.setdefault("sahay_chat_history", [])

    # Launcher pill — bottom-right, persistent. Streamlit can't attach a
    # real onClick to arbitrary HTML, so the pill is rendered for visual
    # placement/branding review and paired with a normal Streamlit button
    # directly beneath it that actually toggles the panel.
    st.markdown(
        f"""
        <div class="sahay-launcher">
            {sahay_icon_html(22)}
            <div>
                <div class="sahay-launcher-title">Sahay</div>
                <div class="sahay-launcher-subtitle">Your wellness companion</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, launcher_col = st.columns([6, 1])
    with launcher_col:
        toggle_label = "Close Sahay" if st.session_state["sahay_chat_open"] else "Open Sahay"
        if st.button(toggle_label, key="sahay_launcher_toggle"):
            st.session_state["sahay_chat_open"] = not st.session_state["sahay_chat_open"]
            st.rerun()

    if st.session_state["sahay_chat_open"]:
        _render_panel()


def _render_panel() -> None:
    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;'>"
            f"{sahay_icon_html(24)}"
            f"<span style='font-weight:700;'>Sahay</span>"
            f"<span style='color:#6B7280;font-size:12px;'>· AI wellness companion, not a medical professional</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        for turn in st.session_state["sahay_chat_history"]:
            with st.chat_message(turn["role"]):
                st.write(turn["content"])

        render_suggestion_card("sahay_chat_history", key_prefix="launcher")

        if not st.session_state["sahay_chat_history"]:
            render_suggestion_chips("sahay_chat_history", key_prefix="launcher")

        user_msg = st.chat_input("Message Sahay")
        if user_msg:
            send_message("sahay_chat_history", user_msg)
            st.rerun()

        if st.session_state["sahay_chat_history"]:
            if st.button("Clear conversation", key="sahay_clear_chat"):
                st.session_state["sahay_chat_history"] = []
                st.rerun()
