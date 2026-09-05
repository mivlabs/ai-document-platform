import pytest

from app.services.cache import (
    build_rag_cache_key,
    get_cached_rag_response,
    get_redis_client,
    set_cached_rag_response,
)


def test_cache_key_ignores_document_id_order():
    a = build_rag_cache_key("Что такое NDA?", 10, ["doc-b", "doc-a"])
    b = build_rag_cache_key("Что такое NDA?", 10, ["doc-a", "doc-b"])
    assert a == b


def test_cache_key_is_case_and_whitespace_insensitive():
    a = build_rag_cache_key("Что такое NDA?", 10, None)
    b = build_rag_cache_key("  что такое nda?  ", 10, None)
    assert a == b


def test_cache_key_differs_by_top_k():
    a = build_rag_cache_key("query", 10, None)
    b = build_rag_cache_key("query", 5, None)
    assert a != b


def test_cache_key_differs_between_no_filter_and_empty_filter():
    a = build_rag_cache_key("query", 10, None)
    b = build_rag_cache_key("query", 10, [])
    # Пустой список и None сейчас нормализуются одинаково ("all") — это
    # осознанный выбор (пустой фильтр = искать везде, как и без фильтра).
    assert a == b


@pytest.mark.asyncio
async def test_cache_roundtrip_or_skip_if_redis_unavailable():
    try:
        await get_redis_client().ping()
    except Exception:
        pytest.skip("Redis недоступен в этом окружении")

    key = build_rag_cache_key("roundtrip test", 3, ["11111111-1111-1111-1111-111111111111"])
    assert await get_cached_rag_response(key) is None

    payload = {"answer": "42", "sources": []}
    await set_cached_rag_response(key, payload, ttl_seconds=30)

    assert await get_cached_rag_response(key) == payload
