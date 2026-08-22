from uuid import UUID
from app.db.engine import get_pool


async def handle_get_conversation_history(params: dict, user: str):
    conversation_id = params.get("conversation_id")
    if not conversation_id:
        return {"error": "conversation_id is required"}

    try:
        UUID(conversation_id)
    except ValueError:
        return {"error": f"Invalid conversation_id format: {conversation_id}"}

    limit = int(params.get("limit", 50))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT text, tags, created_at
            FROM memories
            WHERE conversation_id = $1 AND "user" = $2
            ORDER BY created_at;
            """,
            conversation_id,
            user,
        )

    return {
        "memories": [
            {
                "text": r["text"],
                "tags": r["tags"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }
