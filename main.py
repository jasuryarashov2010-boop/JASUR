import asyncio, logging, sqlite3, re, os, threading
import pandas as pd
from aiohttp import web 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- UYG'OQ TUTISH UCHUN VEB-SERVER (RENDER UCHUN TO'G'IRLANDI) ---
async def handle(request):
    return web.Response(text="Bot is live and running!")

def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    # Render portni 'PORT' o'zgaruvchisi orqali beradi, agar bo'lmasa 8080 ishlatadi
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host='0.0.0.0', port=port)

# --- SOZLAMALAR ---
TOKEN = "8787202401:AAG7xJkTycIavNpbqJfvHE-S2QdxH-ushRg"
ADMIN_ID = 8588645504
ADMIN_LINK = "https://t.me/jasurbek_o10"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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

def clean_input(text):
    return "".join(re.findall(r'[a-zA-Z]', text.lower()))

# --- KLAVIATURA ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="📝 Test ishlash"), KeyboardButton(text="✅ Testni tekshirish")],
        [KeyboardButton(text="📊 Natijalarim"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="📞 Admin")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Paneli")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    db_query("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (message.from_user.id, message.from_user.full_name))
    await message.answer(f"👋 Salom, **{message.from_user.full_name}**!", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")

# --- ADMIN: TESTLAR BO'YICHA STATISTIKA ---
async def admin_detailed_stats_menu(message: types.Message):
    rows = db_query("SELECT kod FROM tests", fetch=True)
    if not rows: return await message.answer("📭 Bazada testlar yo'q.")
    
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 Kod: {r[0]} statistikasi", callback_data=f"stat_{r[0]}")] 
        for r in rows
    ])
    await message.answer("📈 Qaysi test bo'yicha natijalarni ko'rmoqchisiz?", reply_markup=ikb)

@dp.callback_query(F.data.startswith("stat_"))
async def show_test_results(call: types.CallbackQuery):
    test_kod = call.data.split("_")[1]
    query = "SELECT u.name, r.ball, r.foiz FROM results r JOIN users u ON r.user_id = u.id WHERE r.kod = ? ORDER BY r.ball DESC"
    results = db_query(query, (test_kod,), fetch=True)
    
    if not results: return await call.answer(f"⚠️ Natijalar yo'q.", show_alert=True)

    text = f"📊 **Kod: {test_kod} bo'yicha natijalar:**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    for i, (name, ball, foiz) in enumerate(results, 1):
        text += f"{i}. **{name}** - `{ball}` ball ({foiz}%)\n"
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()

# --- ASOSIY BOSHQARUV ---
@dp.message(F.text.in_({"📝 Test ishlash", "📊 Natijalarim", "👤 Profilim", "📞 Admin", "⚙️ Admin Paneli", "📊 Batafsil Statistika", "📢 Xabar yuborish", "📥 Excel Yuklash", "⬅️ Orqaga"}))
async def handle_buttons(message: types.Message, state: FSMContext):
    await state.clear()
    t = message.text
    
    if t == "📝 Test ishlash":
        await tests_list(message)
    elif t == "📊 Natijalarim":
        await my_res(message)
    elif t == "👤 Profilim":
        await profile(message)
    elif t == "📞 Admin":
        await message.answer(f"👨‍💻 Admin: {ADMIN_LINK}")
    elif t == "⚙️ Admin Paneli" and message.from_user.id == ADMIN_ID:
        await admin_menu_h(message)
    elif t == "📊 Batafsil Statistika" and message.from_user.id == ADMIN_ID:
        await admin_detailed_stats_menu(message)
    elif t == "📢 Xabar yuborish" and message.from_user.id == ADMIN_ID:
        await message.answer("📝 Xabarni yozing:")
        await state.set_state(BotStates.broadcast_msg)
    elif t == "📥 Excel Yuklash" and message.from_user.id == ADMIN_ID:
        await export_users_to_excel(message)
    elif t == "⬅️ Orqaga":
        await message.answer("🏠 Asosiy menyu", reply_markup=main_menu(message.from_user.id))

# --- ADMIN: EXCEL EKSPORT ---
async def export_users_to_excel(message: types.Message):
    await message.answer("⏳ Tayyorlanmoqda...")
    query = "SELECT u.id, u.name, COUNT(r.id), IFNULL(SUM(r.ball), 0) FROM users u LEFT JOIN results r ON u.id = r.user_id GROUP BY u.id"
    rows = db_query(query, fetch=True)
    df = pd.DataFrame(rows, columns=['Telegram ID', 'Ism', 'Testlar', 'Jami Ball'])
    df.to_excel("users.xlsx", index=False)
    await message.answer_document(FSInputFile("users.xlsx"), caption="📊 Foydalanuvchilar ro'yxati")
    os.remove("users.xlsx")

# --- ADMIN: XABAR TARQATISH ---
@dp.message(BotStates.broadcast_msg)
async def send_broadcast(message: types.Message, state: FSMContext):
    users = db_query("SELECT id FROM users", fetch=True)
    for u in users:
        try: await bot.send_message(u[0], message.text)
        except: continue
    await message.answer("✅ Yuborildi.", reply_markup=main_menu(ADMIN_ID))
    await state.clear()

# --- TEST TEKSHIRISH ---
@dp.message(F.text == "✅ Testni tekshirish")
async def check_step1(message: types.Message, state: FSMContext):
    await message.answer("🔢 **Test kodini yuboring:**")
    await state.set_state(BotStates.waiting_for_kod)

@dp.message(BotStates.waiting_for_kod, F.text)
async def check_step2(message: types.Message, state: FSMContext):
    kod = message.text.strip()
    res = db_query("SELECT javob FROM tests WHERE kod=?", (kod,), fetch=True)
    if res:
        await state.update_data(kod=kod, correct=res[0][0])
        await message.answer(f"✅ Kod topildi. Javoblarni yuboring (masalan: abcd...):")
        await state.set_state(BotStates.waiting_for_answers)
    else: await message.answer("❌ Xato kod.")

@dp.message(BotStates.waiting_for_answers, F.text)
async def check_step3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct_ans = data['correct']
    user_ans = clean_input(message.text)
    ball, xato_detal = 0, []
    for i in range(len(correct_ans)):
        u = user_ans[i] if i < len(user_ans) else "?"
        if u == correct_ans[i]: ball += 1
        else: xato_detal.append(f"❌ {i+1}: Siz '{u}', To'g'ri '{correct_ans[i]}'")
    
    foiz = round((ball / len(correct_ans)) * 100, 1)
    db_query("INSERT INTO results (user_id, kod, ball, foiz, xatolar) VALUES (?, ?, ?, ?, ?)", 
             (message.from_user.id, data['kod'], ball, foiz, "\n".join(xato_detal) or "Xato yo'q!"))
    await message.answer(f"🏁 Natija: {ball}/{len(correct_ans)} ({foiz}%)", reply_markup=main_menu(message.from_user.id))
    await state.clear()

# --- NATIJALARIM ---
async def my_res(message: types.Message):
    rows = db_query("SELECT id, kod, ball, foiz FROM results WHERE user_id=? ORDER BY id DESC LIMIT 10", (message.from_user.id,), fetch=True)
    if not rows: return await message.answer("🧐 Natijalar yo'q.")
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📊 Kod: {r[1]} | {r[2]} ball", callback_data=f"v_{r[0]}")] for r in rows])
    await message.answer("📂 Oxirgi natijalaringiz (Tahlil uchun bosing):", reply_markup=ikb)

@dp.callback_query(F.data.startswith("v_"))
async def view_analysis(call: types.CallbackQuery):
    r_id = call.data.split("_")[1]
    res = db_query("SELECT kod, ball, foiz, xatolar FROM results WHERE id=?", (r_id,), fetch=True)
    if res:
        msg = f"📝 **Tahlil (Kod: {res[0][0]})**\n🏆 Ball: `{res[0][1]}` ({res[0][2]}%)\n\n**Xatolar:**\n{res[0][3]}"
        await call.message.answer(msg, parse_mode="Markdown")
    await call.answer()

# --- ADMIN PANEL ---
async def admin_menu_h(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Qo'shish"), KeyboardButton(text="🗑 O'chirish")],
        [KeyboardButton(text="📊 Batafsil Statistika"), KeyboardButton(text="📥 Excel Yuklash")],
        [KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="⬅️ Orqaga")]
    ], resize_keyboard=True)
    await message.answer("🛠 **Admin paneli:**", reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "➕ Qo'shish", F.from_user.id == ADMIN_ID)
async def a_add1(message: types.Message, state: FSMContext):
    await message.answer("📁 PDF yuboring:")
    await state.set_state(BotStates.admin_pdf)

@dp.message(BotStates.admin_pdf, F.document)
async def a_add2(message: types.Message, state: FSMContext):
    await state.update_data(pdf_id=message.document.file_id)
    await message.answer("🔢 Test kodini yozing:")
    await state.set_state(BotStates.admin_kod)

@dp.message(BotStates.admin_kod)
async def a_add3(message: types.Message, state: FSMContext):
    await state.update_data(kod=message.text.strip())
    await message.answer("✅ To'g'ri javoblarni yuboring:")
    await state.set_state(BotStates.admin_ans)

@dp.message(BotStates.admin_ans)
async def a_add4(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO tests (kod, javob, pdf_id) VALUES (?, ?, ?)", (data['kod'], clean_input(message.text), data['pdf_id']))
    await message.answer("✅ Qo'shildi!", reply_markup=main_menu(ADMIN_ID))
    await state.clear()

@dp.message(F.text == "🗑 O'chirish", F.from_user.id == ADMIN_ID)
async def a_del(message: types.Message):
    rows = db_query("SELECT kod FROM tests", fetch=True)
    if not rows: return await message.answer("Testlar yo'q.")
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"❌ {r[0]}", callback_data=f"del_{r[0]}")] for r in rows])
    await message.answer("O'chirishni tanlang:", reply_markup=ikb)

@dp.callback_query(F.data.startswith("del_"))
async def a_del_conf(call: types.CallbackQuery):
    kod = call.data.split("_")[1]
    db_query("DELETE FROM tests WHERE kod=?", (kod,))
    await call.message.edit_text(f"O'chirildi: {kod}")
    await call.answer()

async def tests_list(message: types.Message):
    rows = db_query("SELECT kod FROM tests", fetch=True)
    if not rows: return await message.answer("📭 Testlar yo'q.")
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📄 Kod: {r[0]}", callback_data=f"p_{r[0]}")] for r in rows])
    await message.answer("📚 Mavjud testlar:", reply_markup=ikb)

@dp.callback_query(F.data.startswith("p_"))
async def send_pdf(call: types.CallbackQuery):
    kod = call.data.split("_")[1]
    res = db_query("SELECT pdf_id FROM tests WHERE kod=?", (kod,), fetch=True)
    if res: await call.message.answer_document(res[0][0], caption=f"✅ Test kodi: `{kod}`")
    await call.answer()

async def profile(message: types.Message):
    res = db_query("SELECT COUNT(*), SUM(ball) FROM results WHERE user_id=?", (message.from_user.id,), fetch=True)
    text = f"👤 **Profil: {message.from_user.full_name}**\n🆔 ID: `{message.from_user.id}`\n📝 Testlar: `{res[0][0]}` ta\n🏆 Jami ball: `{res[0][1] or 0}`"
    await message.answer(text, parse_mode="Markdown")

async def main():
    # Veb-serverni alohida oqimda ishga tushirish (Render uchun)
    threading.Thread(target=run_web_server, daemon=True).start()
    
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
