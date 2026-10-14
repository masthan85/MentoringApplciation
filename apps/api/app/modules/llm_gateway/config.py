"""Route configuration: which provider and model serves each kind of call."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Effort = Literal["low", "medium", "high", "xhigh", "max"]

DEFAULT_ROUTES_FILE = Path(__file__).with_name("routes.yaml")


class Target(BaseModel):
    provider: str
    model: str
    effort: Effort | None = None  # reasoning effort, where the provider supports it


class Route(BaseModel):
    kind: Literal["chat", "embedding"] = "chat"
    targets: list[Target] = Field(min_length=1)
    max_tokens: int = 1024
    timeout_s: float = 60.0
    retries: int = Field(default=1, ge=0, le=5)


class Price(BaseModel):
    input_per_mtok: float
    output_per_mtok: float = 0.0
    cache_read_per_mtok: float | None = None


class GatewayConfig(BaseModel):
    routes: dict[str, Route]
    # Keyed "provider/model". Models without an entry have unknown cost.
    pricing: dict[str, Price] = Field(default_factory=dict)

    def price_for(self, provider: str, model: str) -> Price | None:
        return self.pricing.get(f"{provider}/{model}")


def load_config(path: str | Path | None = None) -> GatewayConfig:
    raw = yaml.safe_load(Path(path or DEFAULT_ROUTES_FILE).read_text())
    return GatewayConfig.model_validate(raw)
