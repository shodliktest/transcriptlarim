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

if 'temp_results' not in st.session_state:
    st.session_state.temp_results = {}

# --- 2. MUKAMMAL LONGMAN SCRAPER (TO'LIQ MA'NOLAR) ---
def scrape_longman_ultra(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        # Barcha dictentry bloklarini olamiz (Noun, Verb, Adj va h.k.)
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        all_data = {}
        for entry_idx, entry in enumerate(entries):
            # 1. Turkum (POS)
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "other"
            
            # Unikal POS yaratish (agar bitta so'zda ikki marta 'noun' blok bo'lsa)
            pos_key = f"{pos_text}_{entry_idx}"

            # 2. So'z va Talaffuz
            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
            
            # 3. Barcha Senses (Ma'nolar)
            senses = entry.find_all('span', class_='Sense')
            sense_list = []
            
            for i, sense in enumerate(senses, 1):
                # Ma'no ta'rifi (DEF)
                definition = sense.find('span', class_='DEF')
                if not definition: continue
                
                # Ushbu ma'noga tegishli BARCHA misollarni yig'ish
                examples_tags = sense.find_all('span', class_='EXAMPLE')
                examples = [ex.text.strip() for ex in examples_tags if ex.text.strip()]
                
                # Ba'zi misollar 'GramEx' yoki 'ColloEx' bloklarida bo'lishi mumkin, ularni ham qo'shamiz
                extra_examples = sense.find_all('span', class_='GramEx')
                for ge in extra_examples:
                    ex_text = ge.find('span', class_='EXAMPLE')
                    if ex_text: examples.append(ex_text.text.strip())

                sense_list.append({
                    "id": i,
                    "def": definition.text.strip(),
                    "examples": list(dict.fromkeys(examples)) # Takrorlanishni o'chirish
                })
            
            if sense_list:
                all_data[pos_key] = {
                    "word": hwd,
                    "pos_display": pos_text.upper(),
                    "pron": pron,
                    "senses": sense_list
                }
        
        return all_data
    except Exception as e:
        print(f"Scrape error: {e}")
        return None

# --- 3. FORMATLASH ---
def format_full_data(pos_key, data):
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
        welcome = (
            f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
            "🤖 Men <b>Longman Full Edition</b> botiman.\n\n"
            "Menga so'z yuborsangiz, men saytdagi <b>barcha ma'nolarni va barcha misollarni</b> to'liq chiqarib beraman.\n\n"
            "✍️ So'z yuboring:"
        )
        await m.answer(welcome)

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        wait = await m.answer(f"🔍 <b>{word}</b> qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultra, word)
        await wait.delete()

        if not data:
            await m.answer("❌ Kechirasiz, Longman lug'atidan barcha ma'nolarni olishda xatolik yuz berdi yoki so'z topilmadi.")
            return

        st.session_state.temp_results[m.chat.id] = data
        
        kb = InlineKeyboardBuilder()
        for pos_key, content in data.items():
            kb.button(text=content['pos_display'], callback_data=f"pos_{pos_key}")
        
        if len(data) > 1:
            kb.button(text="📚 Barcha ma'nolar (Full)", callback_data="pos_all_ultra")
        
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun ma'nolar topildi. Bo'limni tanlang:", 
                       reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("pos_"))
    async def process_pos(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("pos_", "")
        data = st.session_state.temp_results.get(chat_id)
        
        if not data:
            await call.answer("Eski ma'lumot. So'zni qayta yozing.", show_alert=True)
            return

        full_response = ""
        if choice == "all_ultra":
            for pk, content in data.items():
                full_response += format_full_data(pk, content) + "═" * 15 + "\n"
        else:
            full_response = format_full_data(choice, data[choice])

        # Telegram xabar limiti (4096) uchun bo'lish
        if len(full_response) > 4000:
            parts = [full_response[i:i+4000] for i in range(0, len(full_response), 4000)]
            for part in parts:
                await call.message.answer(part)
        else:
            await call.message.answer(full_response)
        await call.answer()

# --- 5. RUNNER (THREAD SAFE) ---
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
st.title("📕 Longman Ultra Scraper Bot")
start_bot()
st.success("✅ Bot barcha ma'nolarni olish rejimida ishlamoqda.")
