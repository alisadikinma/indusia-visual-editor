"""Application configuration via pydantic-settings.

All env vars are prefixed `IVE_` (Indusia Visual Editor).
Loads from process env first, then `.env` in the project root.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IVE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8002
    log_level: str = "INFO"


def get_config() -> AppConfig:
    return AppConfig()
