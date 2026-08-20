"""
content/crisis_resources.py
---------------------------
Placeholder structure for verified crisis/emergency resources.

DELIBERATELY EMPTY IN PHASE 1. Per the master spec's safety rules, the
application must never invent hotline numbers or emergency contact
details. This module defines the *shape* pages/human_help.py will render
once you (the developer) supply verified India-specific resources —
nothing here is fabricated or filled in with placeholder-looking-real data.

Expected shape once populated:

    CRISIS_RESOURCES = [
        {
            "name": "<verified organization name>",
            "description": "<what they do>",
            "contact": "<verified phone/text/URL>",
            "availability": "<verified hours, e.g. '24/7' or 'Mon-Fri 9am-6pm'>",
            "region": "<e.g. 'India' or a specific state>",
        },
        ...
    ]
"""

from __future__ import annotations

CRISIS_RESOURCES: list[dict] = []  # populate only with verified sources
