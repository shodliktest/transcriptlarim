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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. KONFIGURATSIYA ---
class Config:
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

# DIQQAT: st.session_state o'rniga oddiy global lug'at ishlatamiz
# Bu Thread-safe (oqimlar uchun xavfsiz) xotira vazifasini bajaradi
TEMP_CACHE = {}

def get_now():
    return datetime.now(Config.TZ).strftime('%Y.%m.%d %H:%M:%S')

# --- 2. MUKAMMAL LONGMAN SCRAPER (TO'LIQ MA'NOLAR) ---
def scrape_longman_ultra(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        all_data = {}
        for entry_idx, entry in enumerate(entries):
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "word"
            pos_key = f"{pos_text}_{entry_idx}"

            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
            
            senses = entry.find_all('span', class_='Sense')
            sense_list = []
            
            for i, sense in enumerate(senses, 1):
                definition = sense.find('span', class_='DEF')
                if not definition: continue
                
                # Barcha misollarni yig'ish (Hech birini qoldirmay)
                examples = [ex.text.strip() for ex in sense.find_all('span', class_='EXAMPLE') if ex.text.strip()]
                
                sense_list.append({
                    "id": i,
                    "def": definition.text.strip(),
                    "examples": list(dict.fromkeys(examples)) 
                })
            
            if sense_list:
                all_data[pos_key] = {
                    "word": hwd,
                    "pos_display": pos_text.upper(),
                    "pron": pron,
                    "senses": sense_list
                }
        return all_data
    except: return None

# --- 3. FORMATLASH ---
def format_full_data(data):
    text = f"📕 <b>{data['word'].upper()}</b> [{data['pos_display']}]\n"
    if data['pron']: text += f"🗣 <code>/{data['pron']}/</code>\n"
    text += "━" * 15 + "\n"
    
    for s in data['senses']:
        text += f"<b>{s['id']}.</b> {s['def']}\n"
        if s['examples']:
            for ex in s['examples']:
                text += f"  • <i>{ex}</i>\n"
        text += "\n"
    return text

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom, {m.from_user.first_name}!\nInglizcha so'z yuboring, barcha ma'no va misollarni Longmandan olib beraman.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        wait = await m.answer(f"🔍 <b>{word}</b> qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultra, word)
        await wait.delete()

        if not data:
            await m.answer("❌ So'z topilmadi.")
            return

        # MUHIM: st.session_state o'rniga TEMP_CACHE lug'atiga saqlaymiz
        TEMP_CACHE[m.chat.id] = data
        
        kb = InlineKeyboardBuilder()
        for pos_key, content in data.items():
            kb.button(text=content['pos_display'], callback_data=f"p_{pos_key}")
        
        if len(data) > 1:
            kb.button(text="📚 Hammasi (Full)", callback_data="p_all")
        
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("p_"))
    async def process_pos(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("p_", "")
        data = TEMP_CACHE.get(chat_id)
        
        if not data:
            await call.answer("Qayta qidiring.", show_alert=True)
            return

        response = ""
        if choice == "all":
            for pk in data:
                response += format_full_data(data[pk]) + "═" * 15 + "\n"
        else:
            response = format_full_data(data[choice])

        # Xabarni bo'laklash (Telegram limiti 4096)
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await call.message.answer(response[i:i+4000])
        else:
            await call.message.answer(response)
        await call.answer()

# --- 5. RUNNER ---
@st.cache_resource
def start_bot():
    def _run():
        async def main():
            bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            register_handlers(dp)
            await bot.delete_webhook(drop_pending_updates=True)
            try:
                await dp.start_polling(bot, handle_signals=False)
            finally:
                await bot.session.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

# --- 6. STREAMLIT UI ---
st.set_page_config(page_title="Longman Ultra", layout="centered")
st.title("📕 Longman Ultra Scraper")
start_bot()
st.success("Bot Online! Telegramda so'z yuborib ko'ring.")
