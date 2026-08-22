import uuid
from uuid import UUID
from app.db.engine import get_pool
from app.clients.embeddings import get_embedding


async def handle_save_memory(params: dict, user: str):
    text = params.get("text")
    if not text or not str(text).strip():
        return {"error": "text is required"}

    conversation_id = params.get("conversation_id") or None
    if conversation_id:
        try:
            UUID(conversation_id)
        except ValueError:
            return {"error": f"Invalid conversation_id format: {conversation_id}"}
    tags = params.get("tags", [])

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Auto-vincular a la conversación más reciente del usuario si no se proporciona
        if not conversation_id:
            row = await conn.fetchrow(
                'SELECT id FROM conversations WHERE "user" = $1 ORDER BY updated_at DESC LIMIT 1',
                user,
            )
            if row:
                conversation_id = row["id"]

        embedding_list = await get_embedding(str(text))
        embedding = "[" + ",".join(str(x) for x in embedding_list) + "]"

        memory_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding, conversation_id, tags)
            VALUES($1, $2, $3, $4::vector, $5, $6);
            """,
            memory_id,
            user,
            text,
            embedding,
            conversation_id,
            tags,
        )

        # Actualizar updated_at de la conversación vinculada
        if conversation_id:
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )

    return {"memory_id": str(memory_id)}
