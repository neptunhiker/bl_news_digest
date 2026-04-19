from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    timezone: str = "Europe/Berlin"
    log_level: str = "INFO"
    http_user_agent: str = "BeginnerLuft-AVGS-NewsBot/0.1"

    # Database
    db_path: str = "./data/app.db"

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"

    # Slack
    slack_bot_token: str
    slack_channel_id: str
    slack_post_enabled: bool = False

    # Digest
    digest_top_n: int = 5
    dry_run: bool = True
    ai_review_cache_enabled: bool = True

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    @property
    def db_path_resolved(self) -> Path:
        return Path(self.db_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
