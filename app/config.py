from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/rumi.db"
    cookie_secure: bool = False
    session_minutes: int = Field(default=60, ge=1, le=1440)
    processor_mode: str = "demo"
    gemini_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    gemini_model: str = "gemini-3.5-flash-lite"
    # Validate AI-only settings in the processor factory, so misconfiguration
    # cannot prevent otherwise valid incoming enquiries from being saved.
    ai_timeout_seconds: str = "20"
    ai_max_output_tokens: str = "1200"
    faq_path: Path = Path("private/faq.json")

    @field_validator("database_url")
    @classmethod
    def local_sqlite(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("This local prototype supports SQLite only")
        return value
