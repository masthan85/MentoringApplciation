import json
from typing import Any


def sse(event: str, data: dict[str, Any]) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
