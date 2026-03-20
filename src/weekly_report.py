"""
Weekly Report
=============
Sends a Monday morning digest to accounting summarising:
  - Receipts matched and filed this week
  - Charges still missing a receipt (needs manual action)
"""

import os
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger(__name__)

REPORT_TO   = os.environ.get("REPORT_EMAIL_TO", "contabilidad@stanton.co")
REPORT_FROM = os.environ.get("REPORT_EMAIL_FROM", "r@stanton.co")
SMTP_HOST   = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER   = os.environ.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")


def send_weekly_report(pending_missing: list[dict], this_run: dict):
    """Send weekly HTML digest email."""
    matched  = this_run.get("matched", [])
    missing  = this_run.get("missing", [])
    week_str = datetime.now().strftime("%B %d, %Y")

    subject = f"Stanton – Reporte de Recibos | Semana del {week_str}"
    html = _build_html(matched, missing, pending_missing, week_str)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = REPORT_FROM
    msg["To"]      = REPORT_TO
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(REPORT_FROM, [REPORT_TO], msg.as_string())
        log.info(f"Weekly report sent to {REPORT_TO}")
    except Exception as e:
        log.error(f"Failed to send weekly report: {e}")


def _build_html(matched, missing, pending_missing, week_str) -> str:
    def cop(amount):
        return f"COP ${amount:,.0f}"

    # Matched this run
    matched_rows = "".join(
        f"<tr><td>{r['vendor']}</td><td>{r['txn_date']}</td>"
        f"<td>{cop(r['amount_cop'])}</td>"
        f"<td><a href='{r.get('drive_url','#')}'>Ver PDF</a></td></tr>"
        for r in matched
    ) or "<tr><td colspan='4' style='color:#999'>Ninguno esta semana</td></tr>"

    # Missing this run
    missing_rows = "".join(
        f"<tr style='background:#fff3cd'>"
        f"<td><b>{r['vendor']}</b></td><td>{r['txn_date']}</td>"
        f"<td>{cop(r['amount_cop'])}</td><td>⚠️ Pendiente</td></tr>"
        for r in missing
    ) or ""

    # All pending missing (last 30 days)
    pending_rows = "".join(
        f"<tr><td>{r['vendor']}</td><td>{r['txn_date']}</td>"
        f"<td>{cop(r['amount_cop'])}</td></tr>"
        for r in pending_missing
    ) or "<tr><td colspan='3' style='color:#999'>Sin pendientes 🎉</td></tr>"

    total_matched = len(matched)
    total_missing = len(pending_missing)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; color: #333; max-width: 700px; margin: 0 auto; }}
  h1 {{ background: #1a1a2e; color: white; padding: 16px 20px; font-size: 18px; }}
  h2 {{ font-size: 14px; color: #555; border-bottom: 2px solid #eee; padding-bottom: 6px; margin-top: 24px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  th {{ background: #f5f5f5; text-align: left; padding: 8px; font-size: 12px; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
  .summary {{ display: flex; gap: 20px; margin: 16px 0; }}
  .card {{ flex: 1; padding: 12px 16px; border-radius: 6px; }}
  .card.green {{ background: #d4edda; color: #155724; }}
  .card.yellow {{ background: #fff3cd; color: #856404; }}
  .card-number {{ font-size: 28px; font-weight: bold; }}
  .footer {{ font-size: 11px; color: #999; margin-top: 24px; padding-top: 12px; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<h1>📋 Stanton — Reporte de Recibos<br><small style="font-size:13px; font-weight:normal">Semana del {week_str}</small></h1>

<div class="summary">
  <div class="card green">
    <div class="card-number">{total_matched}</div>
    <div>Recibos archivados esta semana</div>
  </div>
  <div class="card yellow">
    <div class="card-number">{total_missing}</div>
    <div>Cargos sin recibo (últimos 30 días)</div>
  </div>
</div>

<h2>✅ Archivados esta semana</h2>
<table>
  <tr><th>Proveedor</th><th>Fecha</th><th>Monto</th><th>Archivo</th></tr>
  {matched_rows}
  {missing_rows}
</table>

<h2>⚠️ Pendientes sin recibo (últimos 30 días)</h2>
<p style="font-size:12px; color:#888">Estos cargos aparecieron en la tarjeta Visa 4183 pero no se encontró un recibo digital correspondiente. Por favor subir el recibo manualmente a la carpeta del mes en Google Drive.</p>
<table>
  <tr><th>Proveedor</th><th>Fecha</th><th>Monto</th></tr>
  {pending_rows}
</table>

<div class="footer">
  Generado automáticamente por el Agente de Recibos Stanton · Visa Corporativa **4183 · GNB Sudameris<br>
  Los recibos están archivados en Google Drive: Recibos Stanton / YYYY-MM /
</div>
</body>
</html>"""
