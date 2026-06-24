import logging, asyncio
from typing import Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

logger = logging.getLogger("epms.common.redis")

client: Optional[aioredis.Redis] = None

async def create_redis(cfg: dict) -> Optional[aioredis.Redis]:
    global client
    if aioredis is None:
        logger.warning("redis.asyncio not installed")
        return None
    try:
        client = aioredis.Redis(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 6379),
            password=cfg.get("password", None) or None,
            db=0, decode_responses=True,
            socket_connect_timeout=3, socket_timeout=3,
            retry_on_timeout=False,
        )
        await asyncio.wait_for(client.ping(), timeout=5)
        logger.info("Redis connected")
        return client
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None

async def close_redis():
    global client
    if client:
        await client.close()
        client = None