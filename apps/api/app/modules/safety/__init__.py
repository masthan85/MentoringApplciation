"""Safety: deterministic rules, fixed messages, output checks."""

from app.modules.safety.messages import (
    CRISIS_MESSAGE,
    CRISIS_MESSAGE_VERSION,
    crisis_message,
    refusal_message,
)
from app.modules.safety.output_checks import Violation, check_output
from app.modules.safety.rules import Risk, RuleHit, scan

__all__ = [
    "CRISIS_MESSAGE",
    "CRISIS_MESSAGE_VERSION",
    "Risk",
    "RuleHit",
    "Violation",
    "check_output",
    "crisis_message",
    "refusal_message",
    "scan",
]
