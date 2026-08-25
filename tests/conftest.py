"""Test fixtures with full database isolation.

Tests run against a dedicated database (llamamem_test) derived from the
real DATABASE_URL, so they never pollute production data. The test DB is
created on demand, migrated with the app's own ensure_schema(), and
truncated at the start of each test session.
"""
import os
from pathlib import Path

import pytest
from fastapi import FastAPI

TEST_DB_NAME = "llamamem_test"


def _resolve_base_database_url() -> str:
    """Read DATABASE_URL from env or .env WITHOUT importing app modules.

    Importing app.settings here would instantiate Settings() too early,
    so we parse the value manually instead.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL"):
                _, _, value = stripped.partition("=")
                return value.strip().strip('"').strip("'")
    raise RuntimeError(
        "DATABASE_URL not found: set it as environment variable or in .env"
    )


def _swap_db_name(url: str, db_name: str) -> str:
    """Replace only the database name segment, keeping host/port/auth."""
    head, sep, _tail = url.rpartition("/")
    return f"{head}/{db_name}" if sep else url


TEST_DATABASE_URL = _swap_db_name(_resolve_base_database_url(), TEST_DB_NAME)

# Env var wins over .env in pydantic-settings -> any app import from now
# on resolves settings against the isolated test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


async def _prepare_test_database() -> None:
    import asyncpg

    # 1) Create the test database if missing (maintenance connection)
    admin_conn = await asyncpg.connect(_swap_db_name(TEST_DATABASE_URL, "postgres"))
    try:
        try:
            await admin_conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        except asyncpg.DuplicateDatabaseError:
            pass
    finally:
        await admin_conn.close()

    # 2) Migrate using the app's single source of truth for DDL
    from app.db.schema import ensure_schema

    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    try:
        await ensure_schema(pool)
    finally:
        await pool.close()

    # 3) Truncate for a deterministic, empty state each session
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(
            "TRUNCATE TABLE memories, conversations CASCADE"
        )
    finally:
        await conn.close()


def _bootstrap() -> None:
    import asyncio

    try:
        asyncio.run(_prepare_test_database())
    except Exception as exc:  # noqa: BLE001 - fail fast with a clear message
        raise RuntimeError(
            f"Could not prepare isolated test database '{TEST_DB_NAME}': {exc}"
        ) from exc


_bootstrap()


@pytest.fixture(scope="session")
def app_instance() -> FastAPI:
    """Provide a single FastAPI app instance bound to the isolated test DB."""
    from app.main import app

    return app
