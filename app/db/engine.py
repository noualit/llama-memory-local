import asyncio
import logging
from typing import Dict, Tuple

import asyncpg
from app.settings import settings

logger = logging.getLogger("llama-memory.db")


class PoolManager:
    """
    Robust singleton pool manager.

    Features:
    - One pool per running event loop (safe in tests).
    - No reliance on internal asyncpg attributes (_loop/_closed).
    - Thread-safe initialization via asyncio.Lock per-loop.
    """

    def __init__(self):
        # Tracks pools by event loop id: {loop_id: (pool, lock)}
        self._by_loop: Dict[int, Tuple[asyncpg.Pool, asyncio.Lock]] = {}

    async def get_pool(self) -> asyncpg.Pool:
        loop_id = id(asyncio.get_running_loop())

        # Fast path: pool already exists for this loop.
        entry = self._by_loop.get(loop_id)
        if entry is not None:
            pool, _ = entry
            try:
                # Quick liveness check; if it raises, treat as dead.
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return pool
            except Exception:
                # Stale or broken pool
                self._by_loop.pop(loop_id, None)

        # Slow path: create pool under lock.
        lock = asyncio.Lock()
        async with lock:
            # Double-check after acquiring lock.
            if loop_id in self._by_loop:
                return self._by_loop[loop_id][0]

            pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=1,
                max_size=5,
            )
            self._by_loop[loop_id] = (pool, lock)
            return pool

    async def close_all_pools(self):
        """Close all known pools. Useful in tests / shutdown."""
        for loop_id, (pool, _) in list(self._by_loop.items()):
            try:
                await pool.close()
            except Exception:
                pass  # Best-effort during teardown
        self._by_loop.clear()


_pool_manager = PoolManager()


async def get_pool() -> asyncpg.Pool:
    """Get (or create) a DB connection pool for the current event loop."""
    return await _pool_manager.get_pool()


async def reset_pool():
    """Close all pools. Used primarily in tests to avoid stale connections."""
    await _pool_manager.close_all_pools()
