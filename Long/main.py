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

# --- 1. KONFIGURATSIYA ---
class Config:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    TZ = pytz.timezone('Asia/Tashkent')
    USERS_DB = "user_database.json"

TEMP_CACHE = {}

def get_now():
    return datetime.now(Config.TZ).strftime('%Y.%m.%d %H:%M:%S')

# --- 2. ULTIMATE SCRAPER (PHRASAL VERBS BILAN) ---
def scrape_longman_ultimate_pro(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        all_data = {}
        phrasal_verbs_list = []

        for entry_idx, entry in enumerate(entries):
            # Asosiy sarlavha
            hwd_tag = entry.find('span', class_='HWD')
            hwd = hwd_tag.text if hwd_tag else word
            
            # Turkum aniqlash
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "word"
            
            # Talaffuz
            pron_tag = entry.find('span', class_='PRON')
            pron = pron_tag.text if pron_tag else ""

            # Senses va Phrasal Verbs ajratish
            senses_data = []
            
            # 1. Oddiy ma'nolar (Sense)
            senses = entry.find_all('span', class_='Sense')
            valid_counter = 1
            for s in senses:
                definition = s.find('span', class_='DEF')
                lexunit = s.find('span', class_='LEXUNIT')
                if not definition and not lexunit: continue

                signpost = s.find('span', class_='SIGNPOST')
                sub_senses = []
                subs = s.find_all('span', class_='Subsense')
                
                if subs:
                    for sub_idx, sub in enumerate(subs):
                        sub_def = sub.find('span', class_='DEF')
                        if not sub_def: continue
                        sub_senses.append({
                            "letter": chr(97 + sub_idx),
                            "gram": sub.find('span', class_='GRAM').text.strip() if sub.find('span', class_='GRAM') else "",
                            "def": sub_def.text.strip(),
                            "examples": [ex.text.strip() for ex in sub.find_all('span', class_='EXAMPLE')]
                        })
                else:
                    sub_senses.append({
                        "letter": "",
                        "gram": s.find('span', class_='GRAM').text.strip() if s.find('span', class_='GRAM') else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": [ex.text.strip() for ex in s.find_all('span', class_='EXAMPLE')]
                    })

                senses_data.append({
                    "id": valid_counter,
                    "signpost": signpost.text.strip().upper() if signpost else "",
                    "lexunit": lexunit.text.strip() if lexunit else "",
                    "subs": sub_senses
                })
                valid_counter += 1

            # 2. Phrasal Verbs qidirish (PhrVbEntry)
            phr_vbs = entry.find_all('span', class_='PhrVbEntry')
            for pv in phr_vbs:
                pv_head = pv.find('span', class_='Head')
                pv_def = pv.find('span', class_='DEF')
                if pv_head and pv_def:
                    pv_examples = [ex.text.strip() for ex in pv.find_all('span', class_='EXAMPLE')]
                    phrasal_verbs_list.append({
                        "head": pv_head.text.strip(),
                        "def": pv_def.text.strip(),
                        "examples": pv_examples
                    })

            if senses_data:
                all_data[f"{pos_text}_{entry_idx}"] = {
                    "word": hwd, "pos": pos_text.upper(), "pron": pron, "data": senses_data
                }

        # Phrasal Verbs'larni alohida kategoriya sifatida qo'shish
        if phrasal_verbs_list:
            all_data["phrasal_verb"] = {
                "word": word, "pos": "PHRASAL VERB", "pron": "", "data_pv": phrasal_verbs_list
            }
            
        return all_data
    except: return None

# --- 3. FORMATLASH ---
def format_output(pos_key, data):
    # SIZ SO'RAGAN FORMAT:
    # 📕 WORD [POS]
    # 🗣 /pron/
    word_head = f"📕 {data['word'].upper()} [{data['pos']}]"
    pron_head = f"🗣 /{data['pron']}/" if data['pron'] else ""
    
    text = f"{word_head}\n{pron_head}\n" if pron_head else f"{word_head}\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    # Agar bu Phrasal Verb bo'lsa
    if pos_key == "phrasal_verb":
        for i, pv in enumerate(data['data_pv'], 1):
            text += f"<b>{i}. {pv['head']}</b>\n"
            text += f"  {pv['def']}\n"
            for ex in pv['examples']:
                text += f"    • <i>{ex}</i>\n"
            text += "\n"
    else:
        # Oddiy turkumlar uchun
        for s in data['data']:
            header = f"<b>{s['id']}</b> "
            if s['signpost']: header += f"<u>{s['signpost']}</u> "
            if s['lexunit']: header += f"<b>{s['lexunit']}</b> "
            text += header.strip() + "\n"
            for sub in s['subs']:
                prefix = f"  <b>{sub['letter']})</b> " if sub['letter'] else "  "
                gram = f"<code>[{sub['gram']}]</code> " if sub['gram'] else ""
                text += f"{prefix}{gram}{sub['def']}\n"
                for ex in sub['examples']:
                    text += f"    • <i>{ex}</i>\n"
            text += "\n"
    return text

# --- 4. BOT HANDLERLARI ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom {m.from_user.first_name}!\n\nInglizcha so'z yuboring, barcha ma'no va <b>Phrasal Verblarni</b> to'liq olib beraman.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer(f"🔍 <b>{word}</b> tahlil qilinmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultimate_pro, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            kb.button(text=content['pos'], callback_data=f"sel_{pk}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="sel_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("sel_"))
    async def process_selection(call: types.CallbackQuery):
        choice = call.data.replace("sel_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")

        res = ""
        if choice == "all":
            for pk in data: res += format_output(pk, data[pk]) + "═" * 15 + "\n"
        else:
            res = format_output(choice, data[choice])

        if len(res) > 4000:
            for i in range(0, len(res), 4000): await call.message.answer(res[i:i+4000])
        else: await call.message.answer(res)
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
            await dp.start_polling(bot, handle_signals=False)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    threading.Thread(target=_run, daemon=True).start()

st.title("📕 Longman Ultimate (Phrasal Verbs Edition)")
start_bot()
st.success("Bot Online! Sarlavha formati yangilandi va Phrasal Verblar qo'shildi.")
    
