import os
import sys
import pathlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/documents_test",
    ),
)
os.environ.setdefault("REDIS_URL", os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/14"))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-real")

from app.database import Base, engine, async_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.cache import get_redis_client  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_state():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        await get_redis_client().flushdb()
    except Exception:
        # Redis недоступен локально без docker-compose — тесты кэша это
        # учитывают (см. test_cache.py), остальные тесты от Redis не зависят.
        pass
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    """Прямой доступ к БД в тесте — например, чтобы вставить тестовые
    чанки в обход HTTP-эндпоинтов (upload требует реального PDF+embeddings)."""
    async with async_session() as session:
        yield session
