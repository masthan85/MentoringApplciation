"""Parse and validate structured model output defensively."""

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_structured[T: BaseModel](text: str, model: type[T]) -> T | None:
    """Return a validated model, or None if the text is not usable JSON for it."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        data: Any = json.loads(cleaned)
        return model.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        log.warning("structured output did not validate", extra={"model": model.__name__})
        return None
