"""Turns the active lens (or two lenses) into a short prompt section.

The section carries substance: priorities, questions, failure modes and
seniority-specific depth. It is never a job title and never a biography.
"""

from collections.abc import Callable

from app.modules.persona.registry import PackRegistry
from app.modules.persona.selection import ActivePersona

MAX_PRIORITIES = 6
MAX_QUESTIONS = 5
MAX_FAILURE_MODES = 4
MAX_RED_FLAGS = 4


def _merge(items_by_lens: list[list[str]], weights: tuple[float, ...], limit: int) -> list[str]:
    """Interleave by weighted rank so a heavier lens contributes more of its top items."""
    scored: dict[str, float] = {}
    for items, weight in zip(items_by_lens, weights, strict=True):
        for rank, item in enumerate(items):
            score = weight / (rank + 1)
            key = item.strip()
            scored[key] = max(scored.get(key, 0.0), score)
    ordered = sorted(scored, key=lambda k: scored[k], reverse=True)
    return ordered[:limit]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_persona_section(
    persona: ActivePersona, seniority: str | None, registry: PackRegistry
) -> str:
    lenses = [lens for lid in persona.lens_ids if (lens := registry.get(lid))]
    if not lenses:
        return ""
    weights = persona.weights[: len(lenses)]
    level = seniority if seniority in ("junior", "mid", "senior", "lead", "executive") else "mid"

    def field(getter: Callable[..., list[str]]) -> list[list[str]]:
        return [getter(lens) for lens in lenses]

    if len(lenses) == 1:
        lens = lenses[0]
        perspective = lens.perspective
    else:
        names = " and ".join(lens.name.lower() for lens in lenses)
        perspective = f"A blend of two perspectives ({names}). " + " ".join(
            f"{lens.perspective}" for lens in lenses
        )
    depth = " ".join(
        lens.depth_by_seniority[level]  # type: ignore[index]
        for lens in lenses
    )
    junior_terms = (
        _merge(field(lambda lens: lens.terms_to_explain_for_juniors), weights, 6)
        if level == "junior"
        else []
    )
    parts = [
        "Mentor perspective (use it to decide what matters, what to ask and what to warn about; "
        "it describes a way of thinking, not a person):",
        perspective,
        "What this perspective prioritises, most important first:",
        _bullets(_merge(field(lambda lens: lens.priorities), weights, MAX_PRIORITIES)),
        "Questions this perspective tends to ask when context is missing:",
        _bullets(_merge(field(lambda lens: lens.questions_to_ask), weights, MAX_QUESTIONS)),
        "Common ways things go wrong:",
        _bullets(_merge(field(lambda lens: lens.common_failure_modes), weights, MAX_FAILURE_MODES)),
    ]
    red_flags = _merge(field(lambda lens: lens.red_flags), weights, MAX_RED_FLAGS)
    if red_flags:
        parts += ["Call out these when you see them:", _bullets(red_flags)]
    parts += [f"Depth for this user (seniority: {level}):", depth]
    if junior_terms:
        parts += ["Explain these terms briefly when you use them:", _bullets(junior_terms)]
    out_of_scope = _merge(field(lambda lens: lens.out_of_scope), weights, 4)
    parts += [
        "Outside the scope of this perspective (give general information only and redirect):",
        _bullets(out_of_scope),
    ]
    return "\n".join(parts)
