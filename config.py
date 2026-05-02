from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    runware_api_key: str = "BXWiWIh82TDCxRDscnTIk9Cb3IV1Pmwu"
    GOOGLE_CLOUD_PROJECT: str = "ai-manhwa-creator"
    GOOGLE_CLOUD_LOCATION: str = "global"
    GOOGLE_APPLICATION_CREDENTIALS: str = "ai-manhwa-credentials.json"
    google_tts_voice: str = "gemini-3.1-flash-tts-preview"
    enable_whisper: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
