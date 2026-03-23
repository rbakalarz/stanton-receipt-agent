"""
PDF Generator - uses fpdf2 (pure Python, no system binary needed)
"""
import os
import tempfile
import logging
from fpdf import FPDF

log = logging.getLogger(__name__)


def generate_receipt_pdf(message: dict) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_font("Helvetica", "B", 16)
    subject = message.get("subject", "Receipt")[:80]
    pdf.cell(0, 10, subject, ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"From: {message.get('from', '')[:80]}", ln=True)
    pdf.cell(0, 6, f"Date: {message.get('date', '')[:80]}", ln=True)
    pdf.cell(0, 6, "To: r@stanton.co", ln=True)
    pdf.ln(4)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    body = message.get("body", "").strip() or "(No plain text body available)"

    for line in body.splitlines():
        if pdf.get_y() > 270:
            pdf.add_page()
        safe_line = line.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_line[:200])

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    pdf.output(tmp.name)
    log.info(f"Generated PDF: {tmp.name}")
    return tmp.name
