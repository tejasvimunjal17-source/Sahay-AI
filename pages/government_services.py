"""pages/government_services.py — PHASE 4: polished rendering of
content/government_services.py's five-section structure (what/who/how/
official link/note). No URLs, phone numbers, eligibility rules, or
procedures are invented anywhere in this file — every fact-shaped claim
comes from the content module, which you edit directly."""

from __future__ import annotations

import streamlit as st

from components.cards import safety_note
from content.government_services import GOVERNMENT_SERVICES


def render() -> None:
    st.markdown("### 🇮🇳 Government & Student Support Services")
    safety_note(
        "This section provides general guidance only. Sahay AI is not an "
        "official representative of the Government of India and cannot "
        "issue any ID, card, certificate, or prescription. Always verify "
        "current details on the official portal before acting — eligibility, "
        "documents, and procedures may change."
    )

    for service in GOVERNMENT_SERVICES:
        with st.container(border=True):
            st.markdown(f"#### {service['icon']} {service['name']}")

            st.markdown("**What it is**")
            st.write(service["what_it_is"])

            st.markdown("**Who it may be for**")
            st.write(service["intended_for"])

            st.markdown("**How to access it**")
            st.write(service.get("how_to_access", "See the official portal for current steps."))

            st.markdown("**Official website**")
            if service.get("official_url"):
                st.link_button("Open official portal", service["official_url"])
            else:
                st.caption("⚠️ Official portal link pending verification — not yet added.")

            if service.get("important_note"):
                st.caption(f"ℹ️ {service['important_note']}")
