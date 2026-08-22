import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from app.mcp.endpoint import router as mcp_router
from app.db.engine import get_pool
from app.db.schema import ensure_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "doc" / "system_prompt.txt"
_SYSTEM_PROMPT_TEXT: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load system prompt from file into memory (startup-time only)
    global _SYSTEM_PROMPT_TEXT
    if SYSTEM_PROMPT_PATH.exists():
        _SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

    # Startup: ensure DB schema.
    # - For new deployments, run migrations via Alembic:
    #     alembic upgrade head
    # - For backward compatibility and local use, ensure_schema() still runs.
    await ensure_schema(await get_pool())
    yield  # must not return a non-dict value


app = FastAPI(
    title="llama-memory MCP Memory Service",
    lifespan=lifespan,
)

# Global CORS to prevent “Failed to fetch” from llama-server UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(mcp_router)


@app.get("/system-prompt")
async def get_system_prompt():
    """Return the recommended system prompt for llama-server."""
    return PlainTextResponse(content=_SYSTEM_PROMPT_TEXT or "No system prompt configured.")
