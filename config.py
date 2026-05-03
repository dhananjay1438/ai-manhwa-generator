from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    runware_api_key: str = "BXWiWIh82TDCxRDscnTIk9Cb3IV1Pmwu"
    GOOGLE_CLOUD_PROJECT: str = "ai-manhwa-creator"
    GOOGLE_CLOUD_LOCATION: str = "global"
    GOOGLE_APPLICATION_CREDENTIALS: str = "ai-manhwa-credentials.json"
    google_tts_voice: str = "gemini-3.1-flash-tts-preview"
    enable_whisper: bool = False
    google_drive_client_secret_path: str = "client-secret.json"
    google_drive_token_path: str = "drive-token.json"
    google_drive_folder_id: str | None = None
    google_drive_folder_path: str = ""
    youtube_client_secret_path: str = "client-secret.json"
    youtube_token_path: str = "youtube-token.json"
    youtube_privacy_status: str = "private"
    youtube_category_id: str = "24"
    youtube_made_for_kids: bool = False
    resend_api_key: str | None = None
    notification_email_from: str = "ai-manhwa-creator@resend.com"
    notification_email_to: str = "dhananjaypanage11@gmail.com"
    daily_series_id: str | None = None
    daily_episode_plot: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
