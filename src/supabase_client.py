"""
Supabase Client
===============
Logs all receipts and tracks processing state.

Table: receipts
  id              uuid (auto)
  email_id        text (Sudameris notification message ID)
  vendor          text
  amount_cop      numeric
  txn_date        date
  txn_datetime    timestamptz
  email_date      text
  status          text  — 'matched' | 'missing_receipt' | 'skipped'
  receipt_email_id text (nullable)
  drive_url       text (nullable)
  filename        text (nullable)
  created_at      timestamptz (auto)

Table: processed_emails
  email_id        text primary key
  processed_at    timestamptz
  skipped         boolean
"""

import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

log = logging.getLogger(__name__)


class SupabaseClient:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        self.client: Client = create_client(url, key)

    def get_processed_email_ids(self) -> set[str]:
        """Return set of already-processed Sudameris notification email IDs."""
        resp = self.client.table("processed_emails").select("email_id").execute()
        return {row["email_id"] for row in (resp.data or [])}

    def mark_processed(self, email_id: str, skipped: bool = False):
        self.client.table("processed_emails").upsert({
            "email_id": email_id,
            "processed_at": datetime.utcnow().isoformat(),
            "skipped": skipped,
        }).execute()

    def log_receipt(self, data: dict):
        """Insert a receipt record."""
        row = {
            "email_id":          data["email_id"],
            "vendor":            data["vendor"],
            "amount_cop":        data["amount_cop"],
            "txn_date":          data["txn_date"],
            "txn_datetime":      data["txn_datetime"],
            "email_date":        data.get("email_date", ""),
            "status":            data["status"],
            "receipt_email_id":  data.get("receipt_email_id"),
            "drive_url":         data.get("drive_url"),
            "filename":          data.get("filename"),
            "created_at":        datetime.utcnow().isoformat(),
        }
        self.client.table("receipts").insert(row).execute()

    def get_missing_receipts(self, days: int = 30) -> list[dict]:
        """Return receipts with status='missing_receipt' from last N days."""
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        resp = (
            self.client.table("receipts")
            .select("*")
            .eq("status", "missing_receipt")
            .gte("txn_date", since)
            .order("txn_date", desc=True)
            .execute()
        )
        return resp.data or []
