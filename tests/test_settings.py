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
