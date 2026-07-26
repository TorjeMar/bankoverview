from pathlib import Path

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Enable Banking application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    key_path: Path
    application_id: str
    api_origin: AnyHttpUrl
    aspsp_name: str
    aspsp_country: str
    callback_url: AnyHttpUrl

    @field_validator("key_path")
    @classmethod
    def validate_key_path(cls, value: Path) -> Path:
        if not value.is_file():
            raise ValueError(
                f"Enable Banking private key was not found: {value}"
            )
        return value

    @field_validator("aspsp_country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        value = value.strip().upper()

        if len(value) != 2 or not value.isalpha():
            raise ValueError(
                "ASPSP country must be a two-letter code"
            )

        return value

    @field_validator("application_id", "aspsp_name")
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value must not be empty")

        return value


def load_settings() -> Settings:
    """Load and validate settings from the environment."""
    return Settings()  # pyright: ignore[reportCallIssue]


settings = load_settings()
