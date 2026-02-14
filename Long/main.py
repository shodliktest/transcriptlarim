import asyncio
import os
import json
import threading
import requests
import io
from bs4 import BeautifulSoup
from gtts import gTTS
from PIL import Image
import streamlit as st

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. KONFIGURATSIYA ---
st.set_page_config(page_title="Longman AI Pro Max", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ BOT_TOKEN topilmadi! Secrets'ga qo'shing.")
        st.stop()
    HISTORY_DB = "user_history.json"

TEMP_CACHE = {}

# --- 2. MULTIMEDIA ISHLOV BERISH ---

def crop_image_to_square(image_content):
    """Rasmni markazdan kvadrat qilib qirqish"""
    try:
        img = Image.open(io.BytesIO(image_content))
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) / 2
        top = (height - min_dim) / 2
        right = (width + min_dim) / 2
        bottom = (height + min_dim) / 2
        img = img.crop((left, top, right, bottom))
        
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95)
        return output.getvalue()
    except: return image_content

def save_to_history(user_id, word):
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

# --- 3. MUKAMMAL SKRAPER ---
def scrape_longman_ultimate(word):
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
            
            # Media: Audio va Rasm
            img_tag = entry.find('img', class_='thumb')
            img_url = img_tag['src'] if img_tag else None
            if img_url and not img_url.startswith('http'):
                img_url = f"https://www.ldoceonline.com{img_url}"
            
            audio_tags = entry.find_all('span', attrs={'data-src-mp3': True})
            audio = None
            for a in audio_tags:
                if 'bre' in a['data-src-mp3']: # British English priority
                    audio = a['data-src-mp3']
                    break
            if not audio and audio_tags: audio = audio_tags[0]['data-src-mp3']

            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""

            if pos not in merged:
                merged[pos] = {"word": hwd, "pron": pron, "img": img_url, "audio": audio, "senses": []}

            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            for b in blocks:
                definition = b.find('span', class_='DEF')
                if not definition: continue
                merged[pos]["senses"].append({
                    "sign": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lex": b.find('span', class_='LEXUNIT').text.strip() if b.find('span', class_='LEXUNIT') else "",
                    "def": definition.text.strip(),
                    "exs": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                })
        return merged
    except: return None

# --- 4. FORMATLASH (BOLD + COPYABLE) ---
def format_pro(pos, data):
    res = f"📕 <b>{data['word'].upper()}</b> [{pos}]\n"
    if data['pron']: res += f"🗣 /{data['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    for i, s in enumerate(data['senses'], 1):
        sign = f"<u>{s['sign']}</u> " if s['sign'] else ""
        lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
        # ASOSIY MATN: Qalin va Nusxalanadigan
        res += f"<b>{i}.</b> {sign}{lex}<b><code>{s['def']}</code></b>\n"
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
        await m.answer(f"Xush kelibsiz, {m.from_user.first_name}! Inglizcha so'z yuboring:", 
                       reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "📜 Tarix")
    async def show_history(m: types.Message):
        if not os.path.exists(Config.HISTORY_DB): return await m.answer("Tarix bo'sh.")
        with open(Config.HISTORY_DB, "r") as f: data = json.load(f)
        u_hist = data.get(str(m.from_user.id), [])
        if not u_hist: return await m.answer("Tarix bo'sh.")
        kb = InlineKeyboardBuilder()
        for w in u_hist: kb.button(text=w, callback_data=f"h_{w}")
        kb.adjust(2)
        await m.answer("Oxirgi qidiruvlaringiz:", reply_markup=kb.as_markup())

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        save_to_history(m.from_user.id, word)
        
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultimate, word)
        await wait.delete()

        if not data: return await m.answer("❌ Topilmadi.")
        TEMP_CACHE[m.chat.id] = data

        kb = InlineKeyboardBuilder()
        for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> bo'limini tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")

        if choice != "all":
            content = data[choice]
            # 1. KVADRAT RASM
            if content['img']:
                try:
                    img_res = requests.get(content['img'])
                    sq_img = crop_image_to_square(img_res.content)
                    await call.message.answer_photo(types.BufferedInputFile(sq_img, filename="thumb.jpg"))
                except: pass
            
            # 2. AUDIO
            if content['audio']:
                try: await call.message.answer_audio(content['audio'], title=f"{content['word']} ({choice})")
                except: pass
            else:
                tts = gTTS(text=content['word'], lang='en')
                buf = io.BytesIO(); tts.write_to_fp(buf); buf.seek(0)
                await call.message.answer_voice(types.BufferedInputFile(buf.read(), filename="pron.mp3"))

            await call.message.answer(format_pro(choice, content))
        else:
            for p, c in data.items(): await call.message.answer(format_pro(p, c))
        await call.answer()

    @dp.callback_query(F.data.startswith("h_"))
    async def hist_search(call: types.CallbackQuery):
        word = call.data.replace("h_", "")
        # Bu yerda handle_word mantiqi qayta ishlatiladi
        await call.answer(f"Qidirilmoqda: {word}")
        data = await asyncio.to_thread(scrape_longman_ultimate, word)
        if data:
            TEMP_CACHE[call.message.chat.id] = data
            kb = InlineKeyboardBuilder()
            for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
            await call.message.answer(f"📦 {word.upper()}:", reply_markup=kb.as_markup())

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

st.title("📕 Longman AI Pro Max")
start_bot()
st.success("Bot Online! Kvadrat rasm, Audio va Nusxalash rejimi faol.")
        
