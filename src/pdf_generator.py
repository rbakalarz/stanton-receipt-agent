"""
PDF Generator
=============
Converts a receipt email to a clean PDF using wkhtmltopdf.
Falls back to a plain-text summary PDF if HTML is not available.
"""

import os
import re
import tempfile
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

WKHTMLTOPDF = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")
WKHTMLTOPDF_ARGS = [
    "--quiet",
    "--page-size", "A4",
    "--margin-top", "10mm",
    "--margin-bottom", "10mm",
    "--margin-left", "10mm",
    "--margin-right", "10mm",
    "--encoding", "UTF-8",
    "--disable-javascript",
    "--no-images",          # faster, no external image fetches
]


def generate_receipt_pdf(message: dict) -> str:
    """
    Convert email message to PDF.
    Returns path to temp PDF file (caller is responsible for cleanup).
    """
    html = message.get("html_body") or _text_to_html(message)

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(html)
        html_path = f.name

    pdf_path = html_path.replace(".html", ".pdf")

    try:
        subprocess.run(
            [WKHTMLTOPDF] + WKHTMLTOPDF_ARGS + [html_path, pdf_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
        log.info(f"Generated PDF: {pdf_path}")
        return pdf_path

    except subprocess.CalledProcessError as e:
        log.error(f"wkhtmltopdf failed: {e.stderr.decode()}")
        # Fallback: plain summary
        return _generate_summary_pdf(message)

    finally:
        os.unlink(html_path)


def _text_to_html(message: dict) -> str:
    """Wrap plain text body in minimal HTML for wkhtmltopdf."""
    body = message.get("body", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body_html = body.replace("\n", "<br>\n")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; color: #333; padding: 20px; }}
  .header {{ color: #666; font-size: 11px; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 16px; }}
  .subject {{ font-size: 18px; font-weight: bold; color: #111; margin-bottom: 8px; }}
</style>
</head>
<body>
  <div class="header">
    <b>From:</b> {message.get('from', '')}<br>
    <b>Date:</b> {message.get('date', '')}<br>
    <b>To:</b> r@stanton.co
  </div>
  <div class="subject">{message.get('subject', 'Receipt')}</div>
  <div class="body">{body_html}</div>
</body>
</html>"""


def _generate_summary_pdf(message: dict) -> str:
    """Last resort: generate a basic summary PDF from message metadata."""
    html = _text_to_html(message)
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(html)
        html_path = f.name

    pdf_path = html_path.replace(".html", ".pdf")
    subprocess.run(
        [WKHTMLTOPDF] + WKHTMLTOPDF_ARGS + [html_path, pdf_path],
        check=True, timeout=30
    )
    os.unlink(html_path)
    return pdf_path
