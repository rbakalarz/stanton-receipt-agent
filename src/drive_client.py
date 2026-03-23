"""
Google Drive Client
===================
Uploads PDFs to a shared Google Drive folder organized by YYYY-MM.
"""

import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveClient:
    def __init__(self):
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not sa_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")

        sa_info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=DRIVE_SCOPES
        )
        self.service = build("drive", "v3", credentials=creds)

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
            supportsAllDrives=True,
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
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
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
                body=metadata,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            folder_id = folder["id"]
            log.info(f"Created Drive folder: {name}")

        self._folder_cache[name] = folder_id
        return folder_id
