import pytest
from app.db.engine import get_pool
from app.mcp.tools.get_conversation_history import handle_get_conversation_history


@pytest.mark.asyncio
async def test_get_conversation_history_respects_user():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        user = "history_test@testdomain.com"
        cid = (await conn.fetchval(
            """
            INSERT INTO conversations(id, "user", name, updated_at)
            VALUES(gen_random_uuid(), $1, 'HistoryTest', NOW()) RETURNING id;
            """,
            user,
        ))

        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding, conversation_id)
            VALUES(gen_random_uuid(), $1, 'Hello from user', NULL, $2),
                  (gen_random_uuid(), $1, 'Hi there from assistant', NULL, $2);
            """,
            user,
            cid,
        )

        result = await handle_get_conversation_history(
            {"conversation_id": str(cid)},
            user,
        )

        texts = [m["text"] for m in result["memories"]]
        assert any("Hello" in t for t in texts)
        assert any("Hi there" in t for t in texts)


@pytest.mark.asyncio
async def test_get_conversation_history_isolated():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        owner = "owner@testdomain.com"
        cid = (await conn.fetchval(
            """
            INSERT INTO conversations(id, "user", name, updated_at)
            VALUES(gen_random_uuid(), $1, 'Owned', NOW()) RETURNING id;
            """,
            owner,
        ))

        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding, conversation_id)
            VALUES(gen_random_uuid(), $1, 'Secret memory', NULL, $2);
            """,
            owner,
            cid,
        )

        result = await handle_get_conversation_history(
            {"conversation_id": str(cid)},
            "other@testdomain.com"
        )

        assert len(result["memories"]) == 0
