from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.deps import RequestCtx
from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.goals.models import Commitment
from app.modules.mentors import service
from app.modules.mentors.models import MentorBrief
from app.modules.mentors.schemas import (
    AcceptIn,
    BriefContent,
    BriefOut,
    InviteIn,
    InviteOut,
    LinkOut,
    MenteeOut,
    NoteIn,
    NoteOut,
)
from app.modules.subscriptions.entitlements import require_feature

router = APIRouter(tags=["human-mentor"])


class BriefBody(BaseModel):
    content: BriefContent


def _brief(brief: MentorBrief) -> BriefOut:
    return BriefOut.model_validate(brief)


# ---- the mentee's side ---------------------------------------------------------------


@router.get("/v1/mentor-link", response_model=list[LinkOut])
async def list_links(ctx: RequestCtx) -> list[LinkOut]:
    return [
        LinkOut.model_validate(link)
        for link in await service.my_links(ctx.session)
        if link.mentee_id == ctx.user.id
    ]


@router.post("/v1/mentor-link", response_model=InviteOut, status_code=201)
async def invite(body: InviteIn, ctx: RequestCtx) -> InviteOut:
    await require_feature(ctx.session, ctx.user.id, "human_mentor")
    link, token = await service.invite(ctx.session, ctx.user, body)
    await ctx.session.refresh(link)
    return InviteOut(
        **LinkOut.model_validate(link).model_dump(),
        invite_token=token,
        invite_url=service.invite_url(token),
    )


@router.delete("/v1/mentor-link/{link_id}", status_code=204)
async def end_link(link_id: UUID, ctx: RequestCtx) -> Response:
    link = await service.get_link(ctx.session, link_id, mentee_id=ctx.user.id)
    await service.end_link(ctx.session, link)
    return Response(status_code=204)


@router.post("/v1/mentor-link/{link_id}/briefs", response_model=BriefOut, status_code=201)
async def create_brief(link_id: UUID, ctx: RequestCtx) -> BriefOut:
    link = await service.get_link(ctx.session, link_id, mentee_id=ctx.user.id)
    return _brief(await service.create_brief(ctx.session, link))


@router.get("/v1/mentor-link/{link_id}/briefs", response_model=list[BriefOut])
async def list_briefs(link_id: UUID, ctx: RequestCtx) -> list[BriefOut]:
    from sqlalchemy import select

    await service.get_link(ctx.session, link_id, mentee_id=ctx.user.id)
    rows = await ctx.session.execute(
        select(MentorBrief)
        .where(MentorBrief.link_id == link_id)
        .order_by(MentorBrief.created_at.desc())
    )
    return [_brief(b) for b in rows.scalars()]


@router.put("/v1/mentor-briefs/{brief_id}", response_model=BriefOut)
async def edit_brief(brief_id: UUID, body: BriefContent, ctx: RequestCtx) -> BriefOut:
    brief = await service.get_brief(ctx.session, brief_id)
    await service.edit_brief(ctx.session, brief, body)
    return _brief(brief)


@router.post("/v1/mentor-briefs/{brief_id}/approve", response_model=BriefOut)
async def approve_brief(brief_id: UUID, ctx: RequestCtx) -> BriefOut:
    brief = await service.get_brief(ctx.session, brief_id)
    await service.approve_brief(ctx.session, brief)
    return _brief(brief)


@router.get("/v1/session-notes", response_model=list[NoteOut])
async def session_notes(ctx: RequestCtx) -> list[NoteOut]:
    return [
        NoteOut.model_validate(n)
        for n in await service.list_notes(ctx.session)
        if n.mentee_id == ctx.user.id
    ]


async def _proposed(ctx: RequestCtx, commitment_id: UUID) -> Commitment:
    from sqlalchemy import select

    row = (
        await ctx.session.execute(
            select(Commitment).where(
                Commitment.id == commitment_id, Commitment.user_id == ctx.user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Commitment not found")
    if row.status != "proposed":
        raise Conflict("This was not a proposal, or you have already answered it")
    return row


@router.post("/v1/commitments/{commitment_id}/accept")
async def accept_proposal(commitment_id: UUID, ctx: RequestCtx) -> dict[str, str]:
    row = await _proposed(ctx, commitment_id)
    row.status = "open"
    await audit.record(
        ctx.session,
        "commitment.proposal_accepted",
        user_id=ctx.user.id,
        resource_type="commitment",
        resource_id=str(row.id),
    )
    return {"status": "open"}


@router.post("/v1/commitments/{commitment_id}/decline")
async def decline_proposal(commitment_id: UUID, ctx: RequestCtx) -> dict[str, str]:
    row = await _proposed(ctx, commitment_id)
    row.status = "dropped"
    return {"status": "dropped"}


# ---- the mentor's side ---------------------------------------------------------------


@router.post("/v1/mentor/accept", response_model=dict[str, str])
async def accept_invite(body: AcceptIn, ctx: RequestCtx) -> dict[str, str]:
    link_id = await service.accept(ctx.session, body.token)
    return {"link_id": str(link_id)}


@router.get("/v1/mentor/mentees", response_model=list[MenteeOut])
async def my_mentees(ctx: RequestCtx) -> list[MenteeOut]:
    return [
        MenteeOut(link_id=link.id, accepted_at=link.accepted_at, scopes=link.scopes)
        for link in await service.my_links(ctx.session)
        if link.mentor_user_id == ctx.user.id and link.status == "active"
    ]


@router.get("/v1/mentor/mentees/{link_id}/brief", response_model=BriefBody)
async def view_brief(link_id: UUID, ctx: RequestCtx) -> BriefBody:
    return BriefBody(
        content=BriefContent.model_validate(await service.view_brief(ctx.session, link_id))
    )


@router.post("/v1/mentor/mentees/{link_id}/notes", response_model=dict[str, str], status_code=201)
async def add_note(link_id: UUID, body: NoteIn, ctx: RequestCtx) -> dict[str, str]:
    return {"id": str(await service.add_note(ctx.session, link_id, body))}
