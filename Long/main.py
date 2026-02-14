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
    ADMIN_ID = 1416457518
    USERS_DB = "user_database.json"
    TZ = pytz.timezone('Asia/Tashkent')
    # Bot tokenini Streamlit Secrets'dan olish
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

# Thread-safe global kesh (st.session_state o'rniga)
TEMP_CACHE = {}

def get_now():
    return datetime.now(Config.TZ).strftime('%Y.%m.%d %H:%M:%S')

# --- 2. DATABASE LOGIC ---
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

# --- 3. ULTIMATE LONGMAN SCRAPER ---
def scrape_longman_ultimate(word):
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
            # Asosiy sarlavha, POS va Pronunciation
            hwd_tag = entry.find('span', class_='HWD')
            hwd = hwd_tag.text if hwd_tag else word
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "word"
            pron_tag = entry.find('span', class_='PRON')
            pron = pron_tag.text if pron_tag else ""
            
            senses_data = []
            # Barcha bloklarni (Sense, PhrVbEntry, ColloEx) qidiramiz
            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry', 'ColloEx', 'GramEx'])
            
            valid_counter = 1
            for b in blocks:
                # Blokda ma'no (DEF), ibora (LEXUNIT) yoki Phrasal Verb sarlavhasi (Head) bormi?
                definition = b.find('span', class_='DEF')
                lexunit = b.find('span', class_='LEXUNIT')
                head = b.find('span', class_='Head')
                
                # Agar blok bo'sh bo'lsa, tashlab ketamiz
                if not definition and not lexunit and not head:
                    continue

                signpost = b.find('span', class_='SIGNPOST')
                geo = b.find('span', class_='GEO')
                
                sub_senses = []
                # a, b, c kabi Subsense'larni qidirish
                subs = b.find_all('span', class_='Subsense')
                
                if subs:
                    for sub_idx, sub in enumerate(subs):
                        sub_def_tag = sub.find('span', class_='DEF')
                        if not sub_def_tag: continue
                        
                        sub_gram = sub.find('span', class_='GRAM')
                        sub_examples = [ex.text.strip() for ex in sub.find_all('span', class_='EXAMPLE') if ex.text.strip()]
                        
                        sub_senses.append({
                            "letter": chr(97 + sub_idx),
                            "gram": sub_gram.text.strip() if sub_gram else "",
                            "def": sub_def_tag.text.strip(),
                            "examples": sub_examples
                        })
                else:
                    # Kichik bandlar bo'lmasa, asosiy blokni olamiz
                    gram_tag = b.find('span', class_='GRAM')
                    main_examples = [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE') if ex.text.strip()]
                    
                    sub_senses.append({
                        "letter": "",
                        "gram": gram_tag.text.strip() if gram_tag else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": main_examples
                    })

                senses_data.append({
                    "id": valid_counter,
                    "signpost": signpost.text.strip().upper() if signpost else "",
                    "lexunit": lexunit.text.strip() if lexunit else (head.text.strip() if head else ""),
                    "geo": geo.text.strip() if geo else "",
                    "subs": sub_senses
                })
                valid_counter += 1

            if senses_data:
                pos_key = f"{pos_text}_{entry_idx}"
                all_data[pos_key] = {
                    "word": hwd,
                    "pos_display": pos_text.upper(),
                    "pron": pron,
                    "data": senses_data
                }
        return all_data
    except Exception as e:
        print(f"Scrape Error: {e}")
        return None

# --- 4. FORMATLASH ---
def format_pro_output(data):
    # Sarlavha: WORD /pron/ pos
    text = f"📕 <b>{data['word'].upper()}</b> /{data['pron']}/ <i>{data['pos_display'].lower()}</i>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    for s in data['data']:
        # Ma'no raqami, Signpost, Lexunit va Geo
        header = f"<b>{s['id']}</b> "
        if s['signpost']: header += f"<u>{s['signpost']}</u> "
        if s['lexunit']: header += f"<b>{s['lexunit']}</b> "
        if s['geo']: header += f"<i>{s['geo']}</i>"
        text += header.strip() + "\n"

        for sub in s['subs']:
            prefix = f"  <b>{sub['letter']})</b> " if sub['letter'] else "  "
            gram = f"<code>[{sub['gram']}]</code> " if sub['gram'] else ""
            text += f"{prefix}{gram}{sub['def']}\n"
            
            # Barcha misollar
            for ex in sub['examples']:
                text += f"    • <i>{ex}</i>\n"
        text += "\n"
    return text

# --- 5. BOT HANDLERLARI ---
def register_all_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        log_user(m.from_user)
        welcome = (
            f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
            "🤖 Men <b>Longman Ultimate Pro</b> botiman.\n"
            "Menga inglizcha so'z yuboring, barcha ma'no va misollarni to'liq chiqarib beraman.\n\n"
            "✍️ Boshlash uchun so'z yuboring:"
        )
        kb = ReplyKeyboardBuilder()
        kb.button(text="🔍 Lug'atdan qidirish")
        await m.answer(welcome, reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "🔍 Lug'atdan qidirish")
    async def btn_lookup(m: types.Message):
        await m.answer("📝 Iltimos, qidirilayotgan so'zni yuboring:")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        if len(word.split()) > 1:
            await m.answer("⚠️ Iltimos, faqat bitta so'z yuboring.")
            return

        wait = await m.answer(f"🔍 <b>{word}</b> tahlil qilinmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultimate, word)
        await wait.delete()

        if not data:
            await m.answer("❌ Kechirasiz, so'z topilmadi.")
            return

        # Cache'ga saqlash
        TEMP_CACHE[m.chat.id] = data
        
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            kb.button(text=content['pos_display'], callback_data=f"v_{pk}")
        
        if len(data) > 1:
            kb.button(text="📚 Hammasi (All)", callback_data="v_all")
        
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun ma'nolar topildi:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(chat_id)
        
        if not data:
            await call.answer("Qayta qidiring.", show_alert=True)
            return

        response = ""
        if choice == "all":
            for pk in data:
                response += format_pro_output(data[pk]) + "═" * 15 + "\n"
        else:
            response = format_pro_output(data[choice])

        # Telegram limiti 4096 belgidan oshsa bo'lish
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await call.message.answer(response[i:i+4000])
        else:
            await call.message.answer(response)
        await call.answer()

# --- 6. RUNNER (THREAD SAFE) ---
@st.cache_resource
def start_bot():
    def _run():
        async def main():
            bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            register_all_handlers(dp)
            # ConflictError oldini olish
            await bot.delete_webhook(drop_pending_updates=True)
            try:
                # handle_signals=False Streamlit thread uchun shart
                await dp.start_polling(bot, handle_signals=False)
            finally:
                await bot.session.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

# --- 7. STREAMLIT UI ---
st.set_page_config(page_title="Longman Ultimate Server", layout="wide")
st.title("📕 Longman Ultimate Pro Bot")

# Botni fonda ishga tushirish
start_bot()

st.success("✅ Bot holati: Online")

# Statistikani ko'rsatish
if os.path.exists(Config.USERS_DB):
    with open(Config.USERS_DB, "r") as f:
        users_list = json.load(f)
    st.metric("Foydalanuvchilar soni", len(users_list))
    st.write("Oxirgi qo'shilganlar:")
    st.table(users_list[-5:])

if st.button("🔄 Serverni yangilash"):
    st.cache_resource.clear()
    st.rerun()
