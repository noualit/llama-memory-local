import pytest
from app.db.engine import get_pool
from app.mcp.tools.save_memory import handle_save_memory


@pytest.mark.asyncio
async def test_save_memory_stores_user_memory():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        user = "save_test@testdomain.com"
        result = await handle_save_memory(
            {"text": "I remember save test memory"},
            user,
        )

        mid = result["memory_id"]
        row = await conn.fetchrow(
            """
            SELECT id, "user", text FROM memories WHERE id = $1;
            """,
            mid,
        )

        assert row is not None
        assert row["user"] == user
