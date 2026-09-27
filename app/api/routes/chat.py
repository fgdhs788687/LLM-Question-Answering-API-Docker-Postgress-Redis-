import time

from fastapi import APIRouter, status

from app.api.user_deps import CurrentUser
from app.core.redis import redis_client
from app.database.deps import DbSession
from app.db_models.models import ChatLog
from app.schemas_pydantic.schemas import ChatRequest, ChatResponse
from app.services.llm import LLMProviderDep

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    payload: ChatRequest,
    current_user: CurrentUser,
    provider: LLMProviderDep,
    db: DbSession,
):
    cache_key = f"chat:{payload.question}"

    # ── 1. Try cache ──
    try:
        cached = await redis_client.get(cache_key)
    except Exception:
        cached = None

    if cached:
        log = ChatLog(
            user_id=current_user.id,
            question=payload.question,
            answer=cached,
            model="cache",
            tokens_used=0,
            latency_ms=0,
            cached=True,
        )
        db.add(log)
        await db.commit()
        return ChatResponse(
            answer=cached,
            model="cache",
            tokens_used=0,
            latency_ms=0,
            cached=True,
        )

    # ── 2. Cache miss → LLM ──
    t0 = time.perf_counter()
    result = await provider.generate(payload.question)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # ── 3. Store in Redis for 1 hour ──
    try:
        await redis_client.set(cache_key, result.answer, ex=3600)
    except Exception:
        pass
        
    # ── 4. Log to DB ──
    log = ChatLog(
        user_id=current_user.id,
        question=payload.question,
        answer=result.answer,
        model=result.model,
        tokens_used=result.tokens_used,
        latency_ms=latency_ms,
        cached=False,
    )
    db.add(log)
    await db.commit()

    return ChatResponse(
        answer=result.answer,
        model=result.model,
        tokens_used=result.tokens_used,
        latency_ms=latency_ms,
        cached=False,
    )