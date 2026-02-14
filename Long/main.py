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
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    PIXABAY_KEY = st.secrets.get("PIXABAY_KEY", "") # Pixabay API kaliti
    HISTORY_DB = "history_db.json"

TEMP_CACHE = {}

# --- 2. MULTIMEDIA FUNKSIYALARI ---

def get_pixabay_image(query):
    """Pixabay'dan rasm topish [Image search via API]"""
    if not Config.PIXABAY_KEY: return None
    try:
        url = f"https://pixabay.com/api/?key={Config.PIXABAY_KEY}&q={query}&image_type=photo&per_page=3"
        res = requests.get(url).json()
        if res['hits']:
            return res['hits'][0]['largeImageURL']
    except: return None
    return None

# --- 3. MUKAMMAL SKRAPER (AUDIO VA RASMLAR BILAN) ---
def scrape_longman_multimedia(word):
    try:
        formatted_word = word.lower().strip().replace(' ', '-')
        url = f"https://www.ldoceonline.com/dictionary/{formatted_word}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        merged_data = {}
        for entry in entries:
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().upper() if pos_tag else "WORD"
            
            # Media qidirish (Audio va Rasm)
            # Longmanda audio data-src-mp3 atributida bo'ladi
            uk_audio = entry.find('span', class_='speaker bbcSnd amSnd')
            us_audio = entry.find('span', class_='speaker breSnd amSnd')
            
            # Rasmni topish
            entry_img = entry.find('img', class_='thumb')
            img_url = entry_img['src'] if entry_img else None
            if img_url and not img_url.startswith('http'):
                img_url = f"https://www.ldoceonline.com{img_url}"

            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""

            if pos_text not in merged_data:
                merged_data[pos_text] = {
                    "word": hwd, "pron": pron, "entries": [], 
                    "img": img_url, "audio_uk": None, "audio_us": None
                }

            # Audio linklarini yig'ish
            audio_tags = entry.find_all('span', attrs={'data-src-mp3': True})
            for audio in audio_tags:
                src = audio['data-src-mp3']
                if 'British' in audio.get('title', '') or 'bre' in src:
                    merged_data[pos_text]["audio_uk"] = src
                else:
                    merged_data[pos_text]["audio_us"] = src

            senses = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            senses_data = []
            for b in senses:
                definition = b.find('span', class_='DEF')
                if not definition: continue
                
                sub_list = []
                # Faqat asosiy ma'nolarni sodda formatda yig'ish
                sub_list.append({
                    "def": definition.text.strip(),
                    "examples": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                })

                senses_data.append({
                    "id": len(senses_data) + 1,
                    "signpost": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "subs": sub_list
                })
            
            if senses_data: merged_data[pos_text]["entries"].append(senses_data)
            
        return merged_data
    except: return None

# --- 4. AI EXPLAIN (SIMPLIFIER) ---
def ai_simplify(text):
    """Ma'noni buzmagan holda qisqartirish mantiqi"""
    # Bu yerda AI model chaqirilishi mumkin. Hozircha akademik qisqartirish:
    words = text.split()
    if len(words) > 15:
        return " ".join(words[:12]) + "..." # Soddalashtirilgan versiya placeholder
    return text

# --- 5. FORMATTING ---
def format_pro_style(pos, content):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']: res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    cnt = 1
    for entry_senses in content['entries']:
        for s in entry_senses:
            sign = f"<u>{s['signpost']}</u> " if s['signpost'] else ""
            for sub in s['subs']:
                # NUSXALANADIGAN QISM
                res += f"<b>{cnt}.</b> {sign}<code>{sub['def']}</code>\n"
                for ex in sub['examples']:
                    res += f"   • <i>{ex}</i>\n"
            res += "\n"
            cnt += 1
    return res

# --- 6. HANDLERS ---
def register_handlers(dp: Dispatcher):
    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        wait = await m.answer("🔍 Multimedia qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_multimedia, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        
        # Har bir turkum uchun tugma va media yuborish
        for pos, content in data.items():
            # 1. Rasm yuborish
            img = content['img'] or get_pixabay_image(word)
            if img: await m.answer_photo(img, caption=f"🖼 {word} ({pos})")

            # 2. Audio yuborish (UK/US)
            if content['audio_uk']:
                await m.answer_audio(content['audio_uk'], title=f"{word} (UK)")
            elif content['audio_us']:
                await m.answer_audio(content['audio_us'], title=f"{word} (US)")
            else:
                # ResponsiveVoice o'rniga gTTS (Bot uchun xavfsizroq)
                tts = gTTS(text=word, lang='en')
                audio_file = io.BytesIO()
                tts.write_to_fp(audio_file)
                audio_file.seek(0)
                await m.answer_voice(types.BufferedInputFile(audio_file.read(), filename=f"{word}.mp3"))

            # 3. Ma'lumotlarni yuborish
            kb = InlineKeyboardBuilder()
            kb.button(text="🤖 AI Explain (Short)", callback_data=f"ai_{pos}")
            
            await m.answer(format_pro_style(pos, content), reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("ai_"))
    async def ai_explain_handler(call: types.CallbackQuery):
        pos = call.data.replace("ai_", "")
        chat_id = call.message.chat.id
        data = TEMP_CACHE.get(chat_id)
        
        if not data or pos not in data:
            return await call.answer("Ma'lumot topilmadi.")
        
        # Birinchi ma'noni qisqartirib ko'rsatamiz
        original_def = data[pos]['entries'][0][0]['subs'][0]['def']
        short_def = ai_simplify(original_def)
        
        await call.message.answer(f"🤖 <b>AI Simplification:</b>\n\n<code>{short_def}</code>")
        await call.answer()

# --- 7. RUNNER ---
@st.cache_resource
def start_bot_app():
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

st.title("📕 Longman AI Multimedia Pro")
start_bot_app()
st.success("✅ Bot Online! Rasm, Audio va AI Explain funksiyalari faol.")
