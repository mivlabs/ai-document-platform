"""Redis-кэш для ответов RAG-пайплайна.

До этого коммита Redis был объявлен в settings/docker-compose, но нигде
в коде не использовался ни разу — просто задекларированная, но не
реализованная фича. Каждый /rag/query заново гонял embedding + LLM-запрос
даже для идентичных вопросов. Здесь — реальное использование: кэшируем
готовый ответ по хэшу (query, top_k, document_ids) на TTL_SECONDS.

Redis тут — оптимизация, а не источник истины: если он недоступен, кэш
просто молча выключается (см. try/except в get/set), запрос всё равно
отрабатывает через БД и LLM.
"""
import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.database import settings

logger = logging.getLogger(__name__)

TTL_SECONDS = 3600

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def build_rag_cache_key(query: str, top_k: int, document_ids: Optional[list]) -> str:
    """Детерминированный ключ кэша. Порядок document_ids не должен влиять
    на ключ — сортируем перед хэшированием."""
    normalized_ids = ",".join(sorted(document_ids)) if document_ids else "all"
    raw = f"{query.strip().lower()}|{top_k}|{normalized_ids}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"rag:query:{digest}"


async def get_cached_rag_response(key: str) -> Optional[dict]:
    try:
        raw = await get_redis_client().get(key)
    except Exception as e:
        logger.warning(f"Redis недоступен при чтении кэша ({e}) — работаем без кэша")
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def set_cached_rag_response(key: str, value: dict, ttl_seconds: int = TTL_SECONDS) -> None:
    try:
        await get_redis_client().set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Redis недоступен при записи кэша ({e}) — ответ просто не закэшировался")
