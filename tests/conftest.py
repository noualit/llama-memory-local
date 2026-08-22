import pytest
from fastapi import FastAPI


@pytest.fixture(scope="session")
def app_instance() -> FastAPI:
    """Provide a single FastAPI app instance for all tests."""
    from app.main import app
    return app
