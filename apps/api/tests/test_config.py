import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_dev_auth_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
        Settings(env="production", auth_mode="dev")


def test_dev_auth_allowed_locally() -> None:
    assert Settings(env="local", auth_mode="dev").auth_mode == "dev"


def test_oidc_requires_provider_settings() -> None:
    with pytest.raises(ValidationError, match="AUTH_ISSUER"):
        Settings(env="production", auth_mode="oidc")


def test_oidc_with_provider_settings() -> None:
    s = Settings(
        env="production",
        auth_mode="oidc",
        auth_issuer="https://issuer.example/",
        auth_audience="mentor-api",
        auth_jwks_url="https://issuer.example/.well-known/jwks.json",
    )
    assert s.auth_algorithms == ["RS256"]


def test_dev_secret_is_cleared_in_production() -> None:
    s = Settings(
        env="production",
        auth_mode="oidc",
        auth_issuer="https://i/",
        auth_audience="a",
        auth_jwks_url="https://i/jwks",
    )
    assert s.dev_auth_secret.get_secret_value() == ""


def test_blank_api_keys_count_as_not_configured() -> None:
    s = Settings(env="test", auth_mode="dev", anthropic_api_key="", openai_api_key="")  # type: ignore[arg-type]
    assert not s.anthropic_api_key
    assert not s.openai_api_key
