from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/rumi.db"
    cookie_secure: bool = False
    session_minutes: int = Field(default=60, ge=1, le=1440)

    @field_validator("database_url")
    @classmethod
    def local_sqlite(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("Phase 1 supports local SQLite only")
        return value
