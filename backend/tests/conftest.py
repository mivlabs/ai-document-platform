import os
import sys
import pathlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

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

# Импортируем Base и get_db (чтобы переопределить его), но НЕ глобальный engine!
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.cache import get_redis_client  # noqa: E402


TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/documents_test",
)


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """
    Создает асинхронный engine для каждого теста отдельно.
    Это гарантирует, что он привязан к текущему event loop'у теста.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_db_and_override_dependency(test_engine):
    """
    1. Очищает и пересоздает таблицы перед каждым тестом.
    2. Переопределяет зависимость get_db в FastAPI, чтобы приложение 
       использовало test_engine, а не глобальный engine из app.database.
    """
    # 1. Подготовка БД
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Создаем фабрику сессий, привязанную к test_engine
    async_session_maker = async_sessionmaker(
        test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    # 3. Переопределяем get_db для всего приложения на время теста
    async def override_get_db():
        async with async_session_maker() as session:
            yield session
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    # 4. Очищаем переопределения после теста, чтобы не сломать другие тесты
    app.dependency_overrides.clear()
    
    # 5. (Опционально) Очистка Redis
    try:
        await get_redis_client().flushdb()
    except Exception:
        pass


@pytest_asyncio.fixture
async def client():
    """Тестовый HTTP-клиент, который использует переопределенный app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session(test_engine):
    """
    Прямой доступ к БД в тесте (если нужно вставить данные в обход HTTP).
    Использует тот же test_engine, что и приложение.
    """
    async_session_maker = async_sessionmaker(
        test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session