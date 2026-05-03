from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import settings
from logger import logger

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


class OAuthTokenError(RuntimeError):
    pass


class YouTubePermissionError(RuntimeError):
    pass


@dataclass
class PublishResult:
    drive_file_id: str
    drive_web_view_link: str | None
    youtube_video_id: str
    youtube_url: str


class GooglePublisher:
    """Uploads generated episode videos to Google Drive and YouTube."""

    def __init__(
        self,
        interactive_auth: bool = True,
        enable_drive: bool = True,
        enable_youtube: bool = True,
    ) -> None:
        self.drive = None
        self.youtube = None

        if enable_drive:
            drive_credentials = self._load_credentials(
                service_name="Google Drive",
                client_secret_path=Path(settings.google_drive_client_secret_path),
                token_path=Path(settings.google_drive_token_path),
                scopes=DRIVE_SCOPES,
                interactive_auth=interactive_auth,
            )
            self.drive = build("drive", "v3", credentials=drive_credentials)

        if enable_youtube:
            youtube_credentials = self._load_credentials(
                service_name="YouTube",
                client_secret_path=Path(settings.youtube_client_secret_path),
                token_path=Path(settings.youtube_token_path),
                scopes=YOUTUBE_SCOPES,
                interactive_auth=interactive_auth,
            )
            self.youtube = build("youtube", "v3", credentials=youtube_credentials)

    @staticmethod
    def assert_tokens_present() -> None:
        missing = []
        for service_name, token_path in [
            ("Google Drive", Path(settings.google_drive_token_path)),
            ("YouTube", Path(settings.youtube_token_path)),
        ]:
            if not token_path.exists():
                missing.append(f"{service_name}: {token_path}")

        if missing:
            raise OAuthTokenError(
                "Missing OAuth token file(s): "
                + ", ".join(missing)
                + ". Run `uv run python daily_episode.py --setup-auth` once from a shell."
            )

    @staticmethod
    def assert_youtube_token_present() -> None:
        token_path = Path(settings.youtube_token_path)
        if not token_path.exists():
            raise OAuthTokenError(
                f"Missing YouTube OAuth token file: {token_path}. "
                "Run `uv run python daily_episode.py --setup-auth` once from a shell."
            )

    def _load_credentials(
        self,
        service_name: str,
        client_secret_path: Path,
        token_path: Path,
        scopes: list[str],
        interactive_auth: bool,
    ) -> Credentials:
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
            if not credentials.has_scopes(scopes):
                raise OAuthTokenError(
                    f"{service_name} token at {token_path} is missing required scopes. "
                    "Run `uv run python daily_episode.py --setup-auth` once from a shell."
                )

        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("Refreshing %s OAuth token...", service_name)
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            if not interactive_auth:
                raise OAuthTokenError(
                    f"{service_name} OAuth token at {token_path} is missing or invalid. "
                    "Run `uv run python daily_episode.py --setup-auth` once from a shell."
                )

            if not client_secret_path.exists():
                raise FileNotFoundError(
                    f"Missing {client_secret_path}. Add your OAuth client secret file there "
                    f"before publishing to {service_name}."
                )

            logger.info(
                "Starting %s OAuth flow. Choose the correct Google account/channel.",
                service_name,
            )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
            credentials = flow.run_local_server(port=0)

        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def _resolve_drive_parent_id(self) -> str | None:
        if settings.google_drive_folder_id:
            return settings.google_drive_folder_id

        drive_path = settings.google_drive_folder_path.strip("/")
        if not drive_path:
            return None

        parent_id = "root"
        for folder_name in [part.strip() for part in drive_path.split("/") if part.strip()]:
            parent_id = self._get_or_create_drive_folder(folder_name, parent_id)
        return parent_id

    def _get_or_create_drive_folder(self, folder_name: str, parent_id: str) -> str:
        if not self.drive:
            raise RuntimeError("Google Drive client is not initialized.")

        escaped_name = folder_name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            "mimeType = 'application/vnd.google-apps.folder' "
            f"and name = '{escaped_name}' "
            f"and '{parent_id}' in parents "
            "and trashed = false"
        )
        response = (
            self.drive.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        folders = response.get("files", [])
        if folders:
            return folders[0]["id"]

        logger.info("Creating Google Drive folder %s under %s.", folder_name, parent_id)
        folder = (
            self.drive.files()
            .create(
                body={
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        return folder["id"]

    def upload_to_drive(self, video_path: Path, title: str) -> dict:
        if not self.drive:
            raise RuntimeError("Google Drive client is not initialized.")

        metadata = {
            "name": video_path.name,
            "description": title,
        }

        parent_id = self._resolve_drive_parent_id()
        if parent_id:
            metadata["parents"] = [parent_id]

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        logger.info("Uploading %s to Google Drive...", video_path)
        return (
            self.drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

    def upload_to_youtube(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        publish_at: datetime | None = None,
    ) -> dict:
        if not self.youtube:
            raise RuntimeError("YouTube client is not initialized.")

        status = {
            "privacyStatus": settings.youtube_privacy_status,
            "selfDeclaredMadeForKids": settings.youtube_made_for_kids,
        }
        if publish_at:
            status["privacyStatus"] = "private"
            status["publishAt"] = publish_at.isoformat()

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags or [],
                "categoryId": settings.youtube_category_id,
            },
            "status": status,
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        if publish_at:
            logger.info("Uploading %s to YouTube scheduled for %s...", video_path, publish_at)
        else:
            logger.info("Uploading %s to YouTube...", video_path)
        return (
            self.youtube.videos()
            .insert(part="snippet,status", body=body, media_body=media)
            .execute()
        )

    def update_youtube_metadata(
        self,
        video_id: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category_id: str | None = None,
    ) -> dict:
        if not self.youtube:
            raise RuntimeError("YouTube client is not initialized.")

        body = {
            "id": video_id,
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags or [],
                "categoryId": category_id or settings.youtube_category_id,
            },
        }
        logger.info("Updating YouTube metadata for %s: %s", video_id, title)
        try:
            return self.youtube.videos().update(part="snippet", body=body).execute()
        except HttpError as exc:
            if exc.resp.status == 403 and b"insufficient" in exc.content.lower():
                raise YouTubePermissionError(
                    "YouTube token does not have permission to update video metadata. "
                    f"Delete {settings.youtube_token_path}, then run "
                    "`uv run python daily_episode.py --setup-auth` and choose the same "
                    "YouTube brand account/channel. After that, rerun this command."
                ) from exc
            raise

    def publish_episode(
        self,
        video_path: Path | str,
        series_id: str,
        episode_number: int,
        title: str,
        description: str,
        tags: list[str] | None = None,
        publish_at: datetime | None = None,
        append_episode_suffix: bool = True,
    ) -> PublishResult:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Cannot publish missing video: {video_path}")

        upload_title = (
            f"{title} | {series_id} Episode {episode_number}" if append_episode_suffix else title
        )
        upload_tags = tags or ["manhwa", "webtoon", "recap", series_id]

        drive_file = self.upload_to_drive(video_path, upload_title)
        youtube_video = self.upload_to_youtube(
            video_path, upload_title, description, upload_tags, publish_at=publish_at
        )
        youtube_video_id = youtube_video["id"]

        return PublishResult(
            drive_file_id=drive_file["id"],
            drive_web_view_link=drive_file.get("webViewLink"),
            youtube_video_id=youtube_video_id,
            youtube_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
        )
