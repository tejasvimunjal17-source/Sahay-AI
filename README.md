# Sahay AI

**AI-powered student wellness support and guidance.** Sahay AI is not a
therapist, psychologist, psychiatrist, or doctor, and does not replace
professional mental-health care.

Built for the Edunet Foundation × IBM SkillsBuild "AI for Non-Technical
Students" internship (July 2026 batch), problem statement: *Mental Health
Companion Chatbot*.

## Status: Phase 1 complete (scaffold only)

This repository currently contains **project structure, navigation, theme,
and a static UI shell only**. There is no live authentication, database, or
AI integration yet — see `PHASE1_SUMMARY.md` for the full, evidence-based
account of what was built and verified, and `PHASE0_AUDIT.md` for the
architecture audit this scaffold follows.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

No `.env` or Streamlit secrets are required to run Phase 1 — every page
loads with placeholder content.

## Project structure

See `PHASE0_AUDIT.md` §G for the full proposed structure and `PHASE1_SUMMARY.md`
for exactly which of those files exist today vs. are Phase 2+ placeholders.

## Relationship to the LearnMate AI reference project

Sahay AI is an independent project. LearnMate AI (uploaded separately) was
used only as an **architecture reference** — see `PHASE0_AUDIT.md` for what
was adapted and what was deliberately not carried over (most notably,
LearnMate's passwordless "auth" and its service-role-key-for-everything
data access pattern, both rejected on security grounds for this project).
The LearnMate project files were never modified.
