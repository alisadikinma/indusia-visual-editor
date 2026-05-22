"""FastAPI application entry point.

Routers join here as they ship per milestone. Exception handlers enforce
the canonical `{status, message, data}` envelope on error paths (CLAUDE.md
§6.1).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from indusia_visual_editor import __version__
from indusia_visual_editor.config import get_config
from indusia_visual_editor.routes.assets import router as assets_router
from indusia_visual_editor.routes.projects import router as projects_router
from indusia_visual_editor.services.asset.bom_parser import BomParseError
from indusia_visual_editor.services.asset.image_store import (
    AssetNotFoundError,
    AssetTooLargeError,
)
from indusia_visual_editor.services.project.crud import (
    DuplicateSlugError,
    ProjectNotFoundError,
)
from indusia_visual_editor.utils.responses import failed

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Indusia Visual Editor",
    version=__version__,
    description="Factory-user-driven PCB inspection platform.",
)

# Dev CORS: the Vue frontend runs on Vite at :5173. Production CORS will be
# locked down at M14 via Traefik or an env-var allowlist.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


app.include_router(projects_router)
app.include_router(assets_router)


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
    logging.basicConfig(level=config.log_level)
    uvicorn.run(
        "indusia_visual_editor.main:app",
        host=config.app_host,
        port=config.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
