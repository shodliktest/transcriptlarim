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
    # Telegram bot tokenni Streamlit secrets'dan oladi
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    TZ = pytz.timezone('Asia/Tashkent')

# Threading ichida st.session_state ishlamagani uchun global lug'atdan foydalanamiz
TEMP_CACHE = {}

# --- 2. PROFESSIONAL LONGMAN SCRAPER (FILTRLANGAN VA TO'LIQ) ---
def scrape_longman_ultra_pro(word):
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
            # Turkum (POS) aniqlash
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "word"
            pos_key = f"{pos_text}_{entry_idx}"

            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
            
            senses_data = []
            senses = entry.find_all('span', class_='Sense')
            
            # Bo'sh joylar va xato raqamlashni oldini olish uchun filtr
            valid_sense_counter = 1
            
            for sense in senses:
                # 1. Tekshiruv: Ichida ma'no (DEF) yoki ibora (LEXUNIT) bormi?
                definition = sense.find('span', class_='DEF')
                lexunit = sense.find('span', class_='LEXUNIT')
                
                # Agar blok bo'sh bo'lsa, uni tashlab ketamiz
                if not definition and not lexunit:
                    continue

                signpost = sense.find('span', class_='SIGNPOST')
                sign_text = signpost.text.strip().upper() if signpost else ""
                lex_text = lexunit.text.strip() if lexunit else ""
                geo = sense.find('span', class_='GEO')
                geo_text = geo.text.strip() if geo else ""

                sub_senses = []
                subs = sense.find_all('span', class_='Subsense')
                
                if subs:
                    # a, b, c kabi kichik bandlarni yig'ish
                    for sub_idx, sub in enumerate(subs):
                        sub_def_tag = sub.find('span', class_='DEF')
                        if not sub_def_tag: continue
                        
                        gram = sub.find('span', class_='GRAM')
                        sub_examples = [ex.text.strip() for ex in sub.find_all('span', class_='EXAMPLE') if ex.text.strip()]
                        
                        sub_senses.append({
                            "letter": chr(97 + sub_idx),
                            "gram": gram.text.strip() if gram else "",
                            "def": sub_def_tag.text.strip(),
                            "examples": sub_examples
                        })
                else:
                    # Agar kichik bandlar bo'lmasa, asosiy ma'no bloki
                    gram = sense.find('span', class_='GRAM')
                    sub_examples = [ex.text.strip() for ex in sense.find_all('span', class_='EXAMPLE') if ex.text.strip()]
                    
                    sub_senses.append({
                        "letter": "", 
                        "gram": gram.text.strip() if gram else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": sub_examples
                    })

                senses_data.append({
                    "id": valid_sense_counter,
                    "signpost": sign_text,
                    "lexunit": lex_text,
                    "geo": geo_text,
                    "subs": sub_senses
                })
                valid_sense_counter += 1

            if senses_data:
                all_data[pos_key] = {
                    "word": hwd,
                    "pos": pos_text.upper(),
                    "pron": pron,
                    "data": senses_data
                }
        return all_data
    except Exception:
        return None

# --- 3. FORMATLASH (RASMDAGIDEK STRUKTURA) ---
def format_word_pro(data):
    # Sarlavha: WORD /pron/ pos
    text = f"📕 <b>{data['word'].upper()}</b> /{data['pron']}/ <i>{data['pos'].lower()}</i>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    for s in data['data']:
        # Asosiy ma'no sarlavhasi (1 SIGNPOST LEXUNIT GEO)
        header = f"<b>{s['id']}</b> "
        if s['signpost']: header += f"<u>{s['signpost']}</u> "
        if s['lexunit']: header += f"<b>{s['lexunit']}</b> "
        if s['geo']: header += f"<i>{s['geo']}</i>"
        text += header.strip() + "\n"

        for sub in s['subs']:
            prefix = f"  <b>{sub['letter']})</b> " if sub['letter'] else "  "
            gram = f"<code>{sub['gram']}</code> " if sub['gram'] else ""
            text += f"{prefix}{gram}{sub['def']}\n"
            
            # Barcha misollar
            for ex in sub['examples']:
                text += f"    • <i>{ex}</i>\n"
        text += "\n"
    return text

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom, {m.from_user.first_name}!\n\nMen <b>Longman Full Pro</b> botiman. Menga inglizcha so'z yuboring, barcha ma'no va bandlarni (a, b, c) rasmiy lug'atdagidek to'liq olib beraman.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        if len(word.split()) > 1:
            await m.answer("⚠️ Iltimos, faqat bitta so'z yuboring.")
            return

        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_ultra_pro, word)
        await wait.delete()

        if not data:
            await m.answer("❌ Kechirasiz, so'z topilmadi.")
            return

        # Cache'ga saqlash (Callback uchun)
        TEMP_CACHE[m.chat.id] = data
        
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            kb.button(text=content['pos'], callback_data=f"v_{pk}")
        
        if len(data) > 1:
            kb.button(text="📚 Hammasi (All)", callback_data="v_all")
        
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

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
                response += format_word_pro(data[pk]) + "═" * 15 + "\n"
        else:
            response = format_word_pro(data[choice])

        # Telegram xabar chegarasini boshqarish
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await call.message.answer(response[i:i+4000])
        else:
            await call.message.answer(response)
        await call.answer()

# --- 5. RUNNER (CONFLICT VA NAMEERRORLARSIZ) ---
@st.cache_resource
def start_bot_process():
    def _run():
        async def main():
            # Bot va Dispatcher aynan shu thread ichida yaratilishi shart
            bot_instance = Bot(
                token=Config.BOT_TOKEN, 
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            dp_instance = Dispatcher()
            register_handlers(dp_instance)
            
            # ConflictError'ni oldini olish
            await bot_instance.delete_webhook(drop_pending_updates=True)
            
            try:
                # handle_signals=False Streamlit threading uchun shart
                await dp_instance.start_polling(bot_instance, handle_signals=False)
            finally:
                await bot_instance.session.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

# --- 6. STREAMLIT UI ---
st.set_page_config(page_title="Longman Pro Server", page_icon="📕")
st.title("📕 Longman Pro Dictionary Bot")

# Botni ishga tushirish
start_bot_process()

st.success("✅ Bot holati: ONLINE")
st.info("Bu server Longman lug'atidagi barcha ma'no va misollarni skaner qiladi.")

if st.button("🔄 Serverni yangilash (Clear Cache)"):
    st.cache_resource.clear()
    st.rerun()
