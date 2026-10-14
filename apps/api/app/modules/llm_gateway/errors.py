class LLMError(Exception):
    """Base class for gateway errors."""


class TransientProviderError(LLMError):
    """Rate limits, timeouts, connection failures and 5xx. Worth retrying."""


class ProviderUnavailable(LLMError):
    """The provider cannot serve this request (bad credentials, outage after retries)."""


class InvalidRequestError(LLMError):
    """The request itself is wrong. Retrying or falling back will not help."""
