"""Structured JSON logging with request-scoped context."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def bind_log_context(**values: Any) -> None:
    _context.set({**(_context.get() or {}), **values})


def clear_log_context() -> None:
    _context.set({})


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": self._service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_context.get() or {})
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str, service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Uvicorn's access log is replaced by our own request log middleware.
    logging.getLogger("uvicorn.access").disabled = True
