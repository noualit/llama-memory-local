from app.db.engine import get_pool


async def handle_list_conversations(params: dict, user: str):
    limit = int(params.get("limit", 50))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.name,
                c.updated_at,
                COUNT(m.id) AS memory_count,
                (ARRAY_AGG(m.text ORDER BY m.created_at DESC))[1] AS last_memory
            FROM conversations c
            LEFT JOIN memories m ON m.conversation_id = c.id
            WHERE c."user" = $1
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT $2;
            """,
            user,
            limit,
        )

    return {
        "conversations": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "memory_count": r["memory_count"],
                "last_memory": r["last_memory"],
            }
            for r in rows
        ]
    }
