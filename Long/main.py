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

# --- 1. SINGLE CONFIGURATION ---
class Config:
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

def get_now():
    return datetime.now(Config.TZ).strftime('%Y.%m.%d %H:%M:%S')

# --- 2. LONGMAN SCRAPER (MUKAMMAL) ---
def scrape_longman(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            return "❌ So'z topilmadi yoki Longman saytida texnik ishlar ketmoqda."

        soup = BeautifulSoup(res.text, 'lxml')
        entry = soup.find('span', class_='dictentry')
        
        if not entry:
            return "❌ Kechirasiz, Longman lug'atidan bunday so'z topilmadi."

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
        return f"⚠️ Xatolik: {str(e)}"

# --- 3. DATABASE LOGIC ---
def log_user(user: types.User):
    if not os.path.exists(Config.USERS_DB):
        with open(Config.USERS_DB, "w") as f: json.dump([], f)
    with open(Config.USERS_DB, "r") as f:
        try: users = json.load(f)
        except: users = []
    if not any(u['id'] == user.id for u in users):
        users.append({"id": user.id, "name": user.full_name, "username": f"@{user.username}" if user.username else "N/A", "date": get_now()})
        with open(Config.USERS_DB, "w") as f: json.dump(users, f, indent=4)

# --- 4. RESOURCE CACHING & WEBHOOK KILLER ---
@st.cache_resource
def load_bot():
    bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Webhook Killer
    async def clear_webhook():
        await bot.delete_webhook(drop_pending_updates=True)
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(clear_webhook())
    return bot, dp

bot, dp = load_bot()

# --- 5. TELEGRAM HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    log_user(m.from_user)
    kb = ReplyKeyboardBuilder()
    kb.button(text="🔍 Lug'atdan qidirish")
    await m.answer(f"Salom {m.from_user.first_name}!\nInglizcha so'z yuboring, men uni Longmandan topib beraman.", 
                   reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "🔍 Lug'atdan qidirish")
async def ask_word(m: types.Message):
    await m.answer("So'zni kiriting (masalan: <i>success</i>):")

@dp.message(F.text)
async def lookup(m: types.Message):
    if m.text.startswith('/'): return
    
    # Faqat bitta so'z ekanligini tekshirish (lug'at uchun)
    word = m.text.strip()
    if len(word.split()) > 2:
        await m.answer("Iltimos, faqat bitta so'z yuboring.")
        return

    wait = await m.answer("🔍 Longmandan qidirilmoqda...")
    result = await asyncio.to_thread(scrape_longman, word)
    await wait.delete()
    await m.answer(result)

# --- 6. SINGLE THREAD RUNNER ---
@st.cache_resource
def start_bot_process():
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.start_polling(bot))
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

# --- 7. STREAMLIT INTERFACE ---
st.set_page_config(page_title="Longman Bot Server", page_icon="📕")
st.title("📕 Longman Dictionary Bot")

# Botni fonda ishga tushirish
bot_thread = start_bot_process()

st.success("✅ Bot serverda muvaffaqiyatli ishga tushdi.")

# Statistika bo'limi
if os.path.exists(Config.USERS_DB):
    with open(Config.USERS_DB, "r") as f:
        data = json.load(f)
    
    col1, col2 = st.columns(2)
    col1.metric("Foydalanuvchilar", len(data))
    col2.info("Server: Online")
    
    st.write("### Oxirgi foydalanuvchilar")
    st.dataframe(data[-10:]) # Oxirgi 10 tasini ko'rsatish

if st.button("Serverni yangilash (Rerun)"):
    st.rerun()
