"""
Google Drive Client
===================
Uses Gmail OAuth credentials (not service account) to upload PDFs.
Service accounts cannot upload to personal My Drive - they have no quota.
"""

import os
import json
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class DriveClient:
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
            scopes=DRIVE_SCOPES,
        )

        if self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())

        self.service = build("drive", "v3", credentials=self.creds)

        self.root_folder_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
        if not self.root_folder_id:
            raise ValueError("DRIVE_ROOT_FOLDER_ID env var not set")

        self._folder_cache: dict[str, str] = {}

    def upload(self, local_path: str, filename: str, subfolder: str) -> str:
        folder_id = self._get_or_create_folder(subfolder)

        file_metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        media = MediaFileUpload(local_path, mimetype="application/pdf", resumable=False)

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        drive_url = file.get("webViewLink", "")
        log.info(f"Uploaded to Drive: {filename} -> {drive_url}")

        try:
            import os as _os
            _os.unlink(local_path)
        except Exception:
            pass

        return drive_url

    def _get_or_create_folder(self, name: str) -> str:
        if name in self._folder_cache:
            return self._folder_cache[name]

        query = (
            f"name='{name}' and "
            f"'{self.root_folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )
        results = self.service.files().list(
            q=query, fields="files(id, name)"
        ).execute()

        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [self.root_folder_id],
            }
            folder = self.service.files().create(
                body=metadata, fields="id"
            ).execute()
            folder_id = folder["id"]
            log.info(f"Created Drive folder: {name}")

        self._folder_cache[name] = folder_id
        return folder_id
