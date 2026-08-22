import json
import logging
import time
from collections import defaultdict
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.clients.embeddings import EmbeddingError

logger = logging.getLogger("llama-memory.mcp")


router = APIRouter()


# ---------------------------------------------------------------------------
# 1) MCP tools definition - single source of truth (deduplicated)
# ---------------------------------------------------------------------------
TOOLS_LIST = [
    {
        "name": "create_conversation",
        "description": "Create a new conversation. Call this at the start of each new topic or session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short title for the conversation"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "list_conversations",
        "description": "List recent conversations with their memory count and last memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max conversations to return"}
            },
            "required": []
        }
    },
    {
        "name": "get_conversation_history",
        "description": "Retrieve all memories stored in a specific conversation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "ID of the conversation"},
                "limit": {"type": "integer", "description": "Max memories to return"}
            },
            "required": ["conversation_id"]
        }
    },
    {
        "name": "search_memories",
        "description": "Search across all memories by semantic similarity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for"},
                "limit": {"type": "integer", "description": "Max results"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Save an important fact, decision, or preference. Auto-links to the most recent conversation if conversation_id is not provided.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Memory text to store"},
                "conversation_id": {"type": "string", "description": "Optional conversation ID to link to"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags for categorization"}
            },
            "required": ["text"]
        }
    }
]

# Lightweight summaries for GET /mcp (no inputSchema to keep it minimal)
TOOLS_LIST_SUMMARY = [
    {"name": t["name"], "description": t["description"]}
    for t in TOOLS_LIST
]


# ---------------------------------------------------------------------------
# 2) Rate limiter - sliding window per IP
# ---------------------------------------------------------------------------
class RateLimiter:
    """
    Per-IP sliding window rate limiter (in-memory, process-scoped).

    Notes:
    - Designed for local-first / trusted environments.
    - Resets on restart; not shared across workers.
    - If you need distributed/persistent limiting, integrate Redis or similar.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        # Prune old entries
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= self.max_requests:
            return False
        self._hits[key].append(now)
        return True


_limiter = RateLimiter(max_requests=120, window_seconds=60)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# CORS helpers
# ---------------------------------------------------------------------------
def cors_headers(response: JSONResponse) -> JSONResponse:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers[
        "Access-Control-Allow-Headers"
    ] = "Content-Type, X-User"
    return response


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@router.get("/health")
async def health_check():
    """Validates DB, embedding service, and returns MCP status."""
    checks = {}

    # DB check
    try:
        from app.db.engine import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval("SELECT 1")
            checks["database"] = "ok" if row == 1 else "degraded"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}: {e}"

    # Embedding service check
    try:
        from app.clients.embeddings import get_embedding
        await get_embedding("health check")
        checks["embeddings"] = "ok"
    except Exception as e:
        checks["embeddings"] = f"error: {type(e).__name__}: {e}"

    # MCP tools count
    checks["mcp_tools"] = len(TOOLS_LIST)

    all_ok = all(
        v == "ok" or isinstance(v, int)
        for v in checks.values()
    )

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", **checks}
    )


# ---------------------------------------------------------------------------
# MCP endpoints
# ---------------------------------------------------------------------------
@router.get("/mcp")
async def mcp_info(request: Request):
    resp = JSONResponse({"tools": TOOLS_LIST_SUMMARY})
    return cors_headers(resp)


@router.options("/mcp")
async def mcp_options(request: Request):
    resp = JSONResponse(status_code=200, content={})
    return cors_headers(resp)


@router.post("/mcp")
async def mcp_call(request: Request):
    # Rate limit check
    client_ip = _get_client_ip(request)
    if not _limiter.is_allowed(client_ip):
        return cors_headers(
            JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again shortly."}
            )
        )

    try:
        return await _handle_mcp_call(request)
    except EmbeddingError as e:
        # Clear message when embedding service is down/unreachable
        logger.error("[MCP-EMBEDDING] %s", e)
        return cors_headers(
            JSONResponse(content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Embedding service error: {e}"
                }
            })
        )
    except Exception as e:
        logger.error("[MCP-FATAL] %s: %s", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        return cors_headers(
            JSONResponse(content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {e}"}
            })
        )


async def _handle_mcp_call(request: Request):
    user = request.headers.get("X-User", "").strip()
    effective_user = user or "system"

    body = {}
    try:
        body = await request.json()
    except Exception:
        logger.warning("[MCP] BAD JSON")
        return cors_headers(
            JSONResponse(status_code=400, content={"error": "Invalid JSON"})
        )

    if not isinstance(body, dict):
        logger.warning("[MCP] ROOT NOT DICT")
        return cors_headers(
            JSONResponse(status_code=400, content={"error": "Request must be a JSON object"})
        )

    is_jsonrpc = bool(body.get("jsonrpc"))
    req_id = body.get("id")
    method = (body.get("method") or body.get("tool")) or ""
    params = body.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    logger.debug("[MCP-IN] id=%s method=%s jsonrpc=%s keys=%s", req_id, method, is_jsonrpc, list(body.keys()))

    # MCP: list available tools
    if str(method).lower().strip() == "tools/list":
        if is_jsonrpc:
            return cors_headers(
                JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": TOOLS_LIST}
                })
            )
        else:
            return cors_headers(JSONResponse(content={"tools": TOOLS_LIST}))

    # MCP initialize handshake
    if str(method).lower() == "initialize":
        logger.debug("[MCP-INIT] starting initialize")
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "llama-memory",
                "version": "0.1.0"
            }
        }

        if is_jsonrpc:
            return cors_headers(
                JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                })
            )
        else:
            return cors_headers(JSONResponse(content=result))

    # Tool handlers mapping
    # MCP protocol: tools/call sends name in params.name, not in method
    tool_name = str(method).lower().strip() if method else ""
    if tool_name == "tools/call":
        tool_name = str(params.get("name", "")).lower().strip()

    handler = None

    if tool_name == "create_conversation":
        from app.mcp.tools.create_conversation import handle_create_conversation
        tool_args = params.get("arguments", params)
        handler = lambda: handle_create_conversation(tool_args, effective_user)
    elif tool_name == "list_conversations":
        from app.mcp.tools.list_conversations import handle_list_conversations
        tool_args = params.get("arguments", params)
        handler = lambda: handle_list_conversations(tool_args, effective_user)
    elif tool_name == "get_conversation_history":
        from app.mcp.tools.get_conversation_history import handle_get_conversation_history
        tool_args = params.get("arguments", params)
        handler = lambda: handle_get_conversation_history(tool_args, effective_user)
    elif tool_name == "search_memories":
        from app.mcp.tools.search_memories import handle_search_memories
        tool_args = params.get("arguments", params)
        handler = lambda: handle_search_memories(tool_args, effective_user)
    elif tool_name == "save_memory":
        from app.mcp.tools.save_memory import handle_save_memory
        tool_args = params.get("arguments", params)
        handler = lambda: handle_save_memory(tool_args, effective_user)

    if not handler:
        logger.warning("[MCP-UNKNOWN] method=%s id=%s", method, req_id)
        msg = f"Unknown tool/method: {method}"
        if is_jsonrpc:
            err_response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": msg}
            }
        else:
            err_response = {"error": msg}
        return cors_headers(JSONResponse(content=err_response))

    # Execute handler
    raw_result = await handler()

    # MCP protocol: wrap tool result in content format
    if isinstance(raw_result, dict) and "content" not in raw_result:
        result = {"content": [{"type": "text", "text": json.dumps(raw_result)}]}
    else:
        result = raw_result

    if is_jsonrpc:
        response_payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }
    else:
        response_payload = result

    return cors_headers(JSONResponse(content=response_payload))
