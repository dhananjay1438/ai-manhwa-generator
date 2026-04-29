from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    runware_api_key: str = "MOCK_KEY"
    elevenlabs_api_key: str = "MOCK_KEY"

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

settings = Settings()
