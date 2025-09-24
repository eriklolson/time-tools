# clickup/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    CLICKUP_TOKEN: str
    CLICKUP_LIST_ID: str
    CLICKUP_CLOSED_STATUS: str | None = None

settings = Settings()
CLICKUP_TOKEN = settings.CLICKUP_TOKEN
CLICKUP_LIST_ID = settings.CLICKUP_LIST_ID
CLOSED_STATUS = settings.CLICKUP_CLOSED_STATUS or ""
