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
    database_url: str | None = None

    # Phase 1.3 — asset storage
    storage_root: str = "./storage"
    max_asset_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Phase 3.1 — Ollama LLM client
    ollama_url: str = "http://localhost:11434"
    ollama_model_planner: str = "gemma4:31b"
    ollama_model_prelabel: str = "gemma4:31b"
    ollama_timeout: int = 120  # seconds

    # Phase 4.6 — graphflow model directory root (shared filesystem
    # contract between visual-editor and auto-inspect-service).
    models_root: str = "./models"

    # Phase 7.1 — auto-inspect-service HTTP boundary. The visual-editor
    # POSTs `/api/training/start` and consumes the SSE progress stream;
    # never modifies the sibling repo (see CLAUDE.md §3).
    inspect_service_url: str = "http://localhost:8001"
    inspect_service_timeout: int = 30  # seconds (start call only — SSE is long-lived)


from functools import lru_cache


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()
