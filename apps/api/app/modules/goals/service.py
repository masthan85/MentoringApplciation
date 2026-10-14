"""Goals (with Goal Attainment Scaling), milestones and commitments."""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.modules.audit import service as audit
from app.modules.goals.models import Commitment, Goal, GoalScore, Milestone
from app.modules.goals.schemas import (
    CommitmentIn,
    CommitmentOut,
    CommitmentPatch,
    GasLevels,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    MilestoneIn,
    MilestoneOut,
    SuggestIn,
)
from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.prompts import registry as prompts

MAX_ACTIVE_GOALS = 5
MAX_OPEN_COMMITMENTS = 12
GAS_PROMPT = ("gas_suggestion", 1)
GAS_LABELS = {
    -2: "much less than expected",
    -1: "somewhat less than expected",
    0: "expected outcome",
    1: "somewhat better than expected",
    2: "much better than expected",
}

GAS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["minus_two", "minus_one", "zero", "plus_one", "plus_two"],
    "properties": {
        k: {"type": "string"} for k in ("minus_two", "minus_one", "zero", "plus_one", "plus_two")
    },
}


def to_out(goal: Goal, milestones: list[Milestone] | None = None) -> GoalOut:
    levels: dict[str, str] = dict(goal.gas_levels)
    return GoalOut(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        baseline=goal.baseline,
        target_date=goal.target_date,
        status=goal.status,
        levels=levels,
        baseline_score=goal.baseline_score,
        current_score=goal.current_score,
        current_level_text=levels.get(str(goal.current_score), ""),
        created_at=goal.created_at,
        milestones=[MilestoneOut.model_validate(m) for m in milestones or []],
    )


async def get_goal(session: AsyncSession, user_id: UUID, goal_id: UUID) -> Goal:
    goal = (
        await session.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    ).scalar_one_or_none()
    if goal is None:
        raise NotFound("Goal not found")
    return goal


async def create_goal(session: AsyncSession, user_id: UUID, body: GoalCreate) -> Goal:
    active = (
        await session.execute(
            select(func.count())
            .select_from(Goal)
            .where(Goal.user_id == user_id, Goal.status == "active")
        )
    ).scalar_one()
    if active >= MAX_ACTIVE_GOALS:
        raise AppError(
            f"You can have up to {MAX_ACTIVE_GOALS} active goals. Pause or finish one first; focus is how goals get done."
        )
    goal = Goal(
        user_id=user_id,
        title=body.title,
        description=body.description,
        baseline=body.baseline,
        target_date=body.target_date,
        gas_levels=body.levels.as_dict(),
        baseline_score=body.baseline_score,
        current_score=body.baseline_score,
    )
    session.add(goal)
    await session.flush()
    session.add(
        GoalScore(user_id=user_id, goal_id=goal.id, score=body.baseline_score, source="baseline")
    )
    await audit.record(
        session, "goal.create", user_id=user_id, resource_type="goal", resource_id=str(goal.id)
    )
    await session.flush()
    return goal


async def update_goal(
    session: AsyncSession, user_id: UUID, goal_id: UUID, body: GoalUpdate
) -> Goal:
    goal = await get_goal(session, user_id, goal_id)
    changes = body.model_dump(exclude_unset=True, exclude={"levels"})
    for name, value in changes.items():
        if value is not None or name == "target_date":
            setattr(goal, name, value)
    if body.levels is not None:
        goal.gas_levels = body.levels.as_dict()
    if goal.status == "active":
        active = (
            await session.execute(
                select(func.count())
                .select_from(Goal)
                .where(Goal.user_id == user_id, Goal.status == "active", Goal.id != goal_id)
            )
        ).scalar_one()
        if active >= MAX_ACTIVE_GOALS:
            raise AppError(f"You can have up to {MAX_ACTIVE_GOALS} active goals.")
    await session.flush()
    await session.refresh(goal)
    return goal


async def record_score(
    session: AsyncSession,
    user_id: UUID,
    goal: Goal,
    score: int,
    source: str,
    note: str | None = None,
) -> None:
    session.add(GoalScore(user_id=user_id, goal_id=goal.id, score=score, source=source, note=note))
    goal.current_score = score
    if score >= 0 and goal.status == "active" and source == "manual":
        pass  # reaching the expected outcome is celebrated by the user marking the goal achieved
    await session.flush()


async def list_goals(
    session: AsyncSession, user_id: UUID, *, include_inactive: bool = False
) -> list[GoalOut]:
    query = select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at)
    if not include_inactive:
        query = query.where(Goal.status.in_(("active", "paused")))
    goals = (await session.execute(query)).scalars().all()
    milestones = (
        (
            await session.execute(
                select(Milestone)
                .where(Milestone.user_id == user_id)
                .order_by(Milestone.due_date.nulls_last(), Milestone.created_at)
            )
        )
        .scalars()
        .all()
    )
    by_goal: dict[UUID, list[Milestone]] = {}
    for milestone in milestones:
        by_goal.setdefault(milestone.goal_id, []).append(milestone)
    return [to_out(g, by_goal.get(g.id, [])) for g in goals]


async def add_milestone(
    session: AsyncSession, user_id: UUID, goal_id: UUID, body: MilestoneIn
) -> Milestone:
    await get_goal(session, user_id, goal_id)
    milestone = Milestone(
        user_id=user_id, goal_id=goal_id, title=body.title, due_date=body.due_date
    )
    session.add(milestone)
    await session.flush()
    return milestone


async def set_milestone_done(
    session: AsyncSession, user_id: UUID, milestone_id: UUID, done: bool
) -> Milestone:
    milestone = (
        await session.execute(
            select(Milestone).where(Milestone.id == milestone_id, Milestone.user_id == user_id)
        )
    ).scalar_one_or_none()
    if milestone is None:
        raise NotFound("Milestone not found")
    milestone.status = "done" if done else "open"
    milestone.done_at = datetime.now(UTC) if done else None
    await session.flush()
    return milestone


# ---- commitments ----------------------------------------------------------------------


async def _check_links(
    session: AsyncSession, user_id: UUID, goal_id: UUID | None, milestone_id: UUID | None
) -> None:
    if goal_id:
        await get_goal(session, user_id, goal_id)
    if (
        milestone_id
        and (
            await session.execute(
                select(Milestone.id).where(
                    Milestone.id == milestone_id, Milestone.user_id == user_id
                )
            )
        ).first()
        is None
    ):
        raise NotFound("Milestone not found")


async def count_open(session: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Commitment)
                .where(Commitment.user_id == user_id, Commitment.status == "open")
            )
        ).scalar_one()
    )


async def create_commitment(
    session: AsyncSession,
    user_id: UUID,
    body: CommitmentIn,
    *,
    source: str = "user",
    status: str = "open",
) -> Commitment:
    await _check_links(session, user_id, body.goal_id, body.milestone_id)
    if status == "open" and await count_open(session, user_id) >= MAX_OPEN_COMMITMENTS:
        raise AppError(
            f"You already have {MAX_OPEN_COMMITMENTS} open commitments. Finish or drop some before adding more."
        )
    commitment = Commitment(
        user_id=user_id,
        goal_id=body.goal_id,
        milestone_id=body.milestone_id,
        title=body.title,
        due_date=body.due_date,
        status=status,
        source=source,
    )
    session.add(commitment)
    await session.flush()
    return commitment


async def get_commitment(session: AsyncSession, user_id: UUID, commitment_id: UUID) -> Commitment:
    row = (
        await session.execute(
            select(Commitment).where(Commitment.id == commitment_id, Commitment.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Commitment not found")
    return row


def apply_status(commitment: Commitment, status: str) -> None:
    commitment.status = status
    commitment.completed_at = datetime.now(UTC) if status in ("done", "partial") else None


async def patch_commitment(
    session: AsyncSession, user_id: UUID, commitment_id: UUID, body: CommitmentPatch
) -> Commitment:
    commitment = await get_commitment(session, user_id, commitment_id)
    changes = body.model_dump(exclude_unset=True)
    status = changes.pop("status", None)
    for name, value in changes.items():
        setattr(commitment, name, value)
    if status:
        apply_status(commitment, status)
    await session.flush()
    return commitment


async def list_commitments(
    session: AsyncSession, user_id: UUID, *, status: str | None = None, limit: int = 100
) -> list[Commitment]:
    query = select(Commitment).where(Commitment.user_id == user_id)
    if status:
        query = query.where(Commitment.status == status)
    rows = await session.execute(
        query.order_by(Commitment.due_date.nulls_last(), Commitment.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


def commitment_out(row: Commitment) -> CommitmentOut:
    return CommitmentOut.model_validate(row)


# ---- GAS suggestion -------------------------------------------------------------------


async def suggest_levels(body: SuggestIn) -> GasLevels:
    prompt = (
        f"<goal>{body.title}</goal>\n<where_they_are_now>{body.baseline or 'not stated'}</where_they_are_now>\n"
        f"<what_they_are_aiming_for>{body.target or 'not stated'}</what_they_are_aiming_for>"
    )
    try:
        result = await current_gateway().complete(
            "chat_small",
            CompletionRequest(
                system=prompts.load(*GAS_PROMPT),
                messages=[Message("user", prompt)],
                response_schema=GAS_SCHEMA,
                tags={"purpose": "gas_suggestion"},
            ),
        )
    except LLMError as exc:
        raise AppError("Could not suggest levels right now. You can write them yourself.") from exc
    levels = parse_structured(result.text, GasLevels)
    if levels is None:
        raise AppError("Could not suggest levels right now. You can write them yourself.")
    return levels


# ---- summary for the mentoring prompt -----------------------------------------------------


async def prompt_summary(session: AsyncSession, user_id: UUID, *, today: date | None = None) -> str:
    """Active goals and open commitments, always shown to the mentor. Compact and factual."""
    today = today or datetime.now(UTC).date()
    goals = (
        (
            await session.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.status == "active")
                .order_by(Goal.created_at)
            )
        )
        .scalars()
        .all()
    )
    commitments = (
        (
            await session.execute(
                select(Commitment)
                .where(Commitment.user_id == user_id, Commitment.status == "open")
                .order_by(Commitment.due_date.nulls_last())
                .limit(6)
            )
        )
        .scalars()
        .all()
    )
    lines: list[str] = []
    for goal in goals:
        label = GAS_LABELS[goal.current_score]
        due = f", target {goal.target_date.isoformat()}" if goal.target_date else ""
        lines.append(
            f"- Goal: {goal.title} (now scored {goal.current_score:+d}, {label}{due}). Expected outcome: {goal.gas_levels.get('0', '')}"
        )
    for commitment in commitments:
        if commitment.due_date:
            state = "overdue" if commitment.due_date < today else "due"
            when = f", {state} {commitment.due_date.isoformat()}"
        else:
            when = ""
        lines.append(f"- Commitment: {commitment.title}{when}")
    return "\n".join(lines)
