"""
Регрессионные тесты на SQL-инъекцию в /rag/query.

Раньше document_ids склеивался прямо в SQL-текст через f-string:
    doc_ids_str = ",".join([f"'{doc_id}'" for doc_id in request.document_ids])
    filter_clause = f"WHERE document_id IN ({doc_ids_str})"

Любой document_id со спецсимволами (кавычка, `;`, `--`) исполнялся бы как
часть запроса. Сейчас document_id валидируется как UUID до всякого SQL,
а сам фильтр идёт через expanding bindparam, а не через конкатенацию строк.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import insert

from app.models.document import Document, DocumentChunk
from app.services.cache import get_redis_client

FAKE_EMBEDDING = [1.0] + [0.0] * 1535  # ненулевой вектор: cosine distance для нулевого вектора не определена


def _fake_llm_response(text: str):
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_sql_injection_payload_in_document_ids_is_rejected(client):
    malicious_id = "x'); DROP TABLE document_chunks; --"

    with patch(
        "app.services.embeddings.embeddings_service.create_embeddings",
        new=AsyncMock(return_value=[FAKE_EMBEDDING]),
    ):
        resp = await client.post(
            "/rag/query",
            json={"query": "что угодно", "document_ids": [malicious_id]},
        )

    assert resp.status_code == 422
    assert "uuid" in resp.json()["detail"].lower()

    # Таблица должна остаться на месте — если бы инъекция сработала,
    # следующий вызов упал бы с ошибкой "relation does not exist".
    list_resp = await client.get("/documents/")
    assert list_resp.status_code == 200


@pytest.mark.asyncio
async def test_multiple_document_ids_are_bound_not_concatenated(client):
    """document_ids из нескольких валидных UUID не должен ничего ломать —
    это регрессия на сам механизм expanding bindparam."""
    ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

    with patch(
        "app.services.embeddings.embeddings_service.create_embeddings",
        new=AsyncMock(return_value=[FAKE_EMBEDDING]),
    ):
        resp = await client.post(
            "/rag/query",
            json={"query": "что угодно", "document_ids": ids},
        )

    assert resp.status_code == 200
    # Документов с такими id нет -> честный ответ "нет информации", а не 500
    assert resp.json()["sources"] == []


@pytest.mark.asyncio
async def test_no_chunks_returns_honest_no_info_answer(client):
    with patch(
        "app.services.embeddings.embeddings_service.create_embeddings",
        new=AsyncMock(return_value=[FAKE_EMBEDDING]),
    ):
        resp = await client.post("/rag/query", json={"query": "есть тут что-то?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == []
    assert "нет информации" in body["answer"].lower()


@pytest.mark.asyncio
async def test_matching_chunk_answers_via_llm_and_second_call_hits_cache(client, db_session):
    try:
        await get_redis_client().ping()
    except Exception:
        pytest.skip("Redis недоступен в этом окружении — кэш-хит проверить нечем")

    document_id = uuid.uuid4()
    await db_session.execute(
        insert(Document).values(
            id=document_id,
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size=1,
            total_chunks=1,
        )
    )
    await db_session.execute(
        insert(DocumentChunk).values(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=0,
            text="Договор NDA действует 3 года с даты подписания.",
            embedding=FAKE_EMBEDDING,
        )
    )
    await db_session.commit()

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_fake_llm_response("NDA действует 3 года.")
    )

    with (
        patch(
            "app.services.embeddings.embeddings_service.create_embeddings",
            new=AsyncMock(return_value=[FAKE_EMBEDDING]),
        ),
        patch("app.routers.rag.get_llm_client", return_value=fake_client),
    ):
        first = await client.post("/rag/query", json={"query": "сколько действует NDA?"})
        second = await client.post("/rag/query", json={"query": "сколько действует NDA?"})

    assert first.status_code == 200 == second.status_code
    assert first.json()["answer"] == second.json()["answer"] == "NDA действует 3 года."
    # Второй одинаковый запрос должен быть отдан из кэша, а не сгенерирован заново.
    assert fake_client.chat.completions.create.call_count == 1
