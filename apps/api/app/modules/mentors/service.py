import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.audit import service as audit
from app.modules.goals.models import Commitment, Goal
from app.modules.identity.service import consent_state
from app.modules.mentors.models import MentorBrief, MentorLink, SessionNote
from app.modules.mentors.schemas import BriefContent, BriefSection, InviteIn, NoteIn

INVITE_DAYS = 14


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def invite(session: AsyncSession, mentee: Any, body: InviteIn) -> tuple[MentorLink, str]:
    if not (await consent_state(session, mentee.id)).get("mentor_sharing"):
        raise Forbidden("Turn on sharing with a human mentor in your privacy settings first")
    if body.mentor_email.lower() == (mentee.email or "").lower():
        raise Conflict("You cannot invite yourself")
    token = secrets.token_urlsafe(32)
    link = MentorLink(
        mentee_id=mentee.id,
        mentor_email=body.mentor_email.lower(),
        token_hash=hash_token(token),
        scopes=body.scopes.model_dump(),
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_DAYS),
    )
    session.add(link)
    await session.flush()
    await audit.record(
        session,
        "mentor.invited",
        user_id=mentee.id,
        resource_type="mentor_link",
        resource_id=str(link.id),
        metadata={"scopes": link.scopes},
    )
    return link, token


def invite_url(token: str) -> str:
    return f"{get_settings().public_web_url}/mentor/accept?token={token}"


async def accept(session: AsyncSession, token: str) -> UUID:
    try:
        result = await session.execute(
            text("SELECT mentor_accept_invite(:h)"), {"h": hash_token(token)}
        )
    except DBAPIError as exc:
        raise NotFound("This invitation is not valid. Ask the mentee to send a new one.") from exc
    return result.scalar_one()  # type: ignore[no-any-return]


async def my_links(session: AsyncSession) -> list[MentorLink]:
    rows = await session.execute(
        select(MentorLink)
        .where(MentorLink.status != "ended")
        .order_by(MentorLink.created_at.desc())
    )
    return list(rows.scalars())


async def get_link(session: AsyncSession, link_id: UUID, *, mentee_id: UUID) -> MentorLink:
    link = (
        await session.execute(
            select(MentorLink).where(MentorLink.id == link_id, MentorLink.mentee_id == mentee_id)
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFound("Mentor link not found")
    return link


async def end_link(session: AsyncSession, link: MentorLink) -> None:
    """Revoke access at once. Briefs shared with the mentor are deleted; session notes stay with the mentee."""
    link.status = "ended"
    link.ended_at = datetime.now(UTC)
    for brief in (
        await session.execute(select(MentorBrief).where(MentorBrief.link_id == link.id))
    ).scalars():
        await session.delete(brief)
    await audit.record(
        session,
        "mentor.link_ended",
        user_id=link.mentee_id,
        resource_type="mentor_link",
        resource_id=str(link.id),
    )


async def build_brief(session: AsyncSession, link: MentorLink) -> BriefContent:
    """A starting point made only from goals and commitments the mentee chose to share.

    It never includes memories, conversation text, check-in blockers, writing samples or
    anything sensitive. The mentee edits it and must approve it before the mentor sees anything.
    """
    sections: list[BriefSection] = []
    scopes = link.scopes
    if scopes.get("goals"):
        goals = (
            (
                await session.execute(
                    select(Goal).where(Goal.user_id == link.mentee_id, Goal.status == "active")
                )
            )
            .scalars()
            .all()
        )
        lines = [
            f"- {g.title}: now '{g.gas_levels.get(str(g.current_score), '')}' "
            f"(started at '{g.gas_levels.get(str(g.baseline_score), '')}')"
            for g in goals
        ]
        sections.append(BriefSection(title="Goals", text="\n".join(lines) or "No goals set yet."))
    if scopes.get("commitments"):
        rows = (
            (
                await session.execute(
                    select(Commitment)
                    .where(Commitment.user_id == link.mentee_id)
                    .order_by(Commitment.created_at.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        lines = [f"- {c.title} ({c.status})" for c in rows if c.status != "proposed"]
        sections.append(
            BriefSection(title="Recent commitments", text="\n".join(lines) or "None yet.")
        )
    sections.append(BriefSection(title="What I would like to discuss", text=""))
    return BriefContent(sections=sections)


async def create_brief(session: AsyncSession, link: MentorLink) -> MentorBrief:
    if link.status != "active":
        raise Conflict("The mentor has not accepted yet")
    brief = MentorBrief(
        link_id=link.id,
        mentee_id=link.mentee_id,
        content=(await build_brief(session, link)).model_dump(),
    )
    session.add(brief)
    await session.flush()
    await session.refresh(brief)
    return brief


async def get_brief(session: AsyncSession, brief_id: UUID) -> MentorBrief:
    brief = (
        await session.execute(select(MentorBrief).where(MentorBrief.id == brief_id))
    ).scalar_one_or_none()
    if brief is None:
        raise NotFound("Brief not found")
    return brief


async def edit_brief(session: AsyncSession, brief: MentorBrief, content: BriefContent) -> None:
    brief.content = content.model_dump()
    brief.status = "draft"  # any change needs approving again
    brief.approved_at = None
    brief.updated_at = datetime.now(UTC)


async def approve_brief(session: AsyncSession, brief: MentorBrief) -> None:
    brief.status = "approved"
    brief.approved_at = datetime.now(UTC)
    brief.updated_at = brief.approved_at
    await audit.record(
        session,
        "mentor.brief_approved",
        user_id=brief.mentee_id,
        resource_type="mentor_brief",
        resource_id=str(brief.id),
    )


async def view_brief(session: AsyncSession, link_id: UUID) -> dict[str, Any]:
    result = await session.execute(text("SELECT mentor_view_brief(:l)"), {"l": link_id})
    content = result.scalar_one()
    if content is None:
        raise NotFound("No approved brief has been shared yet")
    return content  # type: ignore[no-any-return]


async def add_note(session: AsyncSession, link_id: UUID, body: NoteIn) -> UUID:
    import json

    actions = [
        {"title": a.title, "due_date": a.due_date.isoformat() if a.due_date else ""}
        for a in body.actions
    ]
    try:
        result = await session.execute(
            text("SELECT mentor_add_session_note(:l, :s, CAST(:a AS jsonb))"),
            {"l": link_id, "s": body.summary, "a": json.dumps(actions)},
        )
    except DBAPIError as exc:
        raise NotFound("No active mentoring link with that id") from exc
    return result.scalar_one()  # type: ignore[no-any-return]


async def list_notes(session: AsyncSession) -> list[SessionNote]:
    rows = await session.execute(select(SessionNote).order_by(SessionNote.created_at.desc()))
    return list(rows.scalars())
