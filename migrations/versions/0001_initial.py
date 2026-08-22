"""initial schema with pgvector support

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-19 (auto)
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension (safe if already exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index(
        "idx_conversations_user_updated",
        "conversations",
        ["user", "updated_at"],
        unique=False,
    )

    # Use a raw column for VECTOR(768) via pgvector
    op.execute(
        """
        CREATE TABLE memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "user" TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding VECTOR(768),
            conversation_id UUID REFERENCES conversations(id),
            tags TEXT[],
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    op.create_index("idx_memories_user", "memories", ["user"], unique=False)

    # HNSW index for cosine similarity (pgvector)
    op.execute(
        """
        CREATE INDEX idx_memories_embedding
        ON memories USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade():
    # Remove indexes
    op.execute("DROP INDEX IF EXISTS idx_memories_embedding")
    op.drop_index("idx_memories_user", table_name="memories")
    op.drop_index("idx_conversations_user_updated", table_name="conversations")

    # Drop tables
    op.drop_table("memories")
    op.drop_table("conversations")

    # Disable extension (if we created it)
    op.execute("DROP EXTENSION IF EXISTS vector")
