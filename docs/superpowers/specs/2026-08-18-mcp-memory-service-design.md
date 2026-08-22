# MCP Memory Service – Design Spec

- Date: 2026-08-18
- Status: Draft (awaiting review)

## 1. Objective

Provide persistent memory between conversations for llama-server, consumed as an MCP server from its UI.

Capabilities:
- Store and retrieve conversation history per user.
- Maintain long-term semantic memories via RAG with PGVector.
- Expose tools via a single MCP endpoint (e.g., /mcp).
- Ensure strict isolation between users in the domain domain.

Constraints:
- Python 3.11, Miniconda, FastAPI.
- Postgres 16 + pgvector.
- llama-server (Qwen3.6-27B) on :8080.
- nomic-embed-text on :8081.
- Respect LOCAL_RULES.md (TDD, no hardcode, modules < 600 lines, etc.).

## 2. Architecture

Core components:

- llama-memory service:
  - FastAPI + uvicorn.
  - Default port: 9001 (configurable via env).
  - Single MCP HTTP endpoint: /mcp used by llama-server UI.

- Dependencies:
  - Postgres 16 + pgvector: conversations, messages, memories.
  - llama-server :8080: chat completions (OpenAI-compatible endpoint).
  - nomic-embed-text :8081: embeddings for RAG.

- Integration with llama-server:
  - Added as MCP server in UI config:
    - URL: http://YOUR_SERVER_IP:9001/mcp
    - Header: X-User = <user@yourdomain.com>
  - The model uses the provided tools during conversations.

Design principles:
- Explicit separation of concerns:
  - DB layer
  - MCP layer
  - LLM/Embedding client layer
- No cross-user leakage; all queries filtered by user.
- Environment-based config (.env), no hardcoded credentials.
- TDD-first for all core operations.

## 3. User Isolation

User identity:
- Format: "user@yourdomain.com" (e.g., "juan@yourdomain.com").
- Source: X-User HTTP header set by llama-server UI per user.

Rules:
- All tools MUST include user.
- If X-User is missing or empty → 401/403, no data exposed.
- No tool allows querying across users (no “admin” escape).
- DB rows duplicated with user field for fast, explicit filtering.

## 4. Database Schema

Extensions:
- CREATE EXTENSION IF NOT EXISTS vector;

Tables:

- conversations:
  - id: UUID PRIMARY KEY
  - user: TEXT NOT NULL
  - name: TEXT
  - updated_at: TIMESTAMPTZ
  - Index(conversation_id, updated_at DESC)

- messages:
  - id: UUID PRIMARY KEY
  - conversation_id: UUID REFERENCES conversations(id)
  - user: TEXT NOT NULL
  - role: TEXT -- "user" | "assistant" | "system" | "tool"
  - content: TEXT
  - created_at: TIMESTAMPTZ
  - Index(user, conversation_id, created_at)

- memories:
  - id: UUID PRIMARY KEY
  - user: TEXT NOT NULL
  - text: TEXT
  - embedding: VECTOR(1536) -- adjust if needed
  - conversation_id: UUID REFERENCES conversations(id) NULL
  - tags: TEXT[]
  - created_at: TIMESTAMPTZ
  - HNSW index on embedding (cosine or configured pgvector metric)

Notes:
- user is redundant where FK exists, but kept explicit to enforce fast, unambiguous isolation.
- All queries must include WHERE user = $user.

## 5. MCP Tools

Accessible via /mcp from llama-server UI.

Each tool receives “user” from X-User header (never guessed).

1) list_conversations
   - Purpose: List recent conversations for a user.
   - Params:
     - user (from header)
     - limit (int, default 50)
   - Output:
     - [ { id, name, updated_at } ]

2) get_conversation_history
   - Purpose: Retrieve messages in a conversation.
   - Params:
     - conversation_id (str)
     - user (from header)
     - limit (int, default 50)
   - Output:
     - [ { role, content } ] ordered by created_at

3) search_memories
   - Purpose: Find semantically relevant memories for a query.
   - Params:
     - query (str)
     - user (from header)
     - limit (int, default 10)
   - Behavior:
     - Compute embedding(query) via nomic-embed-text.
     - Query memories by cosine similarity.
   - Output:
     - [ { text, score } ]

4) save_memory
   - Purpose: Persist an important fact from conversation.
   - Params:
     - text (str)
     - user (from header)
     - conversation_id (optional)
     - tags (list[str], optional)
   - Behavior:
     - Compute embedding(text).
     - Insert memory row.
   - Output:
     - { memory_id }

Security notes:
- Every tool enforces user from X-User header.
- No cross-user access, no global search.

## 6. Conversation Flow

Typical flow during a conversation in llama-server UI:

1) User sends message.
2) LLM (via system prompt or learned behavior):
   - Calls get_conversation_history(conversation_id) to load context.
   - Optionally calls search_memories(query) if long-term memory is relevant.
3) LLM generates response using retrieved context.
4) When appropriate, LLM or system prompt:
   - Calls save_memory with key facts from the conversation.

Design expectations:
- The service itself is neutral about when to call each tool; that logic lives in llama-server prompts/model behavior.
- Our responsibility is reliable, fast, and isolated tool execution.

## 7. Non-Functional Requirements

- Performance:
  - Keep latency of MCP tools low enough for interactive use.
- Reliability:
  - Handle errors from Postgres, embedding model, and llama-server gracefully (clear error messages).
- Maintainability:
  - Modules under 600 lines.
  - Clear boundaries:
    - db/
    - mcp/
    - clients/
    - models/

## 8. Alignment with LOCAL_RULES

- TDD mandatory for:
  - Conversation CRUD and history retrieval.
  - Memory storage and semantic search.
  - MCP tool handlers.
- No hardcoded credentials or connection strings; all via .env.
- No duplicate systems; single source of truth per operation.
- Git messages in Spanish, atomic and focused.

End of spec (Draft).