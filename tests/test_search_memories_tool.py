import pytest
from app.db.engine import get_pool
from app.mcp.tools.search_memories import handle_search_memories


@pytest.mark.asyncio
async def test_search_memories_returns_user_memory():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        user = "rag_test@testdomain.com"
        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding)
            VALUES(gen_random_uuid(), $1, 'I remember RAG test',
                   array_fill(0.0::float8, array[768])::vector(768));
            """,
            user,
        )

        result = await handle_search_memories(
            {"query": "RAG test"},
            user,
        )

        texts = [m["text"] for m in result["memories"]]
        assert any("I remember RAG test" in t for t in texts)


@pytest.mark.asyncio
async def test_search_memories_isolated():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        owner = "owner_rag@testdomain.com"
        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding)
            VALUES(gen_random_uuid(), $1, 'Private RAG memory',
                   array_fill(0.0::float8, array[768])::vector(768));
            """,
            owner,
        )

        result = await handle_search_memories(
            {"query": "RAG"},
            "other_rag@testdomain.com"
        )

        assert len(result["memories"]) == 0
