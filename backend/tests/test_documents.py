import io
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client):
    resp = await client.post(
        "/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"just text"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "pdf" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_creates_document_and_chunks(client):
    with (
        patch("app.services.pdf_parser.pdf_parser.extract_text", return_value="какой-то текст документа"),
        patch(
            "app.services.pdf_parser.pdf_parser.chunk_text",
            return_value=["чанк первый", "чанк второй"],
        ),
        patch(
            "app.services.embeddings.embeddings_service.create_embeddings",
            new=AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536]),
        ),
    ):
        resp = await client.post(
            "/documents/upload",
            files={"file": ("contract.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["total_chunks"] == 2

    listing = await client.get("/documents/")
    assert listing.status_code == 200
    docs = listing.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "contract.pdf"
    assert docs[0]["total_chunks"] == 2


@pytest.mark.asyncio
async def test_list_documents_empty_by_default(client):
    resp = await client.get("/documents/")
    assert resp.status_code == 200
    assert resp.json()["documents"] == []


@pytest.mark.asyncio
async def test_delete_document_removes_it_and_its_chunks(client):
    with (
        patch("app.services.pdf_parser.pdf_parser.extract_text", return_value="текст"),
        patch("app.services.pdf_parser.pdf_parser.chunk_text", return_value=["один чанк"]),
        patch(
            "app.services.embeddings.embeddings_service.create_embeddings",
            new=AsyncMock(return_value=[[0.1] * 1536]),
        ),
    ):
        upload = await client.post(
            "/documents/upload",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
    document_id = upload.json()["document_id"]

    delete_resp = await client.delete(f"/documents/{document_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"

    listing = await client.get("/documents/")
    assert listing.json()["documents"] == []
