import asyncio
import os
import json
import threading
import requests
from bs4 import BeautifulSoup
from gtts import gTTS
import io

import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. KONFIGURATSIYA ---
st.set_page_config(page_title="Longman AI Pro", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ Secrets bo'limida BOT_TOKEN topilmadi!")
        st.stop()
    PIXABAY_KEY = st.secrets.get("PIXABAY_KEY", "")
    HISTORY_DB = "history_db.json"

TEMP_CACHE = {}

# --- 2. MULTIMEDIA VA TARIX LOGIKASI ---

def save_history(user_id, word):
    db = Config.HISTORY_DB
    data = {}
    if os.path.exists(db):
        with open(db, "r") as f:
            try: data = json.load(f)
            except: data = {}
    uid = str(user_id)
    if uid not in data: data[uid] = []
    if word in data[uid]: data[uid].remove(word)
    data[uid].insert(0, word)
    data[uid] = data[uid][:10]
    with open(db, "w") as f: json.dump(data, f, indent=4)

def get_pixabay_img(query):
    if not Config.PIXABAY_KEY: return None
    try:
        url = f"https://pixabay.com/api/?key={Config.PIXABAY_KEY}&q={query}&image_type=photo"
        res = requests.get(url, timeout=5).json()
        if res.get('hits'): return res['hits'][0]['largeImageURL']
    except: return None
    return None

# --- 3. MERGED MULTIMEDIA SCRAPER ---
def scrape_longman_full(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip().replace(' ', '-')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        merged = {}
        for entry in entries:
            pos = entry.find('span', class_='POS').text.strip().upper() if entry.find('span', class_='POS') else "WORD"
            if "PhrVbEntry" in entry.get('class', []): pos = "PHRASAL VERB"
            
            # Audio va Rasm linklari
            img_tag = entry.find('img', class_='thumb')
            img = f"https://www.ldoceonline.com{img_tag['src']}" if img_tag else None
            
            audios = entry.find_all('span', attrs={'data-src-mp3': True})
            audio_url = audios[0]['data-src-mp3'] if audios else None

            if pos not in merged:
                merged[pos] = {
                    "word": entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word,
                    "pron": entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else "",
                    "img": img, "audio": audio_url, "senses": []
                }

            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            for b in blocks:
                definition = b.find('span', class_='DEF')
                if not definition: continue
                merged[pos]["senses"].append({
                    "signpost": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lex": b.find('span', class_='LEXUNIT').text.strip() if b.find('span', class_='LEXUNIT') else "",
                    "def": definition.text.strip(),
                    "exs": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                })
        return merged
    except: return None

# --- 4. FORMATLASH (CLICK-TO-COPY) ---
def format_message(pos, data):
    # Sarlavha nusxalanmaydi, ta'rif <code> ichida nusxalanadi
    res = f"📕 <b>{data['word'].upper()}</b> [{pos}]\n"
    if data['pron']: res += f"🗣 /{data['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    for i, s in enumerate(data['senses'], 1):
        sign = f"<u>{s['signpost']}</u> " if s['signpost'] else ""
        lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
        # FAQAT TA'RIF NUSXALANADI
        res += f"<b>{i}.</b> {sign}{lex}<code>{s['def']}</code>\n"
        for ex in s['exs']:
            res += f"  • <i>{ex}</i>\n"
        res += "\n"
    return res

# --- 5. BOT HANDLERLARI ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        await m.answer(f"Salom {m.from_user.first_name}! So'z yuboring:", reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "📜 Tarix")
    async def show_history(m: types.Message):
        db = Config.HISTORY_DB
        if not os.path.exists(db): return await m.answer("Tarix bo'sh.")
        with open(db, "r") as f: data = json.load(f)
        u_history = data.get(str(m.from_user.id), [])
        if not u_history: return await m.answer("Tarix bo'sh.")
        
        kb = InlineKeyboardBuilder()
        for word in u_history: kb.button(text=word, callback_data=f"h_{word}")
        kb.adjust(2)
        await m.answer("Oxirgi qidiruvlaringiz:", reply_markup=kb.as_markup())

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        save_history(m.from_user.id, word)
        
        wait = await m.answer("🔍 Multimedia qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_full, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")
        TEMP_CACHE[m.chat.id] = data

        kb = InlineKeyboardBuilder()
        for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")

        if choice != "all":
            content = data[choice]
            # 1. Rasm yuborish
            img = content['img'] or get_pixabay_img(content['word'])
            if img:
                try: await call.message.answer_photo(img)
                except: pass
            
            # 2. Audio yuborish
            if content['audio']:
                try: await call.message.answer_voice(content['audio'])
                except: pass
            else:
                # TTS
                tts = gTTS(text=content['word'], lang='en')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                await call.message.answer_voice(types.BufferedInputFile(buf.read(), filename="pron.mp3"))

            await call.message.answer(format_message(choice, content))
        else:
            # All rejimi
            for pos, content in data.items():
                await call.message.answer(format_message(pos, content))
        await call.answer()

    @dp.callback_query(F.data.startswith("h_"))
    async def history_search(call: types.CallbackQuery):
        word = call.data.replace("h_", "")
        await call.message.answer(f"Qidirilmoqda: {word}")
        # handle_word mantiqi bu yerda takrorlanadi
        data = await asyncio.to_thread(scrape_longman_full, word)
        if data:
            TEMP_CACHE[call.message.chat.id] = data
            kb = InlineKeyboardBuilder()
            for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
            kb.adjust(2)
            await call.message.answer(f"📦 {word.upper()}:", reply_markup=kb.as_markup())
        await call.answer()

# --- 6. RUNNER ---
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

st.title("📕 Longman Spectrum Pro")
start_bot()
st.success("Bot Online!")
    
