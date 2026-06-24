import logging
from typing import Optional
from fastapi import HTTPException

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger("epms.common.db")

pool: Optional[asyncpg.Pool] = None

async def create_pool(cfg: dict, min_size: int = 2, max_size: int = 10) -> Optional[asyncpg.Pool]:
    global pool
    if asyncpg is None:
        logger.warning("asyncpg not installed")
        return None
    try:
        pool = await asyncpg.create_pool(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 5432),
            user=cfg.get("user", "postgres"),
            password=cfg.get("password", ""),
            database=cfg.get("name", "epms"),
            min_size=min_size,
            max_size=cfg.get("max_connections", max_size),
        )
        logger.info("PostgreSQL pool created")
        return pool
    except Exception as e:
        logger.warning(f"PostgreSQL not available: {e}")
        return None

async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None

async def get_db():
    if pool is None:
        raise HTTPException(503, "Database not available")
    async with pool.acquire() as conn:
        yield conn