from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import uuid
from app.database import get_db
from app.models.document import Document, DocumentChunk
from app.services.pdf_parser import pdf_parser
from app.services.embeddings import embeddings_service

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Загружает PDF, создаёт embeddings и сохраняет в БД."""
    
    # Проверка типа файла
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Сохраняем файл
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Парсим PDF
    try:
        text = pdf_parser.extract_text(file_path)
        chunks = pdf_parser.chunk_text(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")
    
    if not chunks:
        raise HTTPException(status_code=400, detail="PDF is empty or unreadable")
    
    # Создаём embeddings
    try:
        embeddings = await embeddings_service.create_embeddings(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create embeddings: {str(e)}")
    
    # Сохраняем документ в БД
    document = Document(
        id=uuid.uuid4(),
        filename=file.filename,
        file_path=file_path,
        file_type="pdf",
        file_size=len(content),
        total_chunks=len(chunks)
    )
    db.add(document)
    await db.flush()
    
    # Сохраняем чанки с embeddings
    for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=i,
            text=chunk_text,
            embedding=embedding
        )
        db.add(chunk)
    
    await db.commit()
    
    return {
        "document_id": str(document.id),
        "filename": file.filename,
        "total_chunks": len(chunks),
        "status": "success"
    }

@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """Список всех загруженных документов."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "file_size": doc.file_size,
                "total_chunks": doc.total_chunks,
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ]
    }

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Удаляет документ и все его чанки из БД."""
    from sqlalchemy import delete
    
    try:
        # Удаляем чанки
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        # Удаляем документ
        await db.execute(
            delete(Document).where(Document.id == document_id)
        )
        await db.commit()
        return {"status": "deleted", "document_id": document_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))