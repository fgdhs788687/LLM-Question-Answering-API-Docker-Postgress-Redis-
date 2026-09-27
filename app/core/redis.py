import redis.asyncio as redis
from app.core.settings import get_settings

settings = get_settings()

redis_client: redis.Redis = redis.from_url(
    str(settings.redis_url),
    decode_responses=True,
)