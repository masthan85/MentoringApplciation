"""Application errors, rendered as RFC 9457 problem details."""

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra or {}


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


def _problem(status: int, code: str, detail: str, request: Request, **extra: Any) -> JSONResponse:
    body = {
        "type": f"https://mentor.example/problems/{code}",
        "title": code.replace("_", " "),
        "status": status,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        response = _problem(exc.status_code, exc.code, exc.detail, request, **exc.extra)
        if isinstance(exc, Unauthorized):
            response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validators that raise ValueError put the exception object in the error context.
        errors = json.loads(json.dumps(exc.errors(), default=str))
        return _problem(
            422, "validation_error", "Request validation failed", request, errors=errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(exc.status_code, "http_error", str(exc.detail), request)
