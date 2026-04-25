import asyncio, logging, sqlite3, re, os, threading
import pandas as pd
from aiohttp import web 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from groq import Groq  # Groq kutubxonasi

# --- UYG'OQ TUTISH UCHUN VEB-SERVER ---
async def handle(request):
    return web.Response(text="Bot is live and running!")

def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host='0.0.0.0', port=port)

# --- SOZLAMALAR ---
TOKEN = "8787202401:AAFjQIkQrvKiZisdQwd27CuPC3Q7OwCHi3s"
GROQ_API_KEY = "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"
ADMIN_ID = 8588645504
ADMIN_LINK = "https://t.me/jasurbek_o10"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = Groq(api_key=GROQ_API_KEY)

# --- BAZA FUNKSIYALARI ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect("bot_bazasi.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    db_query("CREATE TABLE IF NOT EXISTS tests (kod TEXT PRIMARY KEY, javob TEXT, pdf_id TEXT)")
    db_query("CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kod TEXT, ball INTEGER, foiz REAL, xatolar TEXT)")

class BotStates(StatesGroup):
    waiting_for_kod = State()
    waiting_for_answers = State()
    admin_pdf = State()
    admin_kod = State()
    admin_ans = State()
    broadcast_msg = State()
    waiting_for_ai = State() # AI uchun yangi holat

def clean_input(text):
    return "".join(re.findall(r'[a-zA-Z]', text.lower()))

# --- KLAVIATURA ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="📝 Test ishlash"), KeyboardButton(text="✅ Testni tekshirish")],
        [KeyboardButton(text="📊 Natijalarim"), KeyboardButton(text="🤖 AI tushuntirgich")],
        [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="📞 Admin")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Paneli")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- AI HANDLER ---
@dp.message(F.text == "🤖 AI tushuntirgich")
async def ai_start(message: types.Message, state: FSMContext):
    back_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)
    await message.answer("🤖 Men AI yordamchisiman. Tushunmagan savolingizni yozib yuboring, men uni batafsil tushuntirib beraman.", reply_markup=back_kb)
    await state.set_state(BotStates.waiting_for_ai)

@dp.message(BotStates.waiting_for_ai)
async def ai_answer(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("Asosiy menyu", reply_markup=main_menu(message.from_user.id))
    
    status_msg = await message.answer("🤔 Savolni o'rganyapman...")
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sen foydali o'qituvchisan. Savollarni o'zbek tilida tushuntir."},
                {"role": "user", "content": message.text}
            ],
            model="llama3-8b-8192",
        )
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=f"✅ **AI Tahlili:**\n\n{completion.choices[0].message.content}"
        )
    except Exception as e:
        await bot.edit_message_text(chat_id=message.chat.id, message_id=status_msg.message_id, text="❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")

# --- START ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    db_query("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (message.from_user.id, message.from_user.full_name))
    await message.answer(f"👋 Salom, **{message.from_user.full_name}**!", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")

# ... (Qolgan test tekshirish va admin funksiyalari o'z holicha qoladi) ...

# --- MAIN ---
async def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
