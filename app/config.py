from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/rumi.db"
    cookie_secure: bool = False
    portfolio_mode: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "[::1]", "testserver"]
    shared_limits: bool = False
    public_demo_live: bool = False
    gemini_daily_limit: int = Field(default=10, ge=0, le=100)
    gemini_total_limit: int = Field(default=100, ge=0, le=1000)
    session_minutes: int = Field(default=60, ge=1, le=1440)
    processor_mode: str = "demo"
    gemini_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    gemini_model: str = "gemini-3.5-flash-lite"
    # Validate AI-only settings in the processor factory, so misconfiguration
    # cannot prevent otherwise valid incoming enquiries from being saved.
    ai_timeout_seconds: str = "20"
    ai_max_output_tokens: str = "1200"
    faq_path: Path = Path("private/faq.json")

    @field_validator("allowed_hosts")
    @classmethod
    def explicit_hosts(cls, hosts: list[str]) -> list[str]:
        import re

        if not hosts or any(not re.fullmatch(r"[A-Za-z0-9.-]+|\[::1\]", host) for host in hosts):
            raise ValueError("Use explicit hostnames without schemes, paths, ports or wildcards")
        return hosts

    @field_validator("database_url")
    @classmethod
    def supported_database(cls, value: str) -> str:
        from sqlalchemy.engine import make_url

        if make_url(value).drivername not in {"sqlite", "postgresql", "postgresql+psycopg"}:
            raise ValueError("Use SQLite or PostgreSQL with psycopg")
        return value

    @model_validator(mode="after")
    def deployment_safety(self):
        import os

        if os.getenv("VERCEL") and not self.portfolio_mode:
            raise ValueError("Vercel requires portfolio mode")
        if self.portfolio_mode:
            from sqlalchemy.engine import make_url

            if make_url(self.database_url).get_backend_name() != "postgresql":
                raise ValueError("Portfolio mode requires a separate PostgreSQL database")
            if not self.cookie_secure or not self.shared_limits:
                raise ValueError("Portfolio mode requires secure cookies and shared limits")
            if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
                raise ValueError("Portfolio mode requires explicit allowed hosts")
            if make_url(self.database_url).query.get("sslmode") not in {"require", "verify-full"}:
                raise ValueError("Portfolio database requires TLS")
            # Never load the local private knowledge in a public portfolio process.
            self.faq_path = Path(__file__).parent / "demo_data" / "faq.json"
        if self.public_demo_live and (not self.portfolio_mode or self.processor_mode != "gemini"):
            raise ValueError("Live demo requires portfolio mode and explicit Gemini mode")
        return self
