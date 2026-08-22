import uuid
from app.db.engine import get_pool


async def handle_create_conversation(params: dict, user: str):
    name = params.get("name", "Untitled conversation")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations ("user", name)
            VALUES ($1, $2)
            RETURNING id, name, updated_at;
            """,
            user,
            name,
        )

    return {
        "conversation_id": str(row["id"]),
        "name": row["name"],
        "created_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
