"""
exports/pdf.py
-----------------
PHASE 6 IMPLEMENTATION.

Renders a exports._shared.ReportData into a PDF using fpdf2. All content
decisions (what data, bounded window, disclaimer wording) live in
exports/_shared.py — this module only translates that already-shaped,
already-safe content into fpdf2 calls. fpdf2 is imported lazily inside
the function, matching this codebase's established pattern (see
backend/supabase_client.py, backend/openrouter_client.py) so this module
stays importable even in an environment without fpdf2 installed.

NOT LIVE-TESTED: fpdf2 could not be installed in this sandbox (no
network access — same constraint documented in every prior phase's
`pip install streamlit`/`supabase` attempts). See
PHASE6_IMPLEMENTATION_REPORT.md for exactly what was and wasn't verified.
"""

from __future__ import annotations

from exports._shared import ReportData


def build_pdf_report(data: ReportData) -> bytes:
    """Returns PDF bytes for the given (already-bounded, already-shaped)
    report data. Raises exports.pdf.PdfExportError with a friendly
    message on any failure — never raises a raw fpdf2 exception to the
    caller."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise PdfExportError(
            "PDF export isn't available right now — the required library isn't installed."
        ) from exc

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        _header(pdf, data)
        _summary_section(pdf, data)

        if not data.has_any_data:
            pdf.ln(4)
            pdf.set_font("Helvetica", "I", 11)
            pdf.multi_cell(0, 7, "No wellness activity was recorded in this period.")
        else:
            _mood_section(pdf, data)
            _conversations_section(pdf, data)
            _activity_section(pdf, data)

        _disclaimer_section(pdf, data)

        output = pdf.output()
        return bytes(output)
    except PdfExportError:
        raise
    except Exception as exc:  # noqa: BLE001 - any fpdf2-internal failure becomes a friendly error
        raise PdfExportError("Couldn't generate the PDF report right now. Please try again.") from exc


class PdfExportError(RuntimeError):
    """User-safe error message — never contains raw library internals."""


def _header(pdf, data: ReportData) -> None:
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Sahay AI", ln=True)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Wellness Reflection Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Generated {data.generated_at}", ln=True)
    if data.display_name:
        pdf.cell(0, 6, f"For: {data.display_name}", ln=True)
    pdf.cell(0, 6, f"Period: {data.period_start} - {data.period_end} ({data.period_days} days)", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


def _summary_section(pdf, data: ReportData) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    lines = [
        f"Conversations in this period: {len(data.conversations_summary)}",
        f"Mood entries recorded: {len(data.mood_events)}",
        f"Relaxation activities completed: {data.activities_completed}",
    ]
    if data.stress_avg is not None:
        lines.append(f"Average recorded stress: {data.stress_avg}/5")
    if data.energy_avg is not None:
        lines.append(f"Average recorded energy: {data.energy_avg}/5")
    if data.sleep_avg is not None:
        lines.append(f"Average recorded sleep quality: {data.sleep_avg}/5")
    for line in lines:
        pdf.cell(0, 6, line, ln=True)
    pdf.ln(2)


def _mood_section(pdf, data: ReportData) -> None:
    if not data.mood_events:
        return
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Mood History", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for m in data.mood_events:
        scales = []
        if m.get("stress") is not None:
            scales.append(f"Stress {m['stress']}/5")
        if m.get("energy") is not None:
            scales.append(f"Energy {m['energy']}/5")
        if m.get("sleep") is not None:
            scales.append(f"Sleep {m['sleep']}/5")
        scale_text = (" - " + ", ".join(scales)) if scales else ""
        line = f"{m['date']}  {m.get('mood', 'Neutral')} ({m.get('source', '')}){scale_text}"
        pdf.multi_cell(0, 6, line)
        if m.get("note"):
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 6, f"   Note: {m['note']}")
            pdf.set_font("Helvetica", "", 9)
    pdf.ln(2)


def _conversations_section(pdf, data: ReportData) -> None:
    if not data.conversations_summary:
        return
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Conversations", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 5, "Titles and message counts only — full conversation content is not included in this report.")
    pdf.set_text_color(0, 0, 0)
    for c in data.conversations_summary:
        pdf.cell(0, 6, f"{c['date']}  {c['title']} ({c['message_count']} messages)", ln=True)
    pdf.ln(2)


def _activity_section(pdf, data: ReportData) -> None:
    if data.mood_distribution:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Approximate Mood Distribution", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for mood, count in sorted(data.mood_distribution.items(), key=lambda kv: -kv[1]):
            pdf.cell(0, 6, f"{mood}: {count}", ln=True)
        pdf.ln(2)


def _disclaimer_section(pdf, data: ReportData) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 5, data.disclaimer)
    pdf.set_text_color(0, 0, 0)
