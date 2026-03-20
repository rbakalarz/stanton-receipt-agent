"""
Stanton Receipt Agent
=====================
Monitors r@stanton.co for Banco GNB Sudameris charge notifications,
matches them to receipt emails, generates PDFs, uploads to Google Drive,
and logs everything to Supabase.

Run on a schedule (e.g. nightly via Railway cron).
"""

import os
import re
import json
import logging
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from gmail_client import GmailClient
from drive_client import DriveClient
from supabase_client import SupabaseClient
from receipt_matcher import ReceiptMatcher
from pdf_generator import generate_receipt_pdf
from weekly_report import send_weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Sudameris notification pattern ──────────────────────────────────────────
# "compra Tarj. Crédito **4183 VENDOR NAME . Por $ 75.565,00 19/03/2026 - 22:32:34"
SUDAMERIS_PATTERN = re.compile(
    r"compra Tarj\. Cr[eé]dito \*\*4183\s+(.+?)\s*\.\s*Por \$\s*([\d\.,]+)\s+(\d{2}/\d{2}/\d{4})\s*-\s*([\d:]+)",
    re.IGNORECASE | re.DOTALL
)


def parse_sudameris_notification(body: str) -> dict | None:
    """Extract vendor, amount, date from a Sudameris notification email body."""
    match = SUDAMERIS_PATTERN.search(body)
    if not match:
        return None

    vendor_raw = match.group(1).strip()
    amount_str = match.group(2).replace(".", "").replace(",", ".")  # 75.565,00 → 75565.00
    date_str   = match.group(3)   # DD/MM/YYYY
    time_str   = match.group(4)   # HH:MM:SS

    try:
        amount_cop = float(amount_str)
        txn_datetime = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None

    # Skip $0 authorisation checks
    if amount_cop == 0:
        return None

    return {
        "vendor": vendor_raw,
        "amount_cop": amount_cop,
        "txn_date": txn_datetime.date().isoformat(),
        "txn_datetime": txn_datetime.isoformat(),
    }


def run():
    log.info("─── Stanton Receipt Agent starting ───")

    gmail   = GmailClient()
    drive   = DriveClient()
    db      = SupabaseClient()
    matcher = ReceiptMatcher(gmail)

    # Fetch Sudameris notifications not yet processed
    processed_ids = db.get_processed_email_ids()
    notifications = gmail.search(
        'from:Notificaciones@gnbsudameris.com.co to:r@stanton.co',
        max_results=200
    )

    new_charges = []
    for msg_meta in notifications:
        msg_id = msg_meta["id"]
        if msg_id in processed_ids:
            continue

        msg = gmail.get_message(msg_id)
        parsed = parse_sudameris_notification(msg["body"])
        if parsed is None:
            log.info(f"Skipping {msg_id} — no match (auth check or parse error)")
            db.mark_processed(msg_id, skipped=True)
            continue

        parsed["email_id"] = msg_id
        parsed["email_date"] = msg["date"]
        new_charges.append(parsed)
        log.info(f"Charge: {parsed['vendor']} | COP {parsed['amount_cop']:,.0f} | {parsed['txn_date']}")

    log.info(f"Found {len(new_charges)} new charges to process")

    results = {"matched": [], "missing": []}

    for charge in new_charges:
        vendor   = charge["vendor"]
        txn_date = charge["txn_date"]
        amount   = charge["amount_cop"]

        # Try to find a receipt email for this charge (±3 days)
        receipt_email = matcher.find_receipt(vendor, txn_date, window_days=3)

        if receipt_email:
            log.info(f"✓ Receipt found for {vendor} on {txn_date}")
            pdf_path = generate_receipt_pdf(receipt_email)
            filename = _make_filename(vendor, txn_date, amount)
            folder   = _drive_folder_for_date(txn_date)
            drive_url = drive.upload(pdf_path, filename, folder)

            db.log_receipt({
                **charge,
                "status": "matched",
                "receipt_email_id": receipt_email["id"],
                "drive_url": drive_url,
                "filename": filename,
            })
            results["matched"].append({**charge, "drive_url": drive_url})
            gmail.apply_label(charge["email_id"], "receipt-processed")

        else:
            log.warning(f"✗ No receipt found for {vendor} on {txn_date}")
            db.log_receipt({
                **charge,
                "status": "missing_receipt",
                "receipt_email_id": None,
                "drive_url": None,
                "filename": None,
            })
            results["missing"].append(charge)
            gmail.apply_label(charge["email_id"], "receipt-missing")

        db.mark_processed(charge["email_id"])

    # Send weekly digest on Mondays
    if datetime.now().weekday() == 0:
        pending_missing = db.get_missing_receipts(days=30)
        send_weekly_report(pending_missing, results)

    log.info(
        f"─── Done — {len(results['matched'])} matched, "
        f"{len(results['missing'])} missing ───"
    )
    return results


def _make_filename(vendor: str, date_str: str, amount: float) -> str:
    """e.g. ANTHROPIC_2026-03-18_$188287.pdf"""
    vendor_clean = re.sub(r'[^A-Z0-9]', '_', vendor.upper()).strip('_')
    amount_clean = f"{amount:,.0f}".replace(",", "")
    return f"{vendor_clean}_{date_str}_COP{amount_clean}.pdf"


def _drive_folder_for_date(date_str: str) -> str:
    """Returns YYYY-MM path segment, e.g. '2026-03'"""
    return date_str[:7]  # first 7 chars of YYYY-MM-DD


if __name__ == "__main__":
    run()
