from functools import lru_cache

from app.core.config import Settings, get_settings
from app.modules.llm_gateway.config import GatewayConfig, Target, load_config
from app.modules.llm_gateway.gateway import LLMGateway, LoggingSink
from app.modules.llm_gateway.providers.anthropic_provider import AnthropicProvider
from app.modules.llm_gateway.providers.base import LLMProvider
from app.modules.llm_gateway.providers.mock import MockProvider
from app.modules.llm_gateway.providers.openai_provider import OpenAIProvider


def build_gateway(settings: Settings) -> LLMGateway:
    config: GatewayConfig = load_config(settings.llm_routes_file)
    providers: dict[str, LLMProvider] = {}
    if settings.llm_default_provider == "mock":
        # Key-less development: every route is served by the mock provider.
        mock_target = Target(provider="mock", model="mock-1")
        for route in config.routes.values():
            route.targets = [mock_target]
        providers["mock"] = MockProvider()
    else:
        if settings.anthropic_api_key:
            providers["anthropic"] = AnthropicProvider(
                settings.anthropic_api_key.get_secret_value()
            )
        if settings.openai_api_key:
            providers["openai"] = OpenAIProvider(settings.openai_api_key.get_secret_value())
    return LLMGateway(
        config, providers, sink=LoggingSink(warn_usd=settings.llm_cost_warn_usd_per_turn)
    )


@lru_cache
def get_gateway() -> LLMGateway:
    return build_gateway(get_settings())


_override: LLMGateway | None = None


def set_gateway(gateway: LLMGateway | None) -> None:
    """Replace the shared gateway (tests, and anything that needs a custom one)."""
    global _override
    _override = gateway


def current_gateway() -> LLMGateway:
    return _override or get_gateway()
