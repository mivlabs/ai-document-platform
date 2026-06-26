import streamlit as st
import httpx
import os
from datetime import datetime

BACKEND_URL = "http://localhost:8000"

# Настройки страницы
st.set_page_config(
    page_title="AI Document Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кастомный CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2c3e50;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.6rem 1.2rem;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

# Заголовок
st.markdown('<div class="main-header">🧠 AI Document Intelligence Platform</div>', unsafe_allow_html=True)
st.markdown("Загружай документы, задавай вопросы, получай ответы с цитатами")

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
    st.markdown("### Меню")
    menu = st.radio(
        "Выбери раздел:",
        ["📊 Dashboard", "📤 Загрузить документ", "💬 Задать вопрос", "📚 Мои документы"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### Статус")
    try:
        response = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        if response.status_code == 200:
            st.success("✅ Backend работает")
        else:
            st.error("❌ Backend недоступен")
    except:
        st.error("❌ Backend недоступен")

# === DASHBOARD ===
if menu == "📊 Dashboard":
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            response = httpx.get(f"{BACKEND_URL}/documents/", timeout=5.0)
            docs = response.json().get("documents", [])
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 2.5rem; font-weight: 700;">{len(docs)}</div>
                <div>📄 Документов</div>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 2.5rem; font-weight: 700;">—</div>
                <div>📄 Документов</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <div style="font-size: 2.5rem; font-weight: 700;">RAG</div>
            <div>🤖 Модель</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <div style="font-size: 2.5rem; font-weight: 700;">pgvector</div>
            <div>🗄 База данных</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🚀 Возможности")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **📄 Загрузка документов**
        - PDF файлы до 20 MB
        - Автоматическое разбиение на чанки
        - Создание векторных embeddings
        """)
        
        st.markdown("""
        **🔍 Векторный поиск**
        - PostgreSQL + pgvector
        - Cosine similarity
        - Топ-N релевантных фрагментов
        """)
    
    with col2:
        st.markdown("""
        **🤖 AI ответы**
        - Llama 3.3 70B через OpenRouter
        - Ответы на основе документа
        - Честность: если нет ответа — скажет
        """)
        
        st.markdown("""
        **💬 Telegram бот**
        - Интерфейс в Telegram
        - История документов
        - Красивые кнопки
        """)

# === UPLOAD ===
elif menu == "📤 Загрузить документ":
    st.markdown('<div class="sub-header">📤 Загрузка документа</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Выбери PDF файл", type=["pdf"])
    
    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.info(f"📄 {uploaded_file.name} ({file_size_mb:.2f} MB)")
        
        if file_size_mb > 20:
            st.error(f"⚠️ Файл слишком большой ({file_size_mb:.1f} MB). Лимит: 20 MB")
        else:
            if st.button("🚀 Загрузить и обработать"):
                with st.spinner("⏳ Загружаю и создаю embeddings..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                        response = httpx.post(
                            f"{BACKEND_URL}/documents/upload",
                            files=files,
                            timeout=300.0
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            st.success(f"✅ Документ загружен!")
                            st.balloons()
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("📄 Файл", data["filename"])
                            with col2:
                                st.metric("📊 Фрагментов", data["total_chunks"])
                        else:
                            st.error(f"❌ Ошибка: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {str(e)}")

# === QUERY ===
elif menu == "💬 Задать вопрос":
    st.markdown('<div class="sub-header">💬 Вопрос по документам</div>', unsafe_allow_html=True)
    
    # Получаем список документов
    try:
        response = httpx.get(f"{BACKEND_URL}/documents/", timeout=5.0)
        docs = response.json().get("documents", [])
        
        if not docs:
            st.warning("📭 Сначала загрузи документ в разделе 'Загрузить документ'")
        else:
            query = st.text_area(
                "Задай вопрос по загруженным документам:",
                placeholder="Например: О чём этот документ? Какие основные мысли?",
                height=100
            )
            
            col1, col2 = st.columns([3, 1])
            with col2:
                top_k = st.slider("Глубина поиска", 3, 20, 10)
            
            if st.button("🔍 Найти ответ") and query:
                with st.spinner("🤔 Анализирую документы..."):
                    try:
                        response = httpx.post(
                            f"{BACKEND_URL}/rag/query",
                            json={"query": query, "top_k": top_k},
                            timeout=60.0
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            st.markdown("### 💡 Ответ")
                            st.info(data["answer"])
                            
                            if data["sources"]:
                                st.markdown("### 📚 Источники")
                                for i, src in enumerate(data["sources"], 1):
                                    with st.expander(f"📄 Фрагмент {i} (релевантность: {src['relevance_score']*100:.0f}%)"):
                                        st.markdown(src["text_preview"])
                        else:
                            st.error(f"❌ Ошибка: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {str(e)}")
    except:
        st.error("❌ Backend недоступен")

# === DOCUMENTS ===
elif menu == "📚 Мои документы":
    st.markdown('<div class="sub-header">📚 Загруженные документы</div>', unsafe_allow_html=True)
    
    try:
        response = httpx.get(f"{BACKEND_URL}/documents/", timeout=5.0)
        docs = response.json().get("documents", [])
        
        if not docs:
            st.info("📭 Пока нет загруженных документов")
        else:
            for doc in docs:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**📄 {doc['filename']}**")
                    with col2:
                        size_kb = doc['file_size'] / 1024
                        st.caption(f"{size_kb:.1f} KB")
                    with col3:
                        created = doc['created_at'][:10] if doc.get('created_at') else ""
                        st.caption(created)
                    
                    if st.button(f"🗑 Удалить {doc['id']}", key=doc['id']):
                        try:
                            del_response = httpx.delete(
                                f"{BACKEND_URL}/documents/{doc['id']}",
                                timeout=30.0
                            )
                            if del_response.status_code == 200:
                                st.success(f"✅ Удалён: {doc['filename']}")
                                st.rerun()
                            else:
                                st.error(f"❌ Ошибка: {del_response.text}")
                        except Exception as e:
                            st.error(f"❌ Ошибка: {str(e)}")
                    
                    st.markdown("---")
    except:
        st.error("❌ Backend недоступен")

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #888; font-size: 0.9rem;">'
    '🧠 Built with FastAPI + PostgreSQL + pgvector + LangChain + Streamlit'
    '</div>',
    unsafe_allow_html=True
)