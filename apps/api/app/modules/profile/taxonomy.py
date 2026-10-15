from enum import StrEnum


class RoleFamily(StrEnum):
    DATA_ENGINEER = "data_engineer"
    DATA_ARCHITECT = "data_architect"
    ANALYTICS_ENGINEER = "analytics_engineer"
    ML_AI_ENGINEER = "ml_ai_engineer"
    SOFTWARE_ENGINEER = "software_engineer"
    TECH_LEAD = "tech_lead"
    ENGINEERING_MANAGER = "engineering_manager"
    OTHER = "other"


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class OnboardingStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


# Fields the onboarding conversation must capture before the profile can be confirmed.
REQUIRED_FIELDS = (
    "role_family",
    "seniority",
    "country",
    "stack",
    "goals_summary",
    "current_challenge",
)
