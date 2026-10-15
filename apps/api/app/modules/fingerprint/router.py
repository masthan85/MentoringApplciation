import uuid

from fastapi import APIRouter, Response

from app.core.deps import RequestCtx
from app.modules.fingerprint import service
from app.modules.fingerprint.schemas import SampleIn, SampleOut, StyleProfileOut, VoiceCardIn

router = APIRouter(tags=["fingerprint"])


def _out(sample: object) -> SampleOut:
    text = service.sample_text(sample)  # type: ignore[arg-type]
    return SampleOut(
        id=sample.id,  # type: ignore[attr-defined]
        channel=sample.channel,  # type: ignore[attr-defined]
        origin=sample.origin,  # type: ignore[attr-defined]
        word_count=sample.word_count,  # type: ignore[attr-defined]
        preview=(text[:160] + "…") if len(text) > 160 else text,
        created_at=sample.created_at,  # type: ignore[attr-defined]
    )


@router.post("/v1/writing-samples", response_model=SampleOut, status_code=201)
async def add_sample(body: SampleIn, ctx: RequestCtx) -> SampleOut:
    sample = await service.add_sample(
        ctx.session, ctx.user.id, channel=body.channel, text=body.text, confirm_own=body.confirm_own
    )
    return _out(sample)


@router.get("/v1/writing-samples", response_model=list[SampleOut])
async def list_samples(ctx: RequestCtx) -> list[SampleOut]:
    return [_out(s) for s in await service.list_samples(ctx.session, ctx.user.id)]


@router.delete("/v1/writing-samples/{sample_id}", status_code=204)
async def delete_sample(sample_id: uuid.UUID, ctx: RequestCtx) -> Response:
    await service.delete_sample(ctx.session, ctx.user.id, sample_id)
    return Response(status_code=204)


@router.get("/v1/style-profile", response_model=StyleProfileOut)
async def read_style_profile(ctx: RequestCtx) -> StyleProfileOut:
    profile = await service.get_profile(ctx.session, ctx.user.id)
    if profile is None:
        return StyleProfileOut(
            sample_count=0, features={}, voice_cards={}, voice_card_override=None
        )
    return StyleProfileOut(
        sample_count=profile.sample_count,
        features=profile.features,
        voice_cards=profile.voice_cards,
        voice_card_override=profile.voice_card_override,
    )


@router.put("/v1/style-profile/voice-card", response_model=StyleProfileOut)
async def set_voice_card(body: VoiceCardIn, ctx: RequestCtx) -> StyleProfileOut:
    """Let the user replace the generated description of their style with their own words."""
    profile = await service.set_override(ctx.session, ctx.user.id, body.voice_card)
    return StyleProfileOut(
        sample_count=profile.sample_count,
        features=profile.features,
        voice_cards=profile.voice_cards,
        voice_card_override=profile.voice_card_override,
    )


@router.delete("/v1/style-profile", response_model=dict[str, int])
async def delete_style_profile(ctx: RequestCtx) -> dict[str, int]:
    return {"deleted_samples": await service.delete_profile(ctx.session, ctx.user.id)}
