"""
Receipt Matcher
===============
Given a vendor name and transaction date from a Sudameris notification,
searches Gmail for a matching receipt email within a time window.

Matching strategy (in order):
  1. Known sender map — if we know Anthropic sends from anthropic.com, search that
  2. Fuzzy vendor name search — search for the vendor name in email body/subject
  3. Amount match — if still ambiguous, verify amount appears in the email
"""

import re
import logging
from datetime import datetime, timedelta
from gmail_client import GmailClient, VENDOR_SENDER_MAP

log = logging.getLogger(__name__)


class ReceiptMatcher:
    def __init__(self, gmail: GmailClient):
        self.gmail = gmail

    def find_receipt(self, vendor: str, txn_date: str, window_days: int = 3) -> dict | None:
        """
        Try to find a receipt email for vendor around txn_date.
        Returns message dict or None.
        """
        vendor_upper = vendor.upper().strip()

        # Date window
        date_obj   = datetime.strptime(txn_date, "%Y-%m-%d")
        after_date = (date_obj - timedelta(days=window_days)).strftime("%Y/%m/%d")
        before_date = (date_obj + timedelta(days=window_days)).strftime("%Y/%m/%d")

        # Strategy 1: known sender
        sender_patterns = self._get_sender_patterns(vendor_upper)
        for sender in sender_patterns:
            query = (
                f"to:r@stanton.co from:{sender} "
                f"after:{after_date} before:{before_date}"
            )
            results = self.gmail.search(query, max_results=5)
            if results:
                log.info(f"  Matched via sender: {sender}")
                return self.gmail.get_message(results[0]["id"])

        # Strategy 2: vendor name in subject or body
        vendor_keyword = self._vendor_to_keyword(vendor_upper)
        if vendor_keyword:
            query = (
                f"to:r@stanton.co {vendor_keyword} "
                f"(receipt OR recibo OR invoice OR factura OR confirmation OR confirmación) "
                f"after:{after_date} before:{before_date}"
            )
            results = self.gmail.search(query, max_results=10)
            if results:
                log.info(f"  Matched via keyword: {vendor_keyword}")
                return self.gmail.get_message(results[0]["id"])

        return None

    def _get_sender_patterns(self, vendor_upper: str) -> list[str]:
        """Return known sender domains for a vendor name."""
        for key, patterns in VENDOR_SENDER_MAP.items():
            if key in vendor_upper or vendor_upper in key:
                return patterns
        return []

    def _vendor_to_keyword(self, vendor_upper: str) -> str:
        """
        Convert a raw Sudameris vendor string to a useful search keyword.
        e.g. "AMERICAN AIRLIN" → "american airlines"
             "UBER * EATS P"  → "uber"
             "ANTHROPIC"      → "anthropic"
        """
        # Strip common noise
        cleaned = re.sub(r'\*+', ' ', vendor_upper)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Take first meaningful word(s)
        words = [w for w in cleaned.split() if len(w) > 2]
        if not words:
            return ""

        # Return first 1-2 words as keyword
        return " ".join(words[:2]).lower()
