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
    assert "create_conversation" in tool_names
    assert "list_conversations" in tool_names
    assert "get_conversation_history" in tool_names
    assert "search_memories" in tool_names
    assert "save_memory" in tool_names


def test_mcp_post_without_user_defaults_to_system():
    """Missing X-User header should default to 'system' user, not reject."""
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_conversations", "arguments": {}},
        },
        headers={},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("result") is not None
