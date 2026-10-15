"""Stage 2 routing. Plain rules, no model."""

from dataclasses import dataclass

from app.modules.safety import Risk, crisis_message, refusal_message

LARGE_INTENTS = {"decision", "drafting", "practice", "technical_question", "mentoring"}
SHORT_REPLY_WORDS = 6


@dataclass(frozen=True)
class FixedReply:
    kind: str  # crisis | refusal
    text: str
    reason: str


@dataclass(frozen=True)
class ModelRoute:
    route: str


def combine_risk(rule_risk: Risk, classifier_risk: str) -> Risk:
    from_classifier = {
        "normal": Risk.NORMAL,
        "adjacent_regulated": Risk.ADJACENT_REGULATED,
        "prohibited": Risk.PROHIBITED,
        "crisis": Risk.CRISIS,
    }.get(classifier_risk, Risk.NORMAL)
    return max(rule_risk, from_classifier)


def decide(
    risk: Risk,
    *,
    rule_reason: str | None,
    intent: str,
    text: str,
    kind: str,
    country: str | None = None,
) -> FixedReply | ModelRoute:
    if risk is Risk.CRISIS:
        return FixedReply("crisis", crisis_message(country), rule_reason or "crisis_classifier")
    if risk is Risk.PROHIBITED:
        reason = rule_reason if rule_reason and rule_reason != "regulated_topic" else "other"
        return FixedReply("refusal", refusal_message(reason), reason)
    if kind == "onboarding":
        return ModelRoute("chat_small")
    if intent in ("check_in", "small_talk"):
        return ModelRoute("chat_small")
    if len(text.split()) <= SHORT_REPLY_WORDS and intent not in (
        "decision",
        "drafting",
        "practice",
    ):
        return ModelRoute("chat_small")
    return ModelRoute("chat_large")
