"""Canonical `{status, message, data}` envelope helpers.

Every Indusia inspection service uses this shape on both success AND error
paths — see CLAUDE.md §6.1. New routes MUST wrap responses with these
helpers (or rely on the exception handlers in main.py, which also use them).
"""

from typing import Any

from fastapi.responses import JSONResponse


def success(
    data: Any = None,
    message: str = "ok",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        {"status": True, "message": message, "data": data},
        status_code=status_code,
    )


def failed(
    message: str,
    status_code: int = 400,
    data: Any = None,
) -> JSONResponse:
    return JSONResponse(
        {"status": False, "message": message, "data": data},
        status_code=status_code,
    )
