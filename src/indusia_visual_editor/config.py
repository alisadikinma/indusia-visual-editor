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
    # M14.4 — structlog renderer mode. "prod" → JSON (machine-parseable
    # for the log aggregator); "dev" → console renderer (human-readable).
    log_mode: str = "prod"
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

    # Phase 10.1 — `ais` CLI subprocess registry boundary. See
    # docs/specs/ais-model-push.md. Working directory MUST be inside the
    # model-registry git repo (operator runs `ais model setup` once per
    # host). The CLI is not bundled with indusia-visual-editor; production
    # hosts install it from auto-inspect-service per the spec.
    ais_binary: str = "ais"  # absolute path or PATH lookup
    registry_root: str = "./registry"
    ais_push_timeout_secs: float = 300.0  # 5 min — covers slow LFS pushes

    # M13 — JWT bearer auth. Secret MUST be overridden via IVE_AUTH_JWT_SECRET
    # in production; the dev default is non-secret and will be refused by the
    # auth layer if it survives into a non-dev env (Phase 14 hardening).
    auth_jwt_secret: str = "dev-only-jwt-secret-change-me"
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_ttl_seconds: int = 3600  # 1 hour access token
    auth_refresh_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    auth_refresh_cookie_name: str = "ive_refresh"
    auth_refresh_cookie_secure: bool = False  # flipped to True behind Traefik HTTPS

    # M14.7 — CORS allowlist. Comma-separated origins; defaults cover the
    # Vite dev server (:5173) + the local prod nginx container (:8080).
    # Override via IVE_CORS_ALLOW_ORIGINS in prod with your real hostnames.
    cors_allow_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )


from functools import lru_cache


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()
