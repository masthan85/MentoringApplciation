import uuid
from typing import Any, Literal

from fastapi import APIRouter, Response

from app.core.deps import RequestCtx
from app.modules.goals import checkin, reviews, service, today
from app.modules.goals.schemas import (
    BaselineIn,
    CheckInComplete,
    CheckInOut,
    CommitmentIn,
    CommitmentOut,
    CommitmentPatch,
    GasLevels,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    MilestoneIn,
    MilestoneOut,
    QuarterlyIn,
    ReviewOut,
    ScoreIn,
    SuggestIn,
)

router = APIRouter(tags=["progress"])


@router.get("/v1/today")
async def read_today(ctx: RequestCtx) -> dict[str, Any]:
    return await today.build_today(ctx.session, ctx.user.id)


# ---- goals -----------------------------------------------------------------------------


@router.post("/v1/goals/suggest-levels", response_model=GasLevels)
async def suggest_levels(body: SuggestIn, _: RequestCtx) -> GasLevels:
    return await service.suggest_levels(body)


@router.get("/v1/goals", response_model=list[GoalOut])
async def list_goals(ctx: RequestCtx, include_inactive: bool = False) -> list[GoalOut]:
    return await service.list_goals(ctx.session, ctx.user.id, include_inactive=include_inactive)


@router.post("/v1/goals", response_model=GoalOut, status_code=201)
async def create_goal(body: GoalCreate, ctx: RequestCtx) -> GoalOut:
    return service.to_out(await service.create_goal(ctx.session, ctx.user.id, body))


@router.patch("/v1/goals/{goal_id}", response_model=GoalOut)
async def update_goal(goal_id: uuid.UUID, body: GoalUpdate, ctx: RequestCtx) -> GoalOut:
    return service.to_out(await service.update_goal(ctx.session, ctx.user.id, goal_id, body))


@router.post("/v1/goals/{goal_id}/scores", response_model=GoalOut)
async def score_goal(goal_id: uuid.UUID, body: ScoreIn, ctx: RequestCtx) -> GoalOut:
    goal = await service.get_goal(ctx.session, ctx.user.id, goal_id)
    await service.record_score(ctx.session, ctx.user.id, goal, body.score, "manual", body.note)
    return service.to_out(goal)


@router.delete("/v1/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: uuid.UUID, ctx: RequestCtx) -> Response:
    goal = await service.get_goal(ctx.session, ctx.user.id, goal_id)
    await ctx.session.delete(goal)
    return Response(status_code=204)


@router.post("/v1/goals/{goal_id}/milestones", response_model=MilestoneOut, status_code=201)
async def add_milestone(goal_id: uuid.UUID, body: MilestoneIn, ctx: RequestCtx) -> MilestoneOut:
    return MilestoneOut.model_validate(
        await service.add_milestone(ctx.session, ctx.user.id, goal_id, body)
    )


@router.post("/v1/milestones/{milestone_id}/done", response_model=MilestoneOut)
async def milestone_done(
    milestone_id: uuid.UUID, ctx: RequestCtx, done: bool = True
) -> MilestoneOut:
    return MilestoneOut.model_validate(
        await service.set_milestone_done(ctx.session, ctx.user.id, milestone_id, done)
    )


# ---- commitments ----------------------------------------------------------------------------


@router.get("/v1/commitments", response_model=list[CommitmentOut])
async def list_commitments(
    ctx: RequestCtx,
    status: Literal["proposed", "open", "done", "partial", "missed", "dropped"] | None = None,
) -> list[CommitmentOut]:
    return [
        service.commitment_out(c)
        for c in await service.list_commitments(ctx.session, ctx.user.id, status=status)
    ]


@router.post("/v1/commitments", response_model=CommitmentOut, status_code=201)
async def create_commitment(body: CommitmentIn, ctx: RequestCtx) -> CommitmentOut:
    return service.commitment_out(await service.create_commitment(ctx.session, ctx.user.id, body))


@router.patch("/v1/commitments/{commitment_id}", response_model=CommitmentOut)
async def patch_commitment(
    commitment_id: uuid.UUID, body: CommitmentPatch, ctx: RequestCtx
) -> CommitmentOut:
    return service.commitment_out(
        await service.patch_commitment(ctx.session, ctx.user.id, commitment_id, body)
    )


@router.delete("/v1/commitments/{commitment_id}", status_code=204)
async def delete_commitment(commitment_id: uuid.UUID, ctx: RequestCtx) -> Response:
    await ctx.session.delete(await service.get_commitment(ctx.session, ctx.user.id, commitment_id))
    return Response(status_code=204)


# ---- check-ins ------------------------------------------------------------------------------------


async def _check_in_out(ctx: RequestCtx, row: Any, safety: str | None = None) -> CheckInOut:
    open_rows = await service.list_commitments(ctx.session, ctx.user.id, status="open")
    return CheckInOut(
        id=row.id,
        week_start=row.week_start,
        status=row.status,
        open_commitments=[service.commitment_out(c) for c in open_rows]
        if row.status == "due"
        else [],
        reply=row.reply,
        safety_message=safety,
    )


@router.get("/v1/check-ins/current", response_model=CheckInOut)
async def current_check_in(ctx: RequestCtx) -> CheckInOut:
    return await _check_in_out(ctx, await checkin.current_check_in(ctx.session, ctx.user))


@router.post("/v1/check-ins/{check_in_id}/complete", response_model=CheckInOut)
async def complete_check_in(
    check_in_id: uuid.UUID, body: CheckInComplete, ctx: RequestCtx
) -> CheckInOut:
    row = await checkin.get_check_in(ctx.session, ctx.user.id, check_in_id)
    row, safety = await checkin.complete_check_in(ctx.session, ctx.user, row, body)
    return await _check_in_out(ctx, row, safety)


@router.post("/v1/check-ins/{check_in_id}/skip", response_model=CheckInOut)
async def skip_check_in(check_in_id: uuid.UUID, ctx: RequestCtx) -> CheckInOut:
    row = await checkin.get_check_in(ctx.session, ctx.user.id, check_in_id)
    if row.status == "due":
        row.status = "skipped"
    return await _check_in_out(ctx, row)


# ---- reviews ------------------------------------------------------------------------------------------


@router.post("/v1/baseline", response_model=dict[str, float])
async def baseline(body: BaselineIn, ctx: RequestCtx) -> dict[str, float]:
    review = await reviews.record_baseline(ctx.session, ctx.user.id, body.self_efficacy)
    return {"self_efficacy": review.scores["self_efficacy"]}


@router.get("/v1/reviews", response_model=list[ReviewOut])
async def list_reviews(
    ctx: RequestCtx, kind: Literal["baseline", "monthly", "quarterly"] | None = None
) -> list[ReviewOut]:
    return [
        ReviewOut.model_validate(r)
        for r in await reviews.list_reviews(ctx.session, ctx.user.id, kind)
    ]


@router.get("/v1/reviews/quarterly/status")
async def quarterly_status(ctx: RequestCtx) -> dict[str, Any]:
    return await reviews.quarterly_status(ctx.session, ctx.user.id)


@router.post("/v1/reviews/quarterly", response_model=ReviewOut, status_code=201)
async def submit_quarterly(body: QuarterlyIn, ctx: RequestCtx) -> ReviewOut:
    return ReviewOut.model_validate(await reviews.submit_quarterly(ctx.session, ctx.user.id, body))


@router.get("/v1/reviews/trends")
async def read_trends(ctx: RequestCtx) -> dict[str, Any]:
    return await reviews.trends(ctx.session, ctx.user.id)
