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

# --- 1. CONFIG ---
class Config:
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

TEMP_CACHE = {}

# --- 2. PROFESSIONAL LONGMAN SCRAPER ---
def scrape_longman_pro(word):
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
            
            senses_data = []
            senses = entry.find_all('span', class_='Sense')
            
            for i, sense in enumerate(senses, 1):
                # 1. SIGNPOST (Ko'k sarlavha: drink/leaves)
                signpost = sense.find('span', class_='SIGNPOST')
                sign_text = signpost.text.strip().upper() if signpost else ""

                # 2. LEXUNIT (Qalin ibora: mint/camomile etc tea)
                lexunit = sense.find('span', class_='LEXUNIT')
                lex_text = lexunit.text.strip() if lexunit else ""

                # 3. GEO/REGISTER (British English)
                geo = sense.find('span', class_='GEO')
                geo_text = geo.text.strip() if geo else ""

                sub_senses = []
                # 4. SUBSENSES (a, b, c bandlar)
                subs = sense.find_all('span', class_='Subsense')
                
                if subs:
                    for sub_idx, sub in enumerate(subs):
                        gram = sub.find('span', class_='GRAM')
                        gram_text = gram.text.strip() if gram else ""
                        
                        definition = sub.find('span', class_='DEF')
                        def_text = definition.text.strip() if definition else ""
                        
                        examples = [ex.text.strip() for ex in sub.find_all('span', class_='EXAMPLE')]
                        
                        sub_senses.append({
                            "letter": chr(97 + sub_idx), # a, b, c...
                            "gram": gram_text,
                            "def": def_text,
                            "examples": examples
                        })
                else:
                    # Agar kichik bandlar bo'lmasa, asosiy ma'noni olamiz
                    gram = sense.find('span', class_='GRAM')
                    gram_text = gram.text.strip() if gram else ""
                    definition = sense.find('span', class_='DEF')
                    def_text = definition.text.strip() if definition else ""
                    examples = [ex.text.strip() for ex in sense.find_all('span', class_='EXAMPLE')]
                    
                    sub_senses.append({
                        "letter": "", 
                        "gram": gram_text,
                        "def": def_text,
                        "examples": examples
                    })

                senses_data.append({
                    "id": i,
                    "signpost": sign_text,
                    "lexunit": lex_text,
                    "geo": geo_text,
                    "subs": sub_senses
                })

            all_data[pos_key] = {
                "word": hwd,
                "pos": pos_text.upper(),
                "pron": pron,
                "data": senses_data
            }
        return all_data
    except: return None

# --- 3. FORMATLASH (RASMDAGIDEK) ---
def format_pro_output(data):
    text = f"📕 <b>{data['word'].upper()}</b> /{data['pron']}/ <i>{data['pos'].lower()}</i>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    for s in data['data']:
        # Ma'no raqami va Sarlavha
        header = f"<b>{s['id']}</b> "
        if s['signpost']: header += f"<u>{s['signpost']}</u> "
        if s['lexunit']: header += f"<b>{s['lexunit']}</b> "
        if s['geo']: header += f"<i>{s['geo']}</i>"
        text += header + "\n"

        for sub in s['subs']:
            prefix = f"  <b>{sub['letter']})</b> " if sub['letter'] else "  "
            gram = f"<code>{sub['gram']}</code> " if sub['gram'] else ""
            text += f"{prefix}{gram}{sub['def']}\n"
            
            for ex in sub['examples']:
                text += f"    • <i>{ex}</i>\n"
        text += "\n"
    return text

# --- 4. BOT RUNNER VA HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom {m.from_user.first_name}!\nInglizcha so'z yuboring, barcha ma'no va bandlarni (a, b, c) Longmandan to'liq olib beraman.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_pro, word)
        await wait.delete()

        if not data:
            await m.answer("❌ So'z topilmadi.")
            return

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            kb.button(text=content['pos'], callback_data=f"v_{pk}")
        if len(data) > 1: kb.button(text="📚 Hammasi", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(chat_id)
        if not data: return await call.answer("Qayta qidiring.")

        res_text = ""
        if choice == "all":
            for pk in data: res_text += format_pro_output(data[pk]) + "═" * 15 + "\n"
        else:
            res_text = format_pro_output(data[choice])

        if len(res_text) > 4000:
            for i in range(0, len(res_text), 4000): await call.message.answer(res_text[i:i+4000])
        else: await call.message.answer(res_text)
        await call.answer()

@st.cache_resource
def start_bot():
    def _run():
        async def main():
            bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            register_handlers(dp)
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    threading.Thread(target=_run, daemon=True).start()

st.title("📕 Longman Pro Scraper")
start_bot()
st.success("Bot Online! Rasmdagi kabi barcha bandlarni chiqaradi.")
