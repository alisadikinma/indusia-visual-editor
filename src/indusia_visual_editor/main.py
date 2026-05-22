"""FastAPI application entry point.

Routers join here as they ship per milestone. Exception handlers enforce
the canonical `{status, message, data}` envelope on error paths (CLAUDE.md
§6.1).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from indusia_visual_editor import __version__
from indusia_visual_editor.config import get_config
from indusia_visual_editor.routes.projects import router as projects_router
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


@app.exception_handler(ProjectNotFoundError)
async def _project_not_found(request: Request, exc: ProjectNotFoundError):
    return failed(f"project {exc} not found", status_code=404)


@app.exception_handler(DuplicateSlugError)
async def _duplicate_slug(request: Request, exc: DuplicateSlugError):
    return failed(f"slug {exc!s} already in use", status_code=409)


@app.exception_handler(RequestValidationError)
async def _validation_failed(request: Request, exc: RequestValidationError):
    return failed("validation failed", status_code=422, data=exc.errors())


app.include_router(projects_router)


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
