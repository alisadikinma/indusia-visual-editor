"""FastAPI application entry point.

Phase 0.1 scaffold: just /health. Routers, DB, services join in later phases.
"""

import logging

from fastapi import FastAPI

from indusia_visual_editor import __version__
from indusia_visual_editor.config import get_config

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Indusia Visual Editor",
    version=__version__,
    description="Factory-user-driven PCB inspection platform.",
)


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
