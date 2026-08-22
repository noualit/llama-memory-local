import httpx
from app.settings import settings


class EmbeddingError(Exception):
    """Raised when the embedding service is unavailable or returns an unexpected response."""


async def get_embedding(text: str) -> list[float]:
    url = f"{settings.EMBEDDING_MODEL_URL}/v1/embeddings"
    payload = {
        "model": settings.EMBEDDING_MODEL_NAME,
        "input": text,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise EmbeddingError(f"Embedding request failed: {e}") from e
    except Exception as e:
        raise EmbeddingError(f"Unexpected error calling embedding service: {e}") from e

    # Typical shape: {data: [{embedding: [...]}, ...]}
    try:
        return data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as e:
        raise EmbeddingError(
            f"Unexpected response format from embedding service: {e}"
        ) from e
