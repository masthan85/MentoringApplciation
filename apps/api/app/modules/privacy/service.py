from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent
from app.modules.fingerprint import service as fingerprint
from app.modules.identity.service import consent_state
from app.modules.memory import service as memory_service

# Tables whose rows belong to one user, exported as they are (row-level security limits them to
# the caller). Columns that are encrypted, or are vectors, are handled separately or left out.
PLAIN_TABLES = (
    "profiles",
    "persona_configs",
    "conversations",
    "messages",
    "goals",
    "goal_scores",
    "milestones",
    "commitments",
    "check_ins",
    "reviews",
    "notifications",
    "drafts",
    "feedback",
    "style_profiles",
    "practice_sessions",
    "mentor_links",
    "mentor_briefs",
    "session_notes",
    "subscriptions",
)
OMIT_COLUMNS = {"token_hash", "stripe_customer_id", "stripe_subscription_id", "embedding"}


async def _rows(session: AsyncSession, table: str) -> list[dict[str, Any]]:
    # The table name comes from the fixed list above, never from a request.
    result = await session.execute(text(f"SELECT to_jsonb(t) AS row FROM {table} t"))  # noqa: S608
    rows = []
    for (row,) in result.all():
        rows.append({k: v for k, v in row.items() if k not in OMIT_COLUMNS})
    return rows


async def export_all(session: AsyncSession, user_id: UUID, email: str | None) -> dict[str, Any]:
    document: dict[str, Any] = {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "account": {"id": str(user_id), "email": email},
        "consents": await consent_state(session, user_id),
        "memories": [
            memory_service.present(m) for m in await memory_service.list_memories(session, user_id)
        ],
        "writing_samples": [
            {
                "id": str(s.id),
                "channel": s.channel,
                "origin": s.origin,
                "text": fingerprint.sample_text(s),
                "created_at": s.created_at.isoformat(),
            }
            for s in await fingerprint.list_samples(session, user_id)
        ],
    }
    for table in PLAIN_TABLES:
        document[table] = await _rows(session, table)
    document["access_log"] = [
        access_entry(e) for e in await access_log(session, user_id, limit=1000)
    ]
    return document


def access_entry(event: AuditEvent) -> dict[str, Any]:
    return {
        "at": event.created_at.isoformat(),
        "action": event.action,
        "by": "you" if event.actor_id == event.user_id else "someone else",
        "resource_type": event.resource_type,
    }


async def access_log(session: AsyncSession, user_id: UUID, *, limit: int = 100) -> list[AuditEvent]:
    rows = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.user_id == user_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def delete_account(session: AsyncSession) -> None:
    await session.execute(text("SELECT delete_own_account()"))
