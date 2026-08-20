"""
components/theme.py
--------------------
Design tokens + CSS injection for Sahay AI.

Palette follows the master spec's suggested direction (deep blue, soft
teal, lavender, white, dark slate) — distinct from both the LearnMate
reference (purple/teal "#7C5CFF" gradient) and the Fitly UX reference
(green accent on cream). Reserves red/amber strictly for safety-escalation
UI, never for general branding.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
COLORS = {
    "deep_blue": "#2F5D8A",
    "soft_teal": "#3FAFA0",
    "lavender": "#8B85C1",
    "white": "#FFFFFF",
    "dark_slate": "#1E2430",
    "bg_light": "#F6F7FB",
    "bg_dark": "#141821",
    "card_light": "#FFFFFF",
    "card_dark": "#1E2430",
    "text_light": "#1E2430",
    "text_dark": "#EDEEF5",
    "muted_light": "#6B7280",
    "muted_dark": "#9CA3AF",
    "safety_amber": "#B45309",
    "safety_red": "#B3261E",
}

ICON_PATH = Path(__file__).parent.parent / "assets" / "sahay_icon.svg"


def _icon_b64() -> str:
    return base64.b64encode(ICON_PATH.read_bytes()).decode("utf-8")


def sahay_icon_html(size_px: int = 28) -> str:
    """The single, consistent Sahay glyph — heart-in-speech-bubble.

    Use this everywhere the companion needs a visual identity (launcher,
    sidebar wordmark, chat header, avatar, empty/loading states) instead of
    ad-hoc emoji, so the icon stays a single recognizable mark per the
    master spec's branding requirement.
    """
    b64 = _icon_b64()
    return (
        f'<img src="data:image/svg+xml;base64,{b64}" '
        f'width="{size_px}" height="{size_px}" '
        f'style="vertical-align:middle;" alt="Sahay" />'
    )


def inject_css(dark_mode: bool = False) -> None:
    bg = COLORS["bg_dark"] if dark_mode else COLORS["bg_light"]
    card = COLORS["card_dark"] if dark_mode else COLORS["card_light"]
    text = COLORS["text_dark"] if dark_mode else COLORS["text_light"]
    muted = COLORS["muted_dark"] if dark_mode else COLORS["muted_light"]

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}
        h1, h2, h3, .sahay-display {{
            font-family: 'Space Grotesk', sans-serif;
        }}

        .stApp {{
            background-color: {bg};
            color: {text};
        }}

        /* ---- Cards ---- */
        .sahay-card {{
            background: {card};
            border-radius: 18px;
            padding: 22px 24px;
            box-shadow: 0 4px 20px rgba(20, 24, 33, 0.06);
            margin-bottom: 16px;
            border: 1px solid rgba(20, 24, 33, 0.04);
        }}
        .sahay-card-muted-label {{
            font-size: 12px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: {muted};
            margin-bottom: 6px;
        }}
        .sahay-card-metric {{
            font-size: 30px;
            font-weight: 700;
            font-family: 'Space Grotesk', sans-serif;
            margin: 0;
        }}
        .sahay-card-caption {{
            font-size: 13px;
            color: {muted};
            margin-top: 4px;
        }}

        /* ---- Companion accent card (deliberately dark, like the
               reference app's contrast card, to signal "this is Sahay") ---- */
        .sahay-accent-card {{
            background: linear-gradient(135deg, {COLORS['deep_blue']}, {COLORS['soft_teal']});
            color: #FFFFFF;
            border-radius: 18px;
            padding: 22px 24px;
            margin-bottom: 16px;
        }}
        .sahay-accent-card .sahay-card-caption {{
            color: rgba(255,255,255,0.75);
        }}

        /* ---- Safety / disclaimer banner ---- */
        .sahay-safety-note {{
            font-size: 12.5px;
            color: {muted};
            border-left: 3px solid {COLORS['soft_teal']};
            padding: 8px 12px;
            background: rgba(63, 175, 160, 0.08);
            border-radius: 6px;
            margin: 10px 0 18px 0;
        }}

        /* ---- Floating chatbot launcher ---- */
        .sahay-launcher {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999;
            background: {COLORS['dark_slate']};
            color: #FFFFFF;
            border-radius: 999px;
            padding: 12px 20px 12px 14px;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 8px 24px rgba(20,24,33,0.25);
            cursor: pointer;
        }}
        .sahay-launcher-title {{
            font-size: 13.5px;
            font-weight: 600;
            line-height: 1.1;
        }}
        .sahay-launcher-subtitle {{
            font-size: 11px;
            color: rgba(255,255,255,0.65);
            line-height: 1.1;
        }}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {{
            background-color: {card};
        }}
        .sahay-sidebar-group-label {{
            font-size: 11px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {muted};
            margin: 18px 0 4px 8px;
        }}
        .sahay-sidebar-profile {{
            border-top: 1px solid rgba(20,24,33,0.08);
            padding-top: 12px;
            margin-top: 12px;
            font-size: 13px;
        }}

        /* Hide default Streamlit chrome that clashes with the custom shell */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* ---- Responsive adjustments ----
           Streamlit's own layout already stacks st.columns() vertically
           below ~640px viewport width and collapses the sidebar into an
           off-canvas drawer on narrow screens; these rules only tighten
           spacing/sizing on top of that built-in behavior so nothing
           overflows horizontally on tablet/mobile widths. */
        @media (max-width: 768px) {{
            .sahay-card, .sahay-accent-card {{
                padding: 16px 16px;
            }}
            .sahay-launcher {{
                bottom: 14px;
                right: 14px;
                padding: 10px 14px 10px 10px;
            }}
            .sahay-launcher-subtitle {{
                display: none;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
