from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.services.embeddings import embeddings_service
from openai import AsyncOpenAI
import os

router = APIRouter(prefix="/rag", tags=["rag"])

class QueryRequest(BaseModel):
    query: str
    top_k: int = 10
    document_ids: Optional[List[str]] = None

class RAGResponse(BaseModel):
    answer: str
    sources: List[dict]

def get_llm_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

@router.post("/query", response_model=RAGResponse)
async def query_documents(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """RAG: ищет релевантные чанки и генерирует ответ."""
    
    # Логируем запрос
    print(f"\n{'='*50}")
    print(f"🔍 Query: {request.query}")
    print(f"📄 Document IDs: {request.document_ids}")
    
    # Создаём embedding для запроса
    try:
        query_embedding = await embeddings_service.create_embeddings([request.query])
        query_embedding = query_embedding[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create query embedding: {str(e)}")
    
    # Формируем embedding как строку для SQL
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    # Фильтрация по document_ids если переданы
    filter_clause = ""
    params = {
        "embedding": embedding_str,
        "top_k": request.top_k
    }
    
    if request.document_ids:
        doc_ids_str = ",".join([f"'{doc_id}'" for doc_id in request.document_ids])
        filter_clause = f"WHERE document_id IN ({doc_ids_str})"
        print(f"🔎 Filtering by document_ids: {doc_ids_str}")
    else:
        print("⚠️ No document_ids filter - searching ALL documents")
    
    # Raw SQL для pgvector с фильтрацией
    sql = text(f"""
        SELECT 
            id, document_id, chunk_index, text,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM document_chunks
        {filter_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)
    
    try:
        result = await db.execute(sql, params)
        chunks = result.fetchall()
        
        # Логируем результаты поиска
        print(f"📊 Found {len(chunks)} chunks")
        
        if chunks:
            for i, chunk in enumerate(chunks[:5]):
                relevance = 1 - chunk.distance
                print(f"  {i+1}. Relevance: {relevance:.3f} | DocID: {chunk.document_id} | Preview: {chunk.text[:80]}...")
        else:
            print("❌ No chunks found!")
            
    except Exception as e:
        print(f"❌ SQL Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search documents: {str(e)}")
    
    # Проверка: если ничего не найдено
    if not chunks:
        print("⚠️ Returning: no chunks found")
        return RAGResponse(
            answer="В документе нет информации по этому вопросу.",
            sources=[]
        )
    
    # Проверка релевантности — очень низкий порог для теста
    max_relevance = max(1 - chunk.distance for chunk in chunks)
    print(f"📈 Max relevance: {max_relevance:.3f}")
    
    if max_relevance < 0.10:  # Очень низкий порог
        print(f"⚠️ Relevance too low: {max_relevance:.3f} < 0.10")
        return RAGResponse(
            answer="В документе нет информации по этому вопросу. Попробуйте переформулировать.",
            sources=[]
        )
    
    # Формируем контекст из найденных чанков
    context = "\n\n---\n\n".join([chunk.text for chunk in chunks])
    print(f"📝 Context length: {len(context)} chars")
    
    # Генерируем ответ через LLM
    client = get_llm_client()
    
    prompt = f"""Ты — эксперт по анализу документов. Твоя задача — дать ТОЧНЫЙ и КОНКРЕТНЫЙ ответ на вопрос пользователя, основываясь на предоставленном контексте из документа.

ПРАВИЛА:
1. Используй ТОЛЬКО информацию из контекста ниже
2. Если в контексте нет ответа на вопрос — честно скажи "В документе нет информации по этому вопросу"
3. Будь КОНКРЕТНЫМ: приводи факты, цифры, цитаты из документа
4. Не используй общих фраз типа "документ обсуждает различные аспекты"
5. Отвечай на том же языке, что и вопрос

КОНТЕКСТ ИЗ ДОКУМЕНТА:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {request.query}

ОТВЕТ (будь конкретным и точным):"""
    
    try:
        response = await client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct",
            messages=[
                {
                    "role": "system",
                    "content": "Ты — эксперт по анализу документов. Отвечай ТОЛЬКО на основе предоставленного контекста. Если ответа нет в контексте — честно скажи 'В документе нет информации по этому вопросу'. Будь конкретным: приводи факты, цифры, цитаты. Отвечай на русском языке."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=1500
        )
        answer = response.choices[0].message.content.strip()
        print(f"✅ Generated answer: {answer[:100]}...")
    except Exception as e:
        print(f"❌ LLM Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")
    
    # Формируем источники
    sources = [
        {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
            "text_preview": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
            "relevance_score": round(1 - chunk.distance, 3)
        }
        for chunk in chunks
    ]
    
    print(f"{'='*50}\n")
    
    return RAGResponse(answer=answer, sources=sources)