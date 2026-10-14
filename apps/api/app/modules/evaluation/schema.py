"""Scenario files for the evaluation suite."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Deterministic: run in every mode, including the CI smoke run with the mock model.
    fixed_reply: str | None = None  # crisis or refusal: the reply must be the fixed one
    lens: str | None = None  # the persona that must be active
    prompt_includes: list[str] = Field(default_factory=list)
    prompt_excludes: list[str] = Field(default_factory=list)
    # Judged against the model's actual reply: full mode only.
    reply_includes_any: list[list[str]] = Field(
        default_factory=list
    )  # each group: at least one word
    reply_excludes: list[str] = Field(default_factory=list)
    max_words: int | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    profile: dict[str, Any] = Field(default_factory=dict)
    persona: list[str] = Field(
        default_factory=list
    )  # pinned lenses, if the scenario is about pinning
    history: list[Turn] = Field(default_factory=list)
    message: str
    classify: dict[str, Any] = Field(
        default_factory=dict
    )  # hints for scripted runs; ignored with real models
    sources: list[str] = Field(default_factory=list)  # slugs of fixture sources to make active
    expect: Expect = Field(default_factory=Expect)
    rubric: list[str] = Field(default_factory=list)  # what a good reply does, for the judge


class SubstancePair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    profile: dict[str, Any] = Field(default_factory=dict)
    message: str
    lens_a: str
    lens_b: str
    max_overlap: float = 0.65  # how alike the two replies' wording may be


class PreservationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    before: str
    after: str
    expect: str = Field(pattern="^(ok|problems)$")
    problem_contains: str | None = None


class FixtureSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    document: str
