from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_root_status():
    # We don't have / defined; expect 404
    assert client.get("/").status_code == 404


def test_mcp_endpoint_reachable():
    r = client.get("/mcp")
    assert r.status_code == 200
