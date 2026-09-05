# 🧠 AI Document Intelligence Platform

**RAG-система для анализа документов** — загружай PDF, задавай вопросы, получай точные ответы с цитатами из документа.

![CI](https://github.com/mivlabs/ai-document-platform/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-blue)
![License](https://img.shields.io/badge/License-MIT-orange)

## 🚀 Возможности

- 📄 **Загрузка PDF** — автоматическое разбиение на чанки с перекрытием
- 🔍 **Векторный поиск** — PostgreSQL + pgvector, cosine similarity
- 🤖 **AI ответы** — Llama 3.3 70B через OpenRouter
- 💬 **Telegram бот** — удобный интерфейс с inline-кнопками
- 📊 **Streamlit Dashboard** — красивая веб-админка
- 🎯 **Честность** — если ответа нет в документе, бот так и скажет

## 🏗 Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│  FastAPI Backend │────▶│  PostgreSQL     │
│  (aiogram)      │     │  + RAG Pipeline  │     │  + pgvector     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐     ┌──────────────────┐
│ Streamlit       │     │  OpenRouter API  │
│ Dashboard       │     │  (LLM + Embed)   │
└─────────────────┘     └──────────────────┘
```

## 🛠 Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI, SQLAlchemy, asyncpg |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis (кэш ответов `/rag/query` по хэшу запроса, TTL 1 час) |
| LLM | Llama 3.3 70B (OpenRouter) |
| Embeddings | OpenAI text-embedding-3-small |
| Telegram | aiogram 3.x |
| Dashboard | Streamlit |
| Containerization | Docker Compose |

## 📦 Установка

### 1. Клонировать репозиторий
```bash
git clone https://github.com/mivlabs/ai-document-platform.git
cd ai-document-platform
```

### 2. Поднять базу данных
```bash
docker-compose up postgres redis -d
```

### 3. Установить зависимости
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# или source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 4. Настроить окружение
Создай `.env` в корне проекта:
```env
OPENROUTER_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/documents
REDIS_URL=redis://localhost:6379
```

### 5. Запустить backend
```bash
cd backend
uvicorn app.main:app --reload
```

### 6. Запустить Telegram бота
```bash
python bot.py
```

### 7. Запустить dashboard
```bash
cd dashboard
pip install streamlit httpx
streamlit run app.py
```

## 🎯 Использование

### Telegram бот
1. Найди бота в Telegram
2. Отправь PDF файл (до 20 MB)
3. Задай вопрос — получи ответ с цитатами

### Streamlit Dashboard
Открой `http://localhost:8501` — загружай документы, задавай вопросы, управляй базой.

### API
Открой `http://localhost:8000/docs` — интерактивная Swagger документация.

## 📂 Структура проекта

```
ai-document-platform/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── documents.py    # Загрузка и список документов
│   │   │   └── rag.py          # RAG pipeline
│   │   ├── models/
│   │   │   └── document.py     # SQLAlchemy модели
│   │   ├── services/
│   │   │   ├── embeddings.py   # OpenAI embeddings
│   │   │   └── pdf_parser.py   # Парсинг PDF + chunking
│   │   ├── database.py         # DB connection
│   │   └── main.py             # FastAPI app
│   └── requirements.txt
├── dashboard/
│   └── app.py                  # Streamlit UI
├── bot.py                      # Telegram bot
├── docker-compose.yml
├── .env
└── README.md
```

## 🔑 Ключевые фичи

### RAG Pipeline
1. **Chunking** — PDF разбивается на чанки по 1000 токенов с перекрытием 200
2. **Embeddings** — каждый чанк превращается в вектор (1536 dim)
3. **Vector Search** — pgvector ищет ближайшие чанки по cosine distance
4. **LLM Generation** — Llama 3.3 70B генерирует ответ на основе контекста
5. **Relevance Filter** — если max relevance < 0.10, бот честно говорит "нет информации"

### Работа с несколькими документами (не multi-user!)
- Telegram-бот хранит список загруженных document_id в памяти процесса, по chat_id
- RAG-запрос можно ограничить конкретными `document_ids`
- **Важно:** это не изоляция пользователей на уровне бэкенда — в API нет аутентификации,
  и любой клиент, знающий `document_id`, может обратиться к нему напрямую через
  `/rag/query`. Разделение "видит только свои документы" сейчас существует только
  в клиентском состоянии Telegram-бота, а не как гарантия сервера. Для реальной
  multi-user изоляции нужна аутентификация + `owner_id` в таблице `documents` — это в Roadmap.

## 🚧 Roadmap

- [ ] Поддержка DOCX, TXT файлов
- [ ] OCR для сканов PDF
- [ ] Hybrid search (BM25 + vector)
- [ ] Аутентификация пользователей + owner_id на документах (см. предупреждение выше про multi-user)
- [ ] Деплой на VPS
- [x] CI/CD через GitHub Actions
- [x] pytest (SQL-инъекция в `/rag/query`, upload/list/delete документов, кэш)

## 🧪 Тестирование

```bash
docker-compose up -d postgres redis
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

Тесты создают/дропают таблицы на каждый тест (нужен Postgres с расширением
`vector` — обычный `postgres:16` не подойдёт, используется образ
`pgvector/pgvector:pg16`, как и в `docker-compose.yml`). LLM и embeddings
в тестах замоканы — реальных вызовов к OpenRouter не происходит, `OPENROUTER_API_KEY`
не нужен.

## 📄 License

MIT
