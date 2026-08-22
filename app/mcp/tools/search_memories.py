from app.db.engine import get_pool
from app.clients.embeddings import get_embedding


async def handle_search_memories(params: dict, user: str):
    query = params.get("query", "").strip()
    if not query:
        return {"error": "query is required"}

    limit = int(params.get("limit", 10))
    embedding_list = await get_embedding(query)
    embedding = "[" + ",".join(str(x) for x in embedding_list) + "]"

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT text, 1 - (embedding <=> $1::vector) AS score
            FROM memories
            WHERE "user" = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3;
            """,
            embedding,
            user,
            limit,
        )

    return {
        "memories": [
            {"text": r["text"], "score": float(r["score"])}
            for r in rows
        ]
    }
