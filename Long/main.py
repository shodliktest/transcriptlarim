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
        st.error("❌ Secrets'da BOT_TOKEN topilmadi!")
        st.stop()
    # Pixabay API kalitingizni bu yerga kiriting
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

# --- 3. MUKAMMAL MULTIMEDIA SKRAPER ---
def scrape_longman_full(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip().replace(' ', '-')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        merged = {}
        for entry in entries:
            pos_tag = entry.find('span', class_='POS')
            pos = pos_tag.text.strip().upper() if pos_tag else "WORD"
            if "PhrVbEntry" in entry.get('class', []): pos = "PHRASAL VERB"
            
            # 1. Rasm qidirish
            img_tag = entry.find('img', class_='thumb')
            img = None
            if img_tag:
                img = img_tag['src']
                if not img.startswith('http'):
                    img = f"https://www.ldoceonline.com{img}"
            
            # 2. Audio qidirish (UK/US)
            audios = entry.find_all('span', attrs={'data-src-mp3': True})
            audio_url = None
            for a in audios:
                src = a['data-src-mp3']
                if "breProns" in src or "British" in a.get('title', ''):
                    audio_url = src # Britaniya talaffuzi ustun
                    break
            if not audio_url and audios: audio_url = audios[0]['data-src-mp3']

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
                
                # Soddalashtirilgan ta'rif (AI Explain uchun tayyorlov)
                full_def = definition.text.strip()
                short_def = full_def.split(';')[0].split('.')[0] # Birinchi qism
                
                merged[pos]["senses"].append({
                    "signpost": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lex": b.find('span', class_='LEXUNIT').text.strip() if b.find('span', class_='LEXUNIT') else "",
                    "def": full_def,
                    "short": short_def,
                    "exs": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                })
        return merged
    except: return None

# --- 4. FORMATLASH (NUSXALASH VA AI EXPLAIN) ---
def format_message(pos, data, simplified=False):
    res = f"📕 <b>{data['word'].upper()}</b> [{pos}]\n"
    if data['pron']: res += f"🗣 /{data['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    for i, s in enumerate(data['senses'], 1):
        sign = f"<u>{s['signpost']}</u> " if s['signpost'] else ""
        lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
        
        # NUSXALANADIGAN QISM (<code> ichida)
        def_text = s['short'] if simplified else s['def']
        res += f"<b>{i}.</b> {sign}{lex}<code>{def_text}</code>\n"
        
        # Misollar nusxalanmasligi uchun oddiy matnda
        if not simplified:
            for ex in s['exs']:
                res += f"  • <i>{ex}</i>\n"
        res += "\n"
    return res

# --- 5. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        await m.answer(f"Salom {m.from_user.first_name}! So'z yuboring:", reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "📜 Tarix")
    async def show_history(m: types.Message):
        if not os.path.exists(Config.HISTORY_DB): return await m.answer("Tarix bo'sh.")
        with open(Config.HISTORY_DB, "r") as f:
            try: data = json.load(f)
            except: data = {}
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
                tts = gTTS(text=content['word'], lang='en')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                await call.message.answer_voice(types.BufferedInputFile(buf.read(), filename="pron.mp3"))

            # 3. Matn va AI tugmasi
            kb = InlineKeyboardBuilder()
            kb.button(text="🤖 AI Explain (Sodda)", callback_data=f"ai_{choice}")
            await call.message.answer(format_message(choice, content), reply_markup=kb.as_markup())
        else:
            for pos, content in data.items():
                await call.message.answer(format_message(pos, content))
        await call.answer()

    @dp.callback_query(F.data.startswith("ai_"))
    async def process_ai(call: types.CallbackQuery):
        pos = call.data.replace("ai_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if data and pos in data:
            await call.message.answer(f"🤖 <b>AI soddalashtirilgan ma'nosi:</b>\n\n{format_message(pos, data[pos], True)}")
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
                
