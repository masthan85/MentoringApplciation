"""A short, readable description of someone's writing, built from features by template."""

from typing import Any


def _level(value: float, low: float, high: float, labels: tuple[str, str, str]) -> str:
    return labels[0] if value < low else labels[2] if value > high else labels[1]


def describe(features: dict[str, Any]) -> str | None:
    if features.get("insufficient"):
        return None
    mean = features["sentence_len_mean"]
    parts = [
        f"Sentences average about {mean:.0f} words and "
        + _level(
            features["sentence_cv"],
            0.35,
            0.65,
            ("are fairly even in length", "vary in length", "vary a lot, mixing short and long"),
        )
        + ".",
        "Paragraphs are "
        + _level(features["paragraph_len_mean"], 40, 90, ("short", "medium length", "long"))
        + ".",
        "Uses contractions "
        + _level(features["contraction_rate"], 0.5, 2.0, ("rarely", "sometimes", "often"))
        + ".",
    ]
    british = features.get("british_ratio")
    if british is not None:
        parts.append(
            "Spells in British English." if british >= 0.5 else "Spells in American English."
        )
    tone = _level(features["formality"], 0.4, 0.6, ("informal", "neutral", "formal"))
    hedges = _level(
        features["hedging_rate"], 0.4, 1.2, ("rarely hedges", "hedges occasionally", "hedges often")
    )
    passive = _level(
        features["passive_rate"],
        0.05,
        0.15,
        (
            "seldom uses the passive voice",
            "uses the passive voice now and then",
            "often uses the passive voice",
        ),
    )
    parts.append(f"Tone is {tone}; {hedges}, and {passive}.")
    person = _level(
        features["first_person_rate"],
        0.8,
        2.5,
        ("mostly impersonal", "uses first person at times", "writes in the first person often"),
    )
    parts.append(person[0].upper() + person[1:] + ".")
    if features["question_rate"] > 0.1:
        parts.append("Asks questions fairly often.")
    if features["list_rate"] > 0.15:
        parts.append("Likes short lists.")
    parts.append(
        "Vocabulary is "
        + _level(
            features.get("mtld") or 0,
            40,
            75,
            ("plain and repetitive", "moderately varied", "varied"),
        )
        + " and "
        + _level(
            features["technical_rate"],
            3,
            9,
            ("light on jargon", "mixes in technical terms", "technical"),
        )
        + "."
    )
    return " ".join(parts)
