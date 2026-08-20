"""
tests/test_pdf_export_mock.py
--------------------------------
MOCK VERIFICATION ONLY — fpdf2 is NOT installed in this environment and
there is no network access to install it (confirmed: `pip install
fpdf2` fails with "No matching distribution found", same constraint
documented in every prior phase's `pip install streamlit`/`supabase`
attempts).

Part 1 (always runs): confirms the TRUE no-library state in THIS real
environment produces a friendly PdfExportError, not a crash or a raw
traceback — this is real, not mocked.

Part 2 (runs only if a fake `fpdf` stub is present on PYTHONPATH):
verifies exports/pdf.py's CONTROL FLOW — the right content is passed to
the FPDF API calls — using a hand-written stub that records text instead
of rendering real PDF bytes. This does NOT verify the output is a valid,
renderable PDF; that requires the real fpdf2 library, unavailable here.

Run with the fake fpdf stub for full coverage:
    PYTHONPATH=/path/to/fpdf_stub:/path/to/streamlit_stub python3 tests/test_pdf_export_mock.py
Run without it for Part 1 only (still meaningful — confirms graceful
real-world degradation):
    PYTHONPATH=/path/to/streamlit_stub python3 tests/test_pdf_export_mock.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures: list[str] = []
total_checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def run() -> int:
    from exports._shared import ReportData
    from exports.pdf import build_pdf_report, PdfExportError

    try:
        import fpdf
        is_fake_stub = getattr(fpdf, "__doc__", "") and "stand-in" in fpdf.__doc__
        fpdf_present = True
    except ImportError:
        fpdf_present = False
        is_fake_stub = False

    empty_data = ReportData(generated_at="x", period_days=7, period_start="a", period_end="b", display_name=None, has_any_data=False)

    # ---- Part 1: real behavior when no fpdf module (real or fake) is present ----
    if not fpdf_present:
        check("fpdf2 is genuinely NOT installed in this environment (real constraint, not simulated)", True)
        try:
            build_pdf_report(empty_data)
            check("build_pdf_report raises a friendly error when fpdf2 is genuinely unavailable", False)
        except PdfExportError as exc:
            check("build_pdf_report raises a friendly error when fpdf2 is genuinely unavailable", True)
            check("Friendly error doesn't leak a raw traceback/ImportError string",
                  "ModuleNotFoundError" not in str(exc) and "Traceback" not in str(exc))
        print()
        print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed (Part 1 only — no fpdf stub on PYTHONPATH)")
        return 1 if failures else 0

    if not is_fake_stub:
        print("A real (or unrecognized) fpdf module is present — this test file expects either "
              "nothing importable, or this project's documented fake stub. Skipping.")
        return 0

    # ---- Part 2: control-flow verification against the fake fpdf stub ----
    data = ReportData(
        generated_at="18 August 2026, 12:00 UTC", period_days=30,
        period_start="19 July 2026", period_end="18 August 2026",
        display_name="Alex", has_any_data=True,
        conversations_summary=[{"title": "Exam stress", "date": "2026-08-10", "message_count": 6}],
        mood_events=[{"date": "2026-08-10 14:30", "mood": "Stressed", "emoji": "😣", "sentiment": "negative",
                      "stress": 4, "energy": 2, "sleep": 3, "source": "Check-in", "note": "Big exam"}],
        mood_distribution={"Stressed": 1}, stress_avg=4.0, energy_avg=2.0, sleep_avg=3.0,
        activities_completed=2,
    )

    pdf_bytes = build_pdf_report(data)
    check("build_pdf_report (fake fpdf stub) returns bytes without raising", isinstance(pdf_bytes, (bytes, bytearray)))
    check("Returned bytes are the FAKE stub placeholder, honestly not claimed as a real PDF",
          bytes(pdf_bytes) == b"%FAKE-PDF-STUB-NOT-A-REAL-PDF%")

    # Directly instrument the section-rendering functions to inspect actual content
    from fpdf import FPDF as StubFPDF
    from exports.pdf import _header, _summary_section, _mood_section, _conversations_section, _disclaimer_section

    instance = StubFPDF()
    _header(instance, data)
    _summary_section(instance, data)
    _mood_section(instance, data)
    _conversations_section(instance, data)
    _disclaimer_section(instance, data)
    recorded = " ".join(instance.recorded_text)

    check("PDF content includes 'Sahay AI' branding", "Sahay AI" in recorded)
    check("PDF content includes the report title", "Wellness Reflection Report" in recorded)
    check("PDF content includes the reporting period", "19 July 2026" in recorded and "30 days" in recorded)
    check("PDF content includes mood data", "Stressed" in recorded)
    check("PDF content includes stress/energy/sleep scale values",
          "Stress 4/5" in recorded and "Energy 2/5" in recorded and "Sleep 3/5" in recorded)
    check("PDF content includes the disclaimer text", "not a medical assessment" in recorded.lower())
    check("PDF content includes conversation title + message-count summary (not full transcript)",
          "Exam stress" in recorded and "6 messages" in recorded)
    check("PDF content contains no 'OPENROUTER'/'SUPABASE' substring", "OPENROUTER" not in recorded.upper() and "SUPABASE" not in recorded.upper())

    instance_empty = StubFPDF()
    _header(instance_empty, empty_data)
    _summary_section(instance_empty, empty_data)
    recorded_empty = " ".join(instance_empty.recorded_text)
    check("Empty-data PDF still renders the header without crashing", "Sahay AI" in recorded_empty)

    print()
    print(f"TOTAL: {total_checks - len(failures)}/{total_checks} passed")
    print("(Part 1: real behavior, no library. Part 2: MOCK control-flow via fake stub — NOT real PDF rendering.)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
