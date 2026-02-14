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
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. CONFIG ---
class Config:
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

# Vaqtinchalik ma'lumotlarni saqlash (Turkumlarni tanlash uchun)
temp_data = {}

# --- 2. FULL LONGMAN SCRAPER ---
def scrape_longman_full(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        
        if not entries:
            return None

        results = {}

        for entry in entries:
            # Turkum (POS) aniqlash
            pos_tag = entry.find('span', class_='POS')
            pos = pos_tag.text.strip() if pos_tag else "other"
            
            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
            
            # Barcha ma'nolarni (Senses) yig'ish
            senses = entry.find_all('span', class_='Sense')
            sense_list = []
            
            for i, sense in enumerate(senses, 1):
                definition = sense.find('span', class_='DEF')
                if not definition: continue
                
                def_text = definition.text.strip()
                examples = [ex.text.strip() for ex in sense.find_all('span', class_='EXAMPLE')]
                
                sense_info = {
                    "num": i,
                    "def": def_text,
                    "examples": examples[:3] # Har bir ma'no uchun max 3 ta misol
                }
                sense_list.append(sense_info)
            
            if sense_list:
                results[pos] = {
                    "word": hwd,
                    "pron": pron,
                    "senses": sense_list
                }
        
        return results
    except Exception:
        return None

# --- 3. FORMATTING FUNCTION ---
def format_entry(pos, data):
    res = f"📕 <b>{data['word'].upper()}</b> ({pos})\n"
    if data['pron']: res += f"🗣 [/{data['pron']}/]\n"
    res += "─" * 15 + "\n"
    
    for s in data['senses']:
        res += f"<b>{s['num']}.</b> {s['def']}\n"
        for ex in s['examples']:
            res += f"  • <i>{ex}</i>\n"
        res += "\n"
    return res

# --- 4. BOT HANDLERS ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        welcome = (
            f"👋 Salom, <b>{m.from_user.first_name}</b>!\n\n"
            "Men Longman lug'atining eng to'liq versiyasiman. "
            "So'z yuborsangiz, uning barcha turkumlari va ma'nolarini topib beraman."
        )
        await m.answer(welcome)

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        if len(word.split()) > 1:
            await m.answer("⚠️ Iltimos, faqat bitta so'z yuboring.")
            return

        wait = await m.answer("🔍 Longman bazasidan qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_full, word)
        await wait.delete()

        if not data:
            await m.answer("❌ So'z topilmadi.")
            return

        temp_data[m.chat.id] = data # Ma'lumotni saqlab turamiz

        kb = InlineKeyboardBuilder()
        for pos in data.keys():
            kb.button(text=pos.capitalize(), callback_data=f"pos_{pos}")
        
        if len(data) > 1:
            kb.button(text="📚 Hammasi (All)", callback_data="pos_all")
        
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> so'zi uchun quyidagi turkumlar topildi. Qaysi biri kerak?", 
                       reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("pos_"))
    async def process_callback(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        if chat_id not in temp_data:
            await call.answer("Ma'lumot muddati o'tgan. Qayta qidiring.", show_alert=True)
            return

        choice = call.data.replace("pos_", "")
        full_data = temp_data[chat_id]
        
        final_text = ""
        if choice == "all":
            for pos, content in full_data.items():
                final_text += format_entry(pos, content) + "\n" + "═" * 10 + "\n"
        else:
            final_text = format_entry(choice, full_data[choice])

        # Telegram xabar chegarasi 4096 belgi
        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                await call.message.answer(final_text[i:i+4000])
        else:
            await call.message.answer(final_text)
        
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

# --- 6. STREAMLIT ---
st.set_page_config(page_title="Longman Full", page_icon="📕")
st.title("📕 Longman Full Dictionary Bot")
start_bot()
st.success("Bot faol! Telegramda so'z yuboring.")
    
