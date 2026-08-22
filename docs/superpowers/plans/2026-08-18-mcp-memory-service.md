# MCP Memory Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a FastAPI-based MCP Memory Service providing persistent conversation history and semantic memory for llama-server, consumed via its UI as an MCP server.

**Architecture:**
- FastAPI service exposing /mcp endpoint (port 9001).
- Postgres 16 + pgvector stores conversations, messages, memories, with strict per-user isolation.
- llama-server Qwen on :8080 for chat completions; nomic-embed-text on :8081 for embeddings.

**Tech Stack:**
- Python 3.11 (Miniconda)
- FastAPI, uvicorn
- asyncpg
- httpx
- pydantic-settings
- postgres 16 + pgvector

---

### Task 1: Create project structure and environment config

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/settings.py`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "llama-memory"
version = "0.1.0"
description = "MCP Memory Service for llama-server with persistent history and semantic memory"
requires-python = ">=3.11,<3.12"
dependencies = [
    "fastapi[all]",
    "uvicorn[standard]",
    "asyncpg",
    "httpx",
    "pydantic-settings",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```bash
# Database
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/llamamem"

# Llama-server (LLM)
LLAMA_SERVER_BASE_URL="http://localhost:8080"

# Embedding model (nomic-embed-text via llama-server)
EMBEDDING_MODEL_URL="http://localhost:8081"

# Service
SERVICE_PORT=9001
```

- [ ] **Step 3: Create app/__init__.py**

Empty module file.

- [ ] **Step 4: Implement app/settings.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str
    LLAMA_SERVER_BASE_URL: str
    EMBEDDING_MODEL_URL: str
    SERVICE_PORT: int = 9001


settings = Settings()
```

- [ ] **Step 5: Create tests/test_settings.py**

```python
import os
from app.settings import Settings


def test_settings_loads_from_env():
    # Simulate env presence (for real usage, rely on .env)
    assert hasattr(Settings, "model_config")

    # Ensure known fields exist
    s = Settings()
    assert isinstance(s.DATABASE_URL, str) and len(s.DATABASE_URL) > 0
    assert isinstance(s.LLAMA_SERVER_BASE_URL, str) and len(s.LLAMA_SERVER_BASE_URL) > 0
    assert isinstance(s.EMBEDDING_MODEL_URL, str) and len(s.EMBEDDING_MODEL_URL) > 0
    assert isinstance(s.SERVICE_PORT, int)
```

- [ ] **Step 6: Run test to verify it passes (once .env is set)**

Run: `pytest tests/test_settings.py -v`
Expected: PASS (assuming .env exists with values).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example app/__init__.py app/settings.py tests/test_settings.py
git commit -m "feat: add project structure and settings"
```

---

### Task 2: DB connection and schema creation

**Files:**
- Create: `app/db/engine.py`
- Create: `app/db/schema.py`
- Create: `tests/test_db_engine.py`

- [ ] **Step 1: Implement app/db/engine.py**

```python
from app.settings import settings
import asyncpg


async def get_pool():
    return await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=1,
        max_size=5,
    )
```

- [ ] **Step 2: Implement app/db/schema.py**

```python
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
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID REFERENCES conversations(id),
                "user" TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_user_conv_time
            ON messages ("user", conversation_id, created_at);
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "user" TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding VECTOR(1536),
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
```

- [ ] **Step 3: Create test tests/test_db_engine.py**

```python
import pytest
from app.db.engine import get_pool


@pytest.mark.asyncio
async def test_get_pool_returns_connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval("SELECT 1")
    assert row == 1
```

- [ ] **Step 4: Run test to verify DB connectivity**

Run: `pytest tests/test_db_engine.py -v`
Expected: PASS (if DATABASE_URL is valid and DB reachable).

- [ ] **Step 5: Commit**

```bash
git add app/db/engine.py app/db/schema.py tests/test_db_engine.py
git commit -m "feat: add DB engine and schema creation"
```

---

### Task 3: Core FastAPI app with MCP endpoint

**Files:**
- Create: `app/mcp/endpoint.py`
- Create: `tests/test_mcp_endpoint_smoke.py`

- [ ] **Step 1: Implement app/mcp/endpoint.py**

This module exposes /mcp as the primary MCP entrypoint. It delegates to tool handlers based on JSON payload.

```python
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/mcp")
async def mcp_info():
    return JSONResponse({
        "tools": [
            {
                "name": "list_conversations",
                "description": "List recent conversations for the user."
            },
            {
                "name": "get_conversation_history",
                "description": "Retrieve messages in a specific conversation."
            },
            {
                "name": "search_memories",
                "description": "Search semantically relevant memories."
            },
            {
                "name": "save_memory",
                "description": "Save an important memory from the conversation."
            }
        ]
    })


@router.post("/mcp")
async def mcp_call(request: Request):
    user = request.headers.get("X-User", "").strip()
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or empty X-User header"}
        )

    body = await request.json()
    tool = body.get("tool")
    params = body.get("params", {})

    if tool == "list_conversations":
        from app.mcp.tools.list_conversations import handle_list_conversations
        result = await handle_list_conversations(params, user)
    elif tool == "get_conversation_history":
        from app.mcp.tools.get_conversation_history import handle_get_conversation_history
        result = await handle_get_conversation_history(params, user)
    elif tool == "search_memories":
        from app.mcp.tools.search_memories import handle_search_memories
        result = await handle_search_memories(params, user)
    elif tool == "save_memory":
        from app.mcp.tools.save_memory import handle_save_memory
        result = await handle_save_memory(params, user)
    else:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown tool: {tool}"}
        )

    return JSONResponse(content=result)
```

- [ ] **Step 2: Create test tests/test_mcp_endpoint_smoke.py**

Basic smoke test for /mcp GET to ensure endpoint exists and returns tools.

```python
from fastapi.testclient import TestClient
from app.mcp.endpoint import router as mcp_router
from fastapi import FastAPI


app = FastAPI()
app.include_router(mcp_router)
client = TestClient(app)


def test_mcp_get_returns_tools():
    r = client.get("/mcp")
    assert r.status_code == 200
    data = r.json()
    tool_names = [t["name"] for t in data["tools"]]
    assert "list_conversations" in tool_names
    assert "get_conversation_history" in tool_names
    assert "search_memories" in tool_names
    assert "save_memory" in tool_names


def test_mcp_post_rejects_missing_user_header():
    r = client.post(
        "/mcp",
        json={"tool": "list_conversations", "params": {}},
        headers={},
    )
    assert r.status_code == 401
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_mcp_endpoint_smoke.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/mcp/endpoint.py tests/test_mcp_endpoint_smoke.py
git commit -m "feat: add MCP endpoint with tool list and user header validation"
```

---

### Task 4: Tool – list_conversations

**Files:**
- Create: `app/mcp/tools/__init__.py`
- Create: `app/mcp/tools/list_conversations.py`
- Create: `tests/test_list_conversations_tool.py`

- [ ] **Step 1: Implement app/mcp/tools/__init__.py**

Empty module.

- [ ] **Step 2: Implement app/mcp/tools/list_conversations.py**

```python
from app.db.engine import get_pool


async def handle_list_conversations(params: dict, user: str):
    limit = int(params.get("limit", 50))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, updated_at
            FROM conversations
            WHERE "user" = $1
            ORDER BY updated_at DESC
            LIMIT $2;
            """,
            user,
            limit,
        )

    return {
        "conversations": [
            {
                "id": r["id"],
                "name": r["name"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    }
```

- [ ] **Step 3: Create test tests/test_list_conversations_tool.py**

TDD-style conceptual test that expects to fail until DB seeded.

```python
import pytest
from app.db.engine import get_pool
from app.mcp.tools.list_conversations import handle_list_conversations


@pytest.mark.asyncio
async def test_list_conversations_uses_user():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ensure schema exists
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
        assert cid in ids


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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_list_conversations_tool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mcp/tools/list_conversations.py tests/test_list_conversations_tool.py
git commit -m "feat: add list_conversations MCP tool with user isolation"
```

---

### Task 5: Tool – get_conversation_history

**Files:**
- Create: `app/mcp/tools/get_conversation_history.py`
- Create: `tests/test_get_conversation_history_tool.py`

- [ ] **Step 1: Implement app/mcp/tools/get_conversation_history.py**

```python
from app.db.engine import get_pool


async def handle_get_conversation_history(params: dict, user: str):
    conversation_id = params.get("conversation_id")
    if not conversation_id:
        return {"error": "conversation_id is required"}

    limit = int(params.get("limit", 50))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = $1 AND "user" = $2
            ORDER BY created_at;
            """,
            conversation_id,
            user,
        )

    return {
        "messages": [
            {"role": r["role"], "content": r["content"]}
            for r in rows
        ]
    }
```

- [ ] **Step 2: Create test tests/test_get_conversation_history_tool.py**

```python
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
            INSERT INTO messages(conversation_id, "user", role, content)
            VALUES($1, $2, 'user', 'Hello'), ($1, $2, 'assistant', 'Hi there');
            """,
            cid,
            user,
        )

        result = await handle_get_conversation_history(
            {"conversation_id": str(cid)},
            user,
        )

        roles = [m["role"] for m in result["messages"]]
        assert "user" in roles and "assistant" in roles


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
            INSERT INTO messages(conversation_id, "user", role, content)
            VALUES($1, $2, 'assistant', 'Secret');
            """,
            cid,
            owner,
        )

        result = await handle_get_conversation_history(
            {"conversation_id": str(cid)},
            "other@testdomain.com"
        )

        assert len(result["messages"]) == 0
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_get_conversation_history_tool.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/mcp/tools/get_conversation_history.py tests/test_get_conversation_history_tool.py
git commit -m "feat: add get_conversation_history MCP tool"
```

---

### Task 6: Tool – search_memories (RAG)

**Files:**
- Create: `app/clients/embeddings.py`
- Create: `app/mcp/tools/search_memories.py`
- Create: `tests/test_search_memories_tool.py`

- [ ] **Step 1: Implement app/clients/embeddings.py**

```python
import httpx
from app.settings import settings


async def get_embedding(text: str) -> list[float]:
    payload = {
        "model": "nomic-embed-text",
        "input": text,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.EMBEDDING_MODEL_URL}/v1/embeddings",
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    # Typical shape: {data: [{embedding: [...]}, ...]}
    return data["data"][0]["embedding"]
```

- [ ] **Step 2: Implement app/mcp/tools/search_memories.py**

```python
from app.db.engine import get_pool
from app.clients.embeddings import get_embedding


async def handle_search_memories(params: dict, user: str):
    query = params.get("query", "").strip()
    if not query:
        return {"error": "query is required"}

    limit = int(params.get("limit", 10))
    embedding = await get_embedding(query)

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
```

- [ ] **Step 3: Create test tests/test_search_memories_tool.py**

This test assumes embeddings service is reachable; if not, treat as integration test.

```python
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
        # Insert a known memory with an embedding placeholder.
        # In real use, save_memory will compute this.
        await conn.execute(
            """
            INSERT INTO memories(id, "user", text, embedding)
            VALUES(gen_random_uuid(), $1, 'I remember RAG test', ARRAY[0::float]::vector[:1536]);
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
            VALUES(gen_random_uuid(), $1, 'Private RAG memory', ARRAY[0::float]::vector[:1536]);
            """,
            owner,
        )

        result = await handle_search_memories(
            {"query": "RAG"},
            "other_rag@testdomain.com"
        )

        assert len(result["memories"]) == 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_search_memories_tool.py -v`
Expected: PASS (if embeddings endpoint reachable; otherwise run manually later).

- [ ] **Step 5: Commit**

```bash
git add app/clients/embeddings.py app/mcp/tools/search_memories.py tests/test_search_memories_tool.py
git commit -m "feat: add search_memories MCP tool with PGVector RAG"
```

---

### Task 7: Tool – save_memory

**Files:**
- Create: `app/mcp/tools/save_memory.py`
- Create: `tests/test_save_memory_tool.py`

- [ ] **Step 1: Implement app/mcp/tools/save_memory.py**

```python
import uuid
from app.db.engine import get_pool
from app.clients.embeddings import get_embedding


async def handle_save_memory(params: dict, user: str):
    text = params.get("text")
    if not text or not str(text).strip():
        return {"error": "text is required"}

    conversation_id = params.get("conversation_id") or None
    tags = params.get("tags", [])

    embedding = await get_embedding(str(text))

    memory_id = uuid.uuid4()

    pool = await get_pool()
    async with pool.acquire() as conn:
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

    return {"memory_id": str(memory_id)}
```

- [ ] **Step 2: Create test tests/test_save_memory_tool.py**

```python
import pytest
from app.db.engine import get_pool
from app.mcp.tools.save_memory import handle_save_memory


@pytest.mark.asyncio
async def test_save_memory_stores_user_memory():
    pool = await get_pool()
    async with pool.acquire() as conn:
        from app.db.schema import ensure_schema
        await ensure_schema(pool)

        user = "save_test@testdomain.com"
        result = await handle_save_memory(
            {"text": "I remember save test memory"},
            user,
        )

        mid = result["memory_id"]
        row = await conn.fetchrow(
            """
            SELECT id, "user", text FROM memories WHERE id = $1;
            """,
            mid,
        )

        assert row is not None
        assert row["user"] == user
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_save_memory_tool.py -v`
Expected: PASS (if embeddings reachable).

- [ ] **Step 4: Commit**

```bash
git add app/mcp/tools/save_memory.py tests/test_save_memory_tool.py
git commit -m "feat: add save_memory MCP tool"
```

---

### Task 8: Wire FastAPI app and ensure startup schema

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main_startup.py`

- [ ] **Step 1: Implement app/main.py**

```python
from fastapi import FastAPI
from app.mcp.endpoint import router as mcp_router
from app.db.engine import get_pool
from app.db.schema import ensure_schema


app = FastAPI(
    title="llama-memory MCP Memory Service",
)

app.include_router(mcp_router)


@app.on_event("startup")
async def on_startup():
    pool = await get_pool()
    await ensure_schema(pool)
```

- [ ] **Step 2: Create test tests/test_main_startup.py**

Smoke test ensuring app loads and /mcp is reachable.

```python
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_root_status():
    # We don't have / defined; expect 404
    assert client.get("/").status_code == 404


def test_mcp_endpoint_reachable():
    r = client.get("/mcp")
    assert r.status_code == 200
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_main_startup.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_main_startup.py
git commit -m "feat: wire FastAPI main app and startup schema"
```

---

### Task 9: Add run script and finalize

**Files:**
- Create: `scripts/run_server.ps1`

- [ ] **Step 1: Create scripts/run_server.ps1**

PowerShell entry for running the service (LOCAL_RULES compliant).

```powershell
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env not found. Copy .env.example to .env and configure."
    exit 1
}

python -m uvicorn app.main:app --host 0.0.0.0 --port 9001
```

- [ ] **Step 2: Commit**

```bash
git add scripts/run_server.ps1
git commit -m "feat: add run_server script for PowerShell"
```

---

End of plan.