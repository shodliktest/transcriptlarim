import asyncio
import os
import json
import threading
import requests
from bs4 import BeautifulSoup
from gtts import gTTS
import io
from PIL import Image

import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. KONFIGURATSIYA ---
class Config:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    PIXABAY_KEY = st.secrets.get("PIXABAY_KEY", "")
    HISTORY_DB = "history_db.json"

# --- 2. RASMNI KVADRAT QILISH (CROP TO SQUARE) ---
def process_image_to_square(image_content):
    try:
        img = Image.open(io.BytesIO(image_content))
        width, height = img.size
        new_side = min(width, height)
        
        left = (width - new_side) / 2
        top = (height - new_side) / 2
        right = (width + new_side) / 2
        bottom = (height + new_side) / 2
        
        img = img.crop((left, top, right, bottom))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()
    except: return image_content

# --- 3. MERGED SCRAPER (MULTIMEDIA BILAN) ---
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
            
            # Media qidirish
            img_tag = entry.find('img', class_='thumb')
            img_url = f"https://www.ldoceonline.com{img_tag['src']}" if img_tag else None
            
            audio_tag = entry.find('span', attrs={'data-src-mp3': True})
            audio_url = audio_tag['data-src-mp3'] if audio_tag else None

            if pos not in merged:
                merged[pos] = {
                    "word": entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word,
                    "pron": entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else "",
                    "img": img_url, "audio": audio_url, "entries": []
                }

            senses = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            for s in senses:
                definition = s.find('span', class_='DEF')
                if not definition: continue
                merged[pos]["entries"].append({
                    "def": definition.text.strip(),
                    "exs": [ex.text.strip() for ex in s.find_all('span', class_='EXAMPLE')]
                })
        return merged
    except: return None

# --- 4. FORMATLASH ---
def format_message(pos, data):
    res = f"📕 <b>{data['word'].upper()}</b> [{pos}]\n"
    if data['pron']: res += f"🗣 /{data['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    for i, s in enumerate(data['entries'], 1):
        res += f"<b>{i}.</b> <code>{s['def']}</code>\n"
        for ex in s['exs']: res += f"  • <i>{ex}</i>\n"
        res += "\n"
    return res

# --- 5. BOT HANDLERLARI ---
def register_handlers(dp: Dispatcher):
    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_full, word)
        await wait.delete()

        if not data: return await m.answer("❌ Topilmadi.")

        for pos, content in data.items():
            # 1. Rasm yuborish (Kvadrat shaklida)
            img_src = content['img'] or (f"https://pixabay.com/api/?key={Config.PIXABAY_KEY}&q={word}" if Config.PIXABAY_KEY else None)
            if img_src:
                try:
                    r = requests.get(img_src)
                    sq_img = process_image_to_square(r.content)
                    await m.answer_photo(types.BufferedInputFile(sq_img, filename="img.jpg"))
                except: pass
            
            # 2. Audio yuborish
            if content['audio']:
                try: await m.answer_voice(content['audio'])
                except: pass
            else:
                tts = gTTS(text=word, lang='en')
                buf = io.BytesIO(); tts.write_to_fp(buf); buf.seek(0)
                await m.answer_voice(types.BufferedInputFile(buf.read(), filename="tts.mp3"))

            await m.answer(format_message(pos, content))

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

st.title("📕 Longman Spectrum Pro Max")
start_bot()
st.success("Bot Online! Kvadrat rasm va audio funksiyasi qo'shildi.")
            
