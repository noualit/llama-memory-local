#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-end integration tests for the full MCP flow:
initialize -> tools/list -> create_conversation -> save_memory -> verify persistence.

These tests run against the real FastAPI app (TestClient) and the configured database.
"""

import json
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client(app_instance: FastAPI):
    """Shared TestClient for E2E integration tests."""
    return TestClient(app_instance)


def _tool_call(client: TestClient, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to call a tool via MCP and unwrap its JSON result."""
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]

    # MCP wraps tool results in content[0].text as JSON.
    if isinstance(result, dict) and "content" in result:
        text_payload = result["content"][0]["text"]
        return json.loads(text_payload)
    return result


class TestMcpE2eFlow:
    def test_mcp_e2e_initialize_and_tools_list(self, client: TestClient):
        # 1) GET /mcp returns tools list (basic sanity)
        get_resp = client.get("/mcp")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert "tools" in data

        # 2) MCP initialize handshake
        init_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                },
            },
        )
        assert init_resp.status_code == 200
        init_data = init_resp.json()
        assert init_data["result"]["capabilities"]["tools"] is not None

        # 3) tools/list returns structured list of tools
        tools_list_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        assert tools_list_resp.status_code == 200
        tools_data = tools_list_resp.json()["result"]
        tool_names = [t["name"] for t in tools_data["tools"]]
        assert "save_memory" in tool_names
        assert "search_memories" in tool_names

    def test_mcp_e2e_create_conversation_save_and_verify(self, client: TestClient):
        token = "llama-memory E2E integration test marker"

        # 1) Create a conversation via MCP
        conv_result = _tool_call(client, "create_conversation", {"name": "E2E Integration Test Conversation"})
        conv_id = conv_result["conversation_id"]

        # 2) Save a memory linked to that conversation
        save_result = _tool_call(
            client,
            "save_memory",
            {
                "text": token,
                "conversation_id": conv_id,
            },
        )
        assert "memory_id" in save_result or "id" in save_result or "ok" in save_result, \
            "save_memory did not return expected result"

        # 3) Get conversation history and confirm our memory is there
        hist_result = _tool_call(
            client,
            "get_conversation_history",
            {"conversation_id": conv_id},
        )
        memories = hist_result.get("memories") or []

        found = any(token in (m.get("text") or "") for m in memories)
        assert found, "Saved memory not found in conversation history (E2E test)"
