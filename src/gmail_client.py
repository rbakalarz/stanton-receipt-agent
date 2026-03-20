"""
Gmail client — thin wrapper around the Gmail API.
Uses OAuth2 credentials stored in GMAIL_CREDENTIALS_JSON env var
(the token.json content you already have from the Claude integration).
"""

import os
import json
import base64
import logging
from email import message_from_bytes
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",   # for applying labels
]

# Vendor name → sender patterns for receipt matching
# Add to this dict as you discover new vendors
VENDOR_SENDER_MAP = {
    "ANTHROPIC":       ["anthropic.com", "billing@anthropic"],
    "CANVA":           ["canva.com"],
    "GRAMMARLY":       ["grammarly.com"],
    "OPENAI":          ["openai.com"],
    "LOVABLE":         ["lovable.dev", "lovable.app"],
    "OTIO":            ["otio.ai", "otio.com"],
    "UBER":            ["uber.com"],
    "RAPPI":           ["rappi.com", "rappi.co"],
    "AMERICAN":        ["aa.com", "info.email.aa.com"],
    "EMIRATES":        ["emirates.email", "emirates.com"],
}


class GmailClient:
    def __init__(self):
        creds_json = os.environ.get("GMAIL_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GMAIL_CREDENTIALS_JSON env var not set")

        creds_data = json.loads(creds_json)
        self.creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=SCOPES,
        )

        if self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())

        self.service = build("gmail", "v1", credentials=self.creds)
        self.user_id = "me"

    def search(self, query: str, max_results: int = 100) -> list[dict]:
        """Return list of {id, threadId} matching Gmail query."""
        results = []
        page_token = None

        while True:
            resp = self.service.users().messages().list(
                userId=self.user_id,
                q=query,
                maxResults=min(max_results - len(results), 500),
                pageToken=page_token,
            ).execute()

            results.extend(resp.get("messages", []))
            page_token = resp.get("nextPageToken")

            if not page_token or len(results) >= max_results:
                break

        return results[:max_results]

    def get_message(self, message_id: str) -> dict:
        """Fetch full message, return dict with body, date, subject, from."""
        msg = self.service.users().messages().get(
            userId=self.user_id,
            id=message_id,
            format="full",
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        body = self._extract_body(msg["payload"])

        return {
            "id": message_id,
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "date": headers.get("date", ""),
            "body": body,
            "raw_payload": msg["payload"],
        }

    def get_message_html(self, message_id: str) -> str:
        """Return HTML body of message (falls back to plain text)."""
        msg = self.service.users().messages().get(
            userId=self.user_id,
            id=message_id,
            format="full",
        ).execute()
        return self._extract_html(msg["payload"]) or self._extract_body(msg["payload"])

    def apply_label(self, message_id: str, label_name: str):
        """Apply a label to a message, creating the label if needed."""
        label_id = self._get_or_create_label(label_name)
        self.service.users().messages().modify(
            userId=self.user_id,
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

    def _get_or_create_label(self, name: str) -> str:
        labels = self.service.users().labels().list(userId=self.user_id).execute()
        for label in labels.get("labels", []):
            if label["name"].lower() == name.lower():
                return label["id"]

        # Create it
        new_label = self.service.users().labels().create(
            userId=self.user_id,
            body={"name": name, "labelListVisibility": "labelShow",
                  "messageListVisibility": "show"},
        ).execute()
        return new_label["id"]

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from MIME payload."""
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result
        return ""

    def _extract_html(self, payload: dict) -> str:
        """Recursively extract HTML body from MIME payload."""
        if payload.get("mimeType") == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            result = self._extract_html(part)
            if result:
                return result
        return ""
