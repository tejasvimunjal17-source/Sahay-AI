"""
content/government_services.py
------------------------------
Static, editorial reference data for the Government & Student Support
Services page. This is a maintainable config layer, not a database table,
per the approved Phase 0 decision — a human (you) edits this file directly
rather than the AI inventing or updating it at runtime.

IMPORTANT (per the master spec, §"Government Services" addendum):
- No URLs, phone numbers, eligibility rules, or procedures are invented.
- `official_url` is intentionally left as None until you have verified the
  current official portal link yourself; pages/government_services.py
  renders a "pending verification" notice for any entry missing one.
- This file only describes WHAT each service is and WHO it is generally
  for, in general terms that don't need frequent verification. Anything
  that could go stale (steps, documents, phone numbers) is deliberately
  left out until you provide a verified source.
"""

from __future__ import annotations

GOVERNMENT_SERVICES: list[dict] = [
    {
        "key": "esanjeevani",
        "icon": "🏥",
        "name": "eSanjeevani",
        "what_it_is": "India's government telemedicine service, allowing patients to consult doctors remotely.",
        "intended_for": "Students seeking general medical consultation without an in-person hospital visit.",
        "how_to_access": "Visit the official eSanjeevani portal and follow its current registration and consultation steps.",
        "important_note": "Availability, doctor specialties, and steps can change — always check the official portal for current details.",
        "official_url": None,  # TODO: add verified official portal URL before launch
    },
    {
        "key": "abha",
        "icon": "🩺",
        "name": "ABHA ID",
        "what_it_is": "Ayushman Bharat Health Account — a digital health ID that links an individual's health records.",
        "intended_for": "Any resident wanting a unified digital health record, including students.",
        "how_to_access": "Create an ABHA ID through the official ABHA portal or app using the current verified process.",
        "important_note": "Sahay AI cannot create or issue an ABHA ID itself — this is guidance only.",
        "official_url": None,  # TODO: add verified official portal URL before launch
    },
    {
        "key": "ayushman_bharat",
        "icon": "💳",
        "name": "Ayushman Bharat / Ayushman Card",
        "what_it_is": "A government health insurance scheme providing coverage for eligible families.",
        "intended_for": "Eligibility varies by household/state criteria — verify on the official portal.",
        "how_to_access": "Check eligibility and application steps on the official Ayushman Bharat / PM-JAY portal.",
        "important_note": "Eligibility, benefits, and documents required can change — Sahay AI does not determine eligibility.",
        "official_url": None,  # TODO: add verified official portal URL before launch
    },
    {
        "key": "govt_hospitals",
        "icon": "🏥",
        "name": "Government Hospitals & Health Centres",
        "what_it_is": "Public healthcare facilities offering low-cost or free treatment.",
        "intended_for": "Students needing in-person care, especially where cost is a barrier.",
        "how_to_access": "Use an official government health-facility locator, or ask your campus health center for the nearest option.",
        "important_note": "Services and availability vary by location.",
        "official_url": None,  # TODO: add verified locator/official portal URL before launch
    },
    {
        "key": "emergency_crisis",
        "icon": "📱",
        "name": "Emergency & Crisis Support",
        "what_it_is": "Configurable emergency contact guidance — see content/crisis_resources.py.",
        "intended_for": "Anyone in immediate danger or crisis.",
        "how_to_access": "See the Human Help section for currently available verified resources.",
        "important_note": "If you are in immediate danger, contact local emergency services right away.",
        "official_url": None,
    },
    {
        "key": "mental_health_support",
        "icon": "🧠",
        "name": "Mental Health Support Resources",
        "what_it_is": "Verified professional and public mental-health resources.",
        "intended_for": "Students wanting professional support beyond the AI companion.",
        "how_to_access": "See the Human Help section for currently available verified resources.",
        "important_note": "Sahay AI is not a substitute for professional mental-health care.",
        "official_url": None,  # TODO: add verified resource list before launch
    },
]
