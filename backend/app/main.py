from dotenv import load_dotenv
from pathlib import Path
import os

# Загружаем .env ИЗ КОРНЯ ПРОЕКТА (до импорта роутеров)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import init_db, health_check
from app.routers import documents, rag

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="AI Document Intelligence Platform",
    description="RAG-based document Q&A system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(rag.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "AI Document Intelligence Platform", "version": "1.0.0"}

@app.get("/health")
async def health():
    db_ok = await health_check()
    return {"status": "healthy" if db_ok else "unhealthy", "database": "connected" if db_ok else "disconnected"}