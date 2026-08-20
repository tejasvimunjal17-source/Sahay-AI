# Tests

No pytest is available in this sandbox (no network to install it), so
these are plain Python scripts using print+exit-code checks:

```bash
python3 tests/test_import_guard.py              # STATIC
python3 tests/test_static_security.py            # STATIC
python3 tests/test_navigation_consistency.py     # STATIC
python3 tests/test_safety_static.py              # STATIC
python3 tests/test_auth_mock.py                  # MOCK (fake Supabase client)
python3 tests/test_openrouter_client_mock.py     # MOCK (fake `requests` module)
python3 tests/test_ai_engine_mock.py             # MOCK (monkeypatched OpenRouter)
python3 tests/test_conversations_mock.py         # MOCK (fake Supabase client)
python3 tests/test_wellness_scales_mock.py       # MOCK (fake Supabase client)
python3 tests/test_exports_mock.py               # MOCK (data shaping) + REAL python-docx execution
python3 tests/test_pdf_export_mock.py            # Part 1 REAL (no-library behavior); Part 2 MOCK (needs fake fpdf stub)

# Requires PYTHONPATH pointed at a streamlit stub, AND SUPABASE_URL/
# SUPABASE_ANON_KEY set (any fake value) so streamlit_app.py's auth gate
# actually calls the mocked backend.auth.get_current_user() instead of
# silently redirecting to the landing page (lesson learned in Phase 4):
SUPABASE_URL=https://fake.supabase.co SUPABASE_ANON_KEY=fake \
    PYTHONPATH=/path/to/streamlit_stub python3 tests/test_ui_interactions_mock.py
SUPABASE_URL=https://fake.supabase.co SUPABASE_ANON_KEY=fake \
    PYTHONPATH=/path/to/streamlit_stub python3 tests/test_phase5_ui_interactions_mock.py
SUPABASE_URL=https://fake.supabase.co SUPABASE_ANON_KEY=fake \
    PYTHONPATH=/path/to/streamlit_stub python3 tests/test_reports_ui_mock.py
```

All exit 0 on full pass. See PHASE2/3/4/5/6_IMPLEMENTATION_REPORT.md for
what remains untested against real Supabase/OpenRouter/fpdf2, and why.

## Phase 6 note: the fake fpdf stub

`exports/pdf.py` uses `fpdf2`, which could not be installed in this
sandbox (no network access — same constraint as `streamlit`/`supabase`
in earlier phases). For deeper-than-static verification of
`exports/pdf.py`'s control flow (does it pass the right content to the
right calls?) without the real library, a hand-written fake `fpdf`
module is used — **not checked into this repository** (it doesn't belong
in the shipped project; it's a test-time-only fixture, same as the
Streamlit stub itself). To exercise `tests/test_pdf_export_mock.py`'s
Part 2 and the PDF portions of `tests/test_reports_ui_mock.py`, create a
file at some path like `/tmp/fpdf_stub/fpdf.py`:

```python
class FPDF:
    def __init__(self, *a, **kw): self.recorded_text = []
    def set_auto_page_break(self, auto=True, margin=0): pass
    def add_page(self): pass
    def set_font(self, family, style="", size=0): pass
    def set_text_color(self, r, g=None, b=None): pass
    def cell(self, w, h=0, txt="", ln=0, **kw):
        t = kw.get("text", txt)
        if t: self.recorded_text.append(t)
    def multi_cell(self, w, h=0, txt="", **kw):
        t = kw.get("text", txt)
        if t: self.recorded_text.append(t)
    def ln(self, h=0): pass
    def output(self, *a, **kw): return bytearray(b"%FAKE-PDF-STUB-NOT-A-REAL-PDF%")
```

Then add its parent directory to `PYTHONPATH` before the streamlit
stub's directory. Without it, `test_pdf_export_mock.py` still runs its
Part 1 (confirms the real, true no-library behavior is a friendly error,
not a crash) and exits 0.

**This stub never produces a real, valid PDF.** Real PDF rendering
(does `fpdf2` actually produce openable PDF bytes with this exact
content?) has never been verified in this environment — see
PHASE6_IMPLEMENTATION_REPORT.md's LIVE section.

## Lessons from earlier phases (still apply)

- `streamlit_app.py`'s auth gate only calls `get_current_user()` when
  `SUPABASE_URL`/`SUPABASE_ANON_KEY` are set — every authenticated-path
  test needs them, even with a mocked auth function.
- When a backend function's signature changes, every test file mocking
  that function needs its mock signature updated too, or a real
  `TypeError` gets silently swallowed by `streamlit_app.py`'s own error
  handler and the test can misleadingly still show "ran clean."
