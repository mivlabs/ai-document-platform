import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_URL = "http://localhost:8000"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище документов по пользователям
user_documents = {}

# Клавиатура "Назад"
back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

async def show_main_menu(message_or_callback, edit=False):
    """Показывает главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📚 Помощь", callback_data="help"),
            InlineKeyboardButton(text="💬 Задать вопрос", callback_data="ask")
        ],
        [
            InlineKeyboardButton(text="📄 Мои документы", callback_data="list"),
            InlineKeyboardButton(text="🗑 Очистить", callback_data="clear")
        ]
    ])
    
    text = (
        "👋 Привет! Я AI Document Assistant.\n\n"
        "📄 Отправь мне PDF — я его проанализирую.\n"
        "❓ Задай вопрос — я отвечу по документу.\n\n"
        "Выбери действие:"
    )
    
    if edit:
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await message_or_callback.answer(text, reply_markup=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await show_main_menu(message)

@dp.callback_query(F.data == "back")
async def callback_back(callback: CallbackQuery):
    await show_main_menu(callback, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 Как пользоваться:\n\n"
        "1️⃣ Отправь PDF файл (до 20 MB)\n"
        "2️⃣ Дождись подтверждения\n"
        "3️⃣ Задай вопрос по документу\n"
        "4️⃣ Получи ответ по документу",
        reply_markup=back_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "ask")
async def callback_ask(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_documents or not user_documents[user_id]:
        await callback.message.edit_text(
            "⚠️ Сначала загрузи PDF документ!\n\n"
            "Просто отправь мне файл PDF.",
            reply_markup=back_keyboard
        )
    else:
        await callback.message.edit_text(
            "💬 Отлично! Просто напиши свой вопрос.\n\n"
            "Например:\n"
            "• О чём этот документ?\n"
            "• Какие основные мысли?\n"
            "• Что сказано про X?",
            reply_markup=back_keyboard
        )
    await callback.answer()

@dp.callback_query(F.data == "list")
async def callback_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_documents or not user_documents[user_id]:
        await callback.message.edit_text(
            "📭 У тебя пока нет загруженных документов.",
            reply_markup=back_keyboard
        )
    else:
        text = "📚 Твои документы:\n\n"
        for i, doc in enumerate(user_documents[user_id], 1):
            text += f"{i}. {doc['filename']}\n\n"
        await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "clear")
async def callback_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_documents[user_id] = []
    await callback.message.edit_text(
        "🗑 Все документы очищены!",
        reply_markup=back_keyboard
    )
    await callback.answer()

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 Как пользоваться:\n\n"
        "1️⃣ Отправь PDF файл (до 20 MB)\n"
        "2️⃣ Дождись подтверждения загрузки\n"
        "3️⃣ Задай вопрос по документу\n"
        "4️⃣ Получи ответ с цитатами из документа\n\n"
        "💡 Примеры вопросов:\n"
        "• О чём этот документ?\n"
        "• Какие основные мысли?\n"
        "• Что сказано про X?\n\n"
        "⚠️ Лимит Telegram: 20 MB на файл\n"
        "Для больших файлов используй веб-интерфейс."
    )

@dp.message(Command("list"))
async def cmd_list(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_documents or not user_documents[user_id]:
        await message.answer("📭 У тебя пока нет загруженных документов.")
        return
    
    text = "📚 Твои документы:\n\n"
    for i, doc in enumerate(user_documents[user_id], 1):
        text += f"{i}. {doc['filename']}\n\n"
    
    await message.answer(text)

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    user_documents[user_id] = []
    await message.answer("🗑 Все документы очищены!")

@dp.message(F.document & (F.document.mime_type == "application/pdf"))
async def handle_pdf(message: Message):
    file_size_mb = message.document.file_size / (1024 * 1024)
    
    if file_size_mb > 20:
        await message.answer(
            f"⚠️ Файл слишком большой ({file_size_mb:.1f} MB).\n\n"
            f"Лимит Telegram: 20 MB.\n\n"
            f"💡 Решения:\n"
            f"• Раздели PDF на части\n"
            f"• Используй веб-интерфейс: http://localhost:8000/docs"
        )
        return
    
    await message.answer(f"📥 Загружаю PDF ({file_size_mb:.1f} MB)...\n⏳ Это может занять 1-3 минуты.")
    
    file = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    pdf_bytes = file_bytes.read()
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            files = {"file": (message.document.file_name, pdf_bytes, "application/pdf")}
            response = await client.post(f"{BACKEND_URL}/documents/upload", files=files)
            
            if response.status_code == 200:
                data = response.json()
                doc_id = data["document_id"]
                
                user_id = message.from_user.id
                if user_id not in user_documents:
                    user_documents[user_id] = []
                user_documents[user_id].append({
                    "id": doc_id,
                    "filename": data["filename"]
                })
                
                await message.answer(
                    f"✅ Документ загружен!\n"
                    f"📄 {data['filename']}\n\n"
                    f"💬 Задай мне вопрос — я отвечу по документу."
                )
            else:
                await message.answer(f"❌ Ошибка загрузки: {response.text}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(F.document)
async def handle_wrong_file(message: Message):
    await message.answer("⚠️ Я принимаю только PDF файлы!")

@dp.message(F.text)
async def handle_question(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_documents or not user_documents[user_id]:
        await message.answer("⚠️ Сначала загрузи PDF документ!\n\nИспользуй /help для инструкций.")
        return
    
    await message.answer("🤔 Анализирую документ...")
    
    user_doc_ids = [doc["id"] for doc in user_documents[user_id]]
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/rag/query",
                json={
                    "query": message.text,
                    "top_k": 15,
                    "document_ids": user_doc_ids
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data["answer"]
                
                # Просто ответ, без источников
                await message.answer(f"💡 {answer}")
            else:
                await message.answer(f"❌ Ошибка: {response.text}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

async def main():
    print("🤖 Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())