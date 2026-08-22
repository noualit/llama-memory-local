from app.db.engine import get_pool


async def ensure_schema(pool=None):
    p = pool or await get_pool()
    async with p.acquire() as conn:
        # Enable pgvector extension
        await conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS vector;
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "user" TEXT NOT NULL,
                name TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
            ON conversations ("user", updated_at DESC);
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "user" TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding VECTOR(768),
                conversation_id UUID REFERENCES conversations(id),
                tags TEXT[],
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_user ON memories ("user");
            """
        )

        # HNSW index using cosine distance; adjust dimension if necessary in future
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_embedding
            ON memories USING hnsw (embedding vector_cosine_ops);
            """
        )
