import os
import sys
import pathlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

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

from app.database import Base, async_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.cache import get_redis_client  # noqa: E402


TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/documents_test",
)


# 🔥 ИСПРАВЛЕНИЕ: scope="function" вместо "session"
@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """
    Создает асинхронный engine для каждого теста отдельно.
    Это предотвращает ScopeMismatch с event_loop и гарантирует чистоту тестов.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_state(test_engine):
    """
    Очищает и пересоздает таблицы перед каждым тестом.
    """
    async with test_engine.begin() as conn:
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
    """Прямой доступ к БД в тесте."""
    async with async_session() as session:
        yield session