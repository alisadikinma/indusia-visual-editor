"""FastAPI application entry point.

Routers join here as they ship per milestone. Exception handlers enforce
the canonical `{status, message, data}` envelope on error paths (CLAUDE.md
§6.1).
"""

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from indusia_visual_editor import __version__
from indusia_visual_editor.config import get_config
from indusia_visual_editor.routes.adapt import router as adapt_router
from indusia_visual_editor.routes.assets import router as assets_router
from indusia_visual_editor.routes.auth import router as auth_router
from indusia_visual_editor.routes.bom import router as bom_router
from indusia_visual_editor.routes.chat import router as chat_router
from indusia_visual_editor.routes.dashboard import router as dashboard_router
from indusia_visual_editor.routes.dataset_stats import router as dataset_stats_router
from indusia_visual_editor.routes.deploy import router as deploy_router
from indusia_visual_editor.routes.edges import router as edges_router
from indusia_visual_editor.routes.eval import router as eval_router
from indusia_visual_editor.routes.inspection_feedback import (
    project_router as inspection_feedback_project_router,
    router as inspection_feedback_router,
)
from indusia_visual_editor.routes.labels import router as labels_router
from indusia_visual_editor.routes.llm import router as llm_router
from indusia_visual_editor.routes.projects import router as projects_router
from indusia_visual_editor.routes.training import (
    router as training_router,
    stream_router as training_stream_router,
)
from indusia_visual_editor.services.asset.bom_parser import BomParseError
from indusia_visual_editor.services.asset.image_store import (
    AssetNotFoundError,
    AssetTooLargeError,
)
from indusia_visual_editor.services.project.crud import (
    DuplicateSlugError,
    ProjectNotFoundError,
)
from indusia_visual_editor.utils.logging_config import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from indusia_visual_editor.utils.otel_config import configure_otel
from indusia_visual_editor.utils.responses import failed

# Configure structlog once at import time using whatever env/.env says. The
# default in logging_config also runs, but doing it explicitly here pins the
# mode to the AppConfig values (IVE_LOG_MODE / IVE_LOG_LEVEL).
_config = get_config()
configure_logging(
    mode=_config.log_mode if _config.log_mode in ("prod", "dev") else "prod",
    level=getattr(logging, _config.log_level.upper(), logging.INFO),
)
logger = get_logger(__name__)

# Install the OTel TracerProvider once. With no `OTEL_EXPORTER_OTLP_ENDPOINT`
# set, this is a near-zero-overhead no-op — spans are still created so any
# `tracer.start_as_current_span` lines in services stay valid. Production
# wires the env var (e.g. `http://otel-collector:4318/v1/traces`) and spans
# flow to the collector.
configure_otel()

app = FastAPI(
    title="Indusia Visual Editor",
    version=__version__,
    description="Factory-user-driven PCB inspection platform.",
)

# Auto-instrument inbound HTTP. Adds a span per request named
# `<METHOD> <route>` carrying `http.status_code`, `http.target`, etc.
# Outbound httpx calls get instrumented too (matches Ollama + edge notify).
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # noqa: E402

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Stamp a per-request UUID into structlog contextvars so every log call
    inside the handler (and any helper it spawns on the same task) carries
    `request_id` without manual plumbing. The id is also echoed back as an
    `X-Request-ID` response header so clients can correlate against logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        bind_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            clear_context()
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestContextMiddleware)

# CORS allowlist — env-configurable via IVE_CORS_ALLOW_ORIGINS (comma-separated).
# Defaults cover the Vite dev server (:5173) + the local prod nginx (:8080).
_cors_origins = [
    origin.strip()
    for origin in get_config().cors_allow_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProjectNotFoundError)
async def _project_not_found(request: Request, exc: ProjectNotFoundError):
    return failed(f"project {exc} not found", status_code=404)


@app.exception_handler(DuplicateSlugError)
async def _duplicate_slug(request: Request, exc: DuplicateSlugError):
    return failed(f"slug {exc!s} already in use", status_code=409)


@app.exception_handler(RequestValidationError)
async def _validation_failed(request: Request, exc: RequestValidationError):
    return failed("validation failed", status_code=422, data=exc.errors())


@app.exception_handler(AssetNotFoundError)
async def _asset_not_found(request: Request, exc: AssetNotFoundError):
    return failed(f"asset {exc} not found", status_code=404)


@app.exception_handler(AssetTooLargeError)
async def _asset_too_large(request: Request, exc: AssetTooLargeError):
    return failed(f"file too large: {exc}", status_code=413)


@app.exception_handler(BomParseError)
async def _bom_parse_failed(request: Request, exc: BomParseError):
    return failed(str(exc), status_code=422)


@app.exception_handler(HTTPException)
async def _http_exception(request: Request, exc: HTTPException):
    # Wrap FastAPI HTTPException into the canonical envelope (CLAUDE.md §6.1).
    return failed(str(exc.detail), status_code=exc.status_code)


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(assets_router)
app.include_router(bom_router)
app.include_router(llm_router)
app.include_router(adapt_router)
app.include_router(labels_router)
app.include_router(dataset_stats_router)
app.include_router(dashboard_router)
app.include_router(training_router)
app.include_router(training_stream_router)
app.include_router(eval_router)
app.include_router(deploy_router)
app.include_router(edges_router)
app.include_router(chat_router)
app.include_router(inspection_feedback_project_router)
app.include_router(inspection_feedback_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": True,
        "message": "ok",
        "data": {"version": __version__},
    }


def main() -> None:
    import uvicorn

    config = get_config()
    # structlog is already configured at import time; this just re-pins the
    # level if the env was updated between import and main() invocation.
    configure_logging(
        mode=config.log_mode if config.log_mode in ("prod", "dev") else "prod",
        level=getattr(logging, config.log_level.upper(), logging.INFO),
    )
    uvicorn.run(
        "indusia_visual_editor.main:app",
        host=config.app_host,
        port=config.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
