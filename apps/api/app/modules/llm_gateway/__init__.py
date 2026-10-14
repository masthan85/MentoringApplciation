"""Provider-agnostic LLM gateway. Import from here, not from submodules."""

from app.modules.llm_gateway.errors import (
    InvalidRequestError,
    LLMError,
    ProviderUnavailable,
    TransientProviderError,
)
from app.modules.llm_gateway.factory import build_gateway, current_gateway, get_gateway, set_gateway
from app.modules.llm_gateway.gateway import LLMGateway
from app.modules.llm_gateway.types import (
    CompletionRequest,
    CompletionResult,
    EmbeddingResult,
    Message,
    StreamEnd,
    StreamEvent,
    TextDelta,
    Usage,
)

__all__ = [
    "CompletionRequest",
    "CompletionResult",
    "EmbeddingResult",
    "InvalidRequestError",
    "LLMError",
    "LLMGateway",
    "Message",
    "ProviderUnavailable",
    "StreamEnd",
    "StreamEvent",
    "TextDelta",
    "TransientProviderError",
    "Usage",
    "build_gateway",
    "current_gateway",
    "get_gateway",
    "set_gateway",
]
