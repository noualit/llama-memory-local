import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_mcp_initialize_returns_capabilities():
    """
    MCP client expects capabilities with tools support in the initialize response.
    """
    init_resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
        headers={"X-User": "test@testdomain.com"},
    )

    assert init_resp.status_code == 200, f"init failed: {init_resp.text}"
    data = init_resp.json()

    result = data.get("result", {})
    caps = result.get("capabilities", {})
    assert "tools" in caps, "Initialize must advertise tools capability"
    assert result.get("serverInfo", {}).get("name") == "llama-memory"


def test_mcp_tools_list_method():
    """
    Some MCP clients explicitly call tools/list after initialize.
    We must return tools there as well, never empty.
    """
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers={"X-User": "test@testdomain.com"},
    )

    assert resp.status_code == 200, f"tools/list failed: {resp.text}"
    data = resp.json()

    result = data.get("result", {})
    tools = result.get("tools")
    assert isinstance(tools, list) and len(tools) == 5, (
        "tools/list must include all 5 tools"
    )

    names = [t["name"] for t in tools]
    assert "create_conversation" in names
    assert "list_conversations" in names
    assert "get_conversation_history" in names
    assert "search_memories" in names
    assert "save_memory" in names


def test_mcp_tool_call_list_conversations():
    """
    After listing tools, client should be able to call a real tool
    using the tools/call method with params.name.
    """
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_conversations",
                "arguments": {},
            },
        },
        headers={"X-User": "test@testdomain.com"},
    )

    assert resp.status_code == 200, f"tool call failed: {resp.text}"
    data = resp.json()

    result = data.get("result")
    assert isinstance(result, dict), "Tool call must return a JSON-RPC result object."
    assert "content" in result, "Tool result must wrap in content format"
