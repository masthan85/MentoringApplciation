"""Which lens (or lenses) the mentor uses for a message.

Order of authority: the user's pinned choice, then a confident suggestion from
the per-message classifier, then the default derived from the profile.
"""

from dataclasses import dataclass
from typing import Literal

from app.modules.persona.registry import PackRegistry

Source = Literal["default", "pinned", "classifier"]
MAX_LENSES = 2


@dataclass(frozen=True)
class ActivePersona:
    lens_ids: tuple[str, ...]
    weights: tuple[float, ...]
    source: Source

    def snapshot(self) -> dict[str, object]:
        return {
            "lens_ids": list(self.lens_ids),
            "weights": list(self.weights),
            "source": self.source,
        }


def normalise_weights(weights: list[float]) -> tuple[float, ...]:
    total = sum(weights)
    if total <= 0:
        return tuple(1 / len(weights) for _ in weights)
    return tuple(round(w / total, 4) for w in weights)


def select_persona(
    *,
    registry: PackRegistry,
    role_family: str | None,
    seniority: str | None,
    pinned_lens_ids: list[str] | None,
    pinned_weights: list[float] | None,
    suggested_lens: str | None,
    suggestion_confidence: float,
    threshold: float,
) -> ActivePersona:
    pinned = [lens for lens in (pinned_lens_ids or []) if registry.get(lens)][:MAX_LENSES]
    if pinned:
        weights = list(pinned_weights or [])[: len(pinned)]
        if len(weights) != len(pinned):
            weights = [1.0] * len(pinned)
        return ActivePersona(tuple(pinned), normalise_weights(weights), "pinned")

    default = registry.default_for(role_family, seniority)
    if (
        suggested_lens
        and suggested_lens != default
        and registry.get(suggested_lens)
        and (suggestion_confidence >= threshold)
    ):
        return ActivePersona((suggested_lens,), (1.0,), "classifier")
    return ActivePersona((default,), (1.0,), "default")
