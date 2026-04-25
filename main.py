import asyncio, logging, sqlite3, re, os, threading
import pandas as pd
from aiohttp import web 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from groq import Groq

# --- KONFIGURATSIYA ---
TOKEN = "8787202401:AAFjQsaIkQrvKiZisdQwd27CuPC3Q7OwCHi3s"
GROQ_API_KEY = "gsk_0RLam5dfr9e1CBqFBf0SWWGdyb3FYyHlYJ7LexVgHazACm8dznX71"
ADMIN_ID = 8588645504

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = Groq(api_key=GROQ_API_KEY)

# --- WEB SERVER (RENDER UCHUN) ---
async def handle(request): return web.Response(text="Bot is active!")
def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- STATELAR ---
class BotStates(StatesGroup):
    waiting_for_kod = State()
    waiting_for_answers = State()
    waiting_for_ai = State() 

# --- AI SISTEMA KO'RSATMASI (SYSTEM PROMPT) ---
# AI ga o'z rolini tushuntiramiz
AI_ROLE = """
Sen mukammal o'qituvchi va repetitorsan. 
Vazifang: Foydalanuvchi yuborgan test savollarini tahlil qilish.
Qoidalaring:
1. Javobni doim O'zbek tilida ber.
2. Savolning yechimini bosqichma-bosqich tushuntir.
3. Agar savolda xatolik bo'lsa, uni ko'rsat.
4. Javobingda Markdown (qalin matn, kursiv, ro'yxatlar) ishlatib, uni chiroyli ko'rsat.
5. Faqat to'g'ri javobni aytib qo'yma, nima uchun aynan shu javob to'g'riligini isbotlab ber.
"""

# --- KLAVIATURALAR ---
def main_menu():
    kb = [
        [KeyboardButton(text="📝 Test ishlash"), KeyboardButton(text="✅ Testni tekshirish")],
        [KeyboardButton(text="🤖 AI Tahlilchi"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="📞 Admin")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Chiqish")]], resize_keyboard=True)

# --- AI HANDLER (MUKAMMAL VERSION) ---
@dp.message(F.text == "🤖 AI Tahlilchi")
async def ai_entry(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_ai)
    await message.answer(
        "🌟 **Mukammal AI Tahlil tizimiga xush kelibsiz!**\n\n"
        "Tushunmagan savolingizni matn shaklida yuboring. Men uni nafaqat yechib beraman, "
        "balki mavzuni tushunishingizga yordam beraman.",
        reply_markup=back_menu(),
        parse_mode="Markdown"
    )

@dp.message(BotStates.waiting_for_ai)
async def process_ai_request(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Chiqish":
        await state.clear()
        return await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu())

    # Foydalanuvchi kutishini ko'rsatish
    process_msg = await message.answer("🔍 **Savol tahlil qilinmoqda...**", parse_mode="Markdown")
    
    try:
        # AI ga so'rov yuborish
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": AI_ROLE},
                {"role": "user", "content": message.text}
            ],
            model="llama3-70b-8192", # Kuchliroq model (70b) ishlatamiz
            temperature=0.6, # Aniqroq javob uchun
            max_tokens=2048
        )
        
        ai_response = completion.choices[0].message.content

        # Javobni qismlarga bo'lish (agar juda uzun bo'lsa)
        if len(ai_response) > 4000:
            for i in range(0, len(ai_response), 4000):
                await message.answer(ai_response[i:i+4000], parse_mode="Markdown")
        else:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=process_msg.message_id,
                text=ai_response,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"AI Error: {e}")
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=process_msg.message_id,
            text="❌ **Kechirasiz, tahlil qilishda xatolik yuz berdi.**\n"
                 "Ehtimol, savol juda murakkab yoki tizim band. Qaytadan urinib ko'ring.",
            parse_mode="Markdown"
        )

# --- START VA ASOSIY LOGIKA ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        f"Assalomu alaykum, {message.from_user.full_name}!\n"
        "Bu bot orqali testlar ishlashingiz va AI yordamida savollarni tahlil qilishingiz mumkin.",
        reply_markup=main_menu()
    )

async def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
