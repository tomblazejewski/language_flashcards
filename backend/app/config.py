from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # ------------------------------------------------------------------ #
    # Auth / JWT
    # ------------------------------------------------------------------ #
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # ------------------------------------------------------------------ #
    # App
    # ------------------------------------------------------------------ #
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
