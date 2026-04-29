from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    runware_api_key: str = "MOCK_KEY"
    google_api_key: str = "MOCK_KEY"
    google_tts_voice: str = "default_voice"
    enable_whisper: bool = True

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

settings = Settings()
