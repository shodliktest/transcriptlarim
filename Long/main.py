import asyncio
import os
import json
import threading
import pytz
import requests
from datetime import datetime
from bs4 import BeautifulSoup

import streamlit as st
from aiogram import Bot, Dispatcher, types, F, html
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. KONFIGURATSIYA ---
class Config:
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

def get_now():
    return datetime.now(Config.TZ).strftime('%Y.%m.%d %H:%M:%S')

# --- 2. LONGMAN LUG'ATI SCRAPERI ---
def scrape_longman(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            return "❌ Kechirasiz, so'z topilmadi yoki Longman bilan bog'lanishda xatolik."

        soup = BeautifulSoup(res.text, 'lxml')
        entry = soup.find('span', class_='dictentry')
        
        if not entry:
            return "❌ Bunday so'z Longman lug'atidan topilmadi. Iltimos, so'zning to'g'ri yozilganini tekshiring."

        # Ma'lumotlarni yig'ish
        hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
        pos = entry.find('span', class_='POS').text if entry.find('span', class_='POS') else ""
        pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
        definition = entry.find('span', class_='DEF').text if entry.find('span', class_='DEF') else "Ta'rif topilmadi."
        example = entry.find('span', class_='EXAMPLE').text if entry.find('span', class_='EXAMPLE') else ""

        response = f"📕 <b>Longman Dictionary</b>\n\n"
        response += f"🔑 <b>Word:</b> {hwd.upper()}\n"
        if pos: response += f"🏷 <b>Part of speech:</b> <i>{pos}</i>\n"
        if pron: response += f"🗣 <b>Pronunciation:</b> /{pron}/\n"
        response += f"\n📖 <b>Definition:</b>\n{definition}\n"
        if example: response += f"\n📝 <b>Example:</b>\n<i>{example.strip()}</i>"
        
        return response
    except Exception as e:
        return f"⚠️ Xatolik yuz berdi: {str(e)}"

# --- 3. FOYDALANUVCHILARNI RO'YXATGA OLISH ---
def log_user(user: types.User):
    if not os.path.exists(Config.USERS_DB):
        with open(Config.USERS_DB, "w") as f: json.dump([], f)
    with open(Config.USERS_DB, "r") as f:
        try: users = json.load(f)
        except: users = []
    if not any(u['id'] == user.id for u in users):
        users.append({
            "id": user.id, 
            "name": user.full_name, 
            "username": f"@{user.username}" if user.username else "N/A", 
            "date": get_now()
        })
        with open(Config.USERS_DB, "w") as f: json.dump(users, f, indent=4)

# --- 4. HANDLERLARNI RO'YXATGA OLISH ---
def register_all_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        log_user(m.from_user)
        
        welcome_text = (
            f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
            f"🤖 Men <b>Longman Dictionary Bot</b>man.\n\n"
            f"📚 <b>Nima qila olaman?</b>\n"
            f"• Inglizcha so'zlarning <b>mukammal ta'rifini</b> topib beraman.\n"
            f"• So'zlarning <b>transkripsiyasini</b> ko'rsataman.\n"
            f"• Gap ichida ishlatilishiga <b>misollar</b> keltiraman.\n\n"
            f"✍️ Shunchaki menga biror inglizcha so'z yuboring!"
        )
        
        kb = ReplyKeyboardBuilder()
        kb.button(text="🔍 Lug'atdan qidirish")
        await m.answer(welcome_text, reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "🔍 Lug'atdan qidirish")
    async def help_lookup(m: types.Message):
        await m.answer("📝 Iltimos, qidirayotgan so'zingizni yuboring:")

    @dp.message(F.text)
    async def handle_message(m: types.Message):
        if m.text.startswith('/'): return
        
        word = m.text.strip()
        # Bir nechta so'z bo'lsa (gap bo'lsa) lug'at qidirmaymiz
        if len(word.split()) > 2:
            await m.answer("⚠️ Iltimos, faqat bitta so'z yuboring. Men lug'at botiman, tarjimon emas.")
            return

        wait = await m.answer("🔍 <b>Longman</b> kutubxonasidan qidirilmoqda...")
        # Scraperni alohida thread'da ishga tushiramiz (bot qotib qolmasligi uchun)
        result = await asyncio.to_thread(scrape_longman, word)
        await wait.delete()
        await m.answer(result)

# --- 5. BOT RUNNER (THREADING & ASYNCIO) ---
@st.cache_resource
def start_bot_process():
    def _run_in_thread():
        async def main_bot():
            # Bot va Dispatcher aynan shu loop ichida yaratilishi shart (aiohttp qoidasi)
            bot_obj = Bot(
                token=Config.BOT_TOKEN, 
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            dp_obj = Dispatcher()
            
            register_all_handlers(dp_obj)
            
            # Webhooklarni tozalash
            await bot_obj.delete_webhook(drop_pending_updates=True)
            
            try:
                # handle_signals=False — Thread ichida ishlash uchun majburiy
                await dp_obj.start_polling(bot_obj, handle_signals=False)
            finally:
                await bot_obj.session.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main_bot())

    thread = threading.Thread(target=_run_in_thread, daemon=True)
    thread.start()
    return thread

# --- 6. STREAMLIT INTERFACE ---
st.set_page_config(page_title="Longman Server", page_icon="📕")
st.title("📕 Longman Bot Server Control")

# Botni fonda ishga tushirish
bot_thread = start_bot_process()

st.success("🤖 Bot Online holatda!")
st.info("Bu server Longman Dictionary API vazifasini bajarmoqda.")

# Statistika bo'limi
if os.path.exists(Config.USERS_DB):
    with open(Config.USERS_DB, "r") as f:
        users_data = json.load(f)
    
    col1, col2 = st.columns(2)
    col1.metric("Foydalanuvchilar", len(users_data))
    col2.metric("Server Status", "Aktiv")
    
    st.write("### Oxirgi 5 ta foydalanuvchi")
    st.table(users_data[-5:])

if st.button("🔄 Serverni yangilash"):
    st.rerun()
