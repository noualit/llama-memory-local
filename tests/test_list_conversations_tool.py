import pytest
from app.db.engine import get_pool
from app.mcp.tools.list_conversations import handle_list_conversations


@pytest.mark.asyncio
async def test_list_conversations_uses_user():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        user = "testuser@testdomain.com"
        cid = (await conn.fetchval(
            """
            INSERT INTO conversations(id, "user", name, updated_at)
            VALUES(gen_random_uuid(), $1, 'Test', NOW()) RETURNING id;
            """,
            user,
        ))

        result = await handle_list_conversations({"limit": 5}, user)

        ids = [c["id"] for c in result["conversations"]]
        assert str(cid) in ids


@pytest.mark.asyncio
async def test_list_conversations_isolated_by_user():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        u1 = "alice@testdomain.com"
        u2 = "bob@testdomain.com"

        await conn.execute(
            """
            INSERT INTO conversations(id, "user", name, updated_at)
            VALUES(gen_random_uuid(), $1, 'Private', NOW());
            """,
            u1,
        )

        result_bob = await handle_list_conversations({"limit": 5}, u2)
        names = [c.get("name") for c in result_bob["conversations"]]
        assert "Private" not in names
