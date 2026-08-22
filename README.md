# llama-memory

MCP Memory Service for llama-server with persistent history and semantic memory via Postgres + PGVector.

Note: This project is intended for local/demo use only. Do not expose it directly to the internet without additional hardening (HTTPS, proper auth, backups).

## What it does

- Semantic memory: save and retrieve memories by meaning, not just keywords.
- Conversation bridge: LLM creates conversations automatically; memories are linked.
- Cross-session recall: ask "what did we talk about before?" and get accurate answers.
- MCP protocol: works directly with llama-server's built-in MCP support.

## Requirements

- Python 3.11 (Miniconda recommended)
- PostgreSQL 16+ with PGVector extension
- llama-server with --jinja flag (required for tool calling)
- nomic-embed-text running on llama-server (port 8081 by default)

## Installation

```bash
# Clone the repo
git clone https://github.com/noualit/llama-memory-local.git
cd llama-memory-local

# Create environment
conda create -n llama-memory python=3.11
conda activate llama-memory

# Install dependencies
pip install -e .
```

## Configuration

Copy .env.example to .env and edit:

```bash
cp .env.example .env
```

Example:

```env
# Database
DATABASE_URL="postgresql://postgres:yourpassword@localhost:5432/llamamem"

# Llama-server (LLM)
LLAMA_SERVER_BASE_URL="http://localhost:8080"

# Embedding model (nomic-embed-text via llama-server)
EMBEDDING_MODEL_URL="http://localhost:8081"

# Embedding model name (default: nomic-embed-text)
EMBEDDING_MODEL_NAME="nomic-embed-text"

# Service port
SERVICE_PORT=9001
```

## Setup database

Create the database and run migrations:

```bash
psql -U postgres -c "CREATE DATABASE llamamem;"
alembic upgrade head
```

The application also ensures basic schema on startup for convenience.

## Run the service

```bash
# Using the script
.\scripts\run_server.ps1

# Or directly
python -m uvicorn app.main:app --host 0.0.0.0 --port 9001
```

## Connect to llama-server

Add to your llama-server MCP configuration:

```json
{
  "mcpServers": {
    "llama-memory": {
      "url": "http://YOUR_SERVER_IP:9001/mcp"
    }
  }
}
```

The service must be reachable from llama-server. Use the actual IP, not localhost if they run on different machines.

## MCP Tools

| Tool | Description |
|------|-------------|
| create_conversation | Create a new conversation session |
| list_conversations | List conversations with memory count |
| get_conversation_history | Get all memories in a conversation |
| search_memories | Semantic search across all memories |
| save_memory | Store an important fact or decision |

## System prompt

You can:

- Fetch the recommended system prompt from the service:

  - GET /system-prompt → returns plain text.

- Or paste this minimal version into llama-server:

```
MEMORY WORKFLOW:
- At the start of each new conversation, call create_conversation with a short title.
- Use the conversation_id from create_conversation when calling save_memory.
- Before answering questions about past topics, call search_memories FIRST.
- When the user shares important information, save it with save_memory.
- If list_conversations has previous chats, check get_conversation_history for context.
```

## Health check

```bash
curl http://localhost:9001/health
```

Returns DB status, embedding service status, and tool count.

## Architecture

High-level structure:

- app/main.py — FastAPI app, lifespan, /system-prompt
- app/settings.py — Pydantic settings from .env
- app/clients/embeddings.py — Calls nomic-embed-text for vectors
- app/db/engine.py — asyncpg connection pool (singleton)
- app/db/schema.py — Auto-creates tables on startup
- app/mcp/endpoint.py — MCP protocol handlers, rate limiter
- app/mcp/tools/ — Individual tool implementations
- migrations/ — Alembic database migrations

## Development

```bash
# Run tests
pytest tests/ -v

# Run with auto-reload
python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload
```

See CONTRIBUTING.md for contribution guidelines.

## License

MIT (see LICENSE file).
