import asyncio
import os
import threading
import requests
from bs4 import BeautifulSoup
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. CONFIG (XATOLIKLARNI OLDINI OLISH) ---
st.set_page_config(page_title="Longman AI Dictionary", page_icon="📕")

class Config:
    # Secrets mavjudligini tekshirish (Oq ekran bo'lmasligi uchun)
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except Exception:
        st.error("❌ BOT_TOKEN topilmadi! Streamlit Secrets bo'limiga tokenni kiriting.")
        st.stop()

# Thread-safe global kesh
TEMP_CACHE = {}

# --- 2. MUKAMMAL VA BIRLASHTIRILGAN SKRAPER ---
def scrape_longman_merged(word):
    try:
        formatted_word = word.lower().strip().replace(' ', '-')
        url = f"https://www.ldoceonline.com/dictionary/{formatted_word}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        # Ma'lumotlarni turkumlar (NOUN, VERB) bo'yicha guruhlash
        merged_data = {}
        
        for entry in entries:
            # Turkumni aniqlash
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().upper() if pos_tag else "OTHER"
            
            # Agar bu Phrasal Verb bo'lsa
            if "PhrVbEntry" in entry.get('class', []):
                pos_text = "PHRASAL VERB"

            hwd_tag = entry.find('span', class_='HWD')
            hwd = hwd_tag.text if hwd_tag else word
            pron_tag = entry.find('span', class_='PRON')
            pron = pron_tag.text if pron_tag else ""

            # Agar bu turkum hali lug'atda bo'lmasa, ochamiz
            if pos_text not in merged_data:
                merged_data[pos_text] = {"word": hwd, "pron": pron, "entries": []}

            senses_data = []
            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            
            for b in blocks:
                definition = b.find('span', class_='DEF')
                lexunit = b.find('span', class_='LEXUNIT')
                head_pv = b.find('span', class_='Head')
                if not definition and not lexunit and not head_pv: continue

                sub_senses = []
                subs = b.find_all('span', class_='Subsense')
                
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
                        "gram": b.find('span', class_='GRAM').text.strip() if b.find('span', class_='GRAM') else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                    })

                senses_data.append({
                    "signpost": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lexunit": lexunit.text.strip() if lexunit else (head_pv.text.strip() if head_pv else ""),
                    "subs": sub_senses
                })
            
            if senses_data:
                merged_data[pos_text]["entries"].append(senses_data)
        
        return merged_data
    except: return None

# --- 3. FORMATLASH (RAQAM VA MA'NO BIR QATORDA) ---
def format_merged_style(pos, content):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']: res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    global_counter = 1
    for entry_senses in content['entries']:
        for s in entry_senses:
            # Raqam yonidan ma'noni chiqarish
            line_start = f"<b>{global_counter}.</b> "
            extra = ""
            if s['signpost']: extra += f"<u>{s['signpost']}</u> "
            if s['lexunit']: extra += f"<b>{s['lexunit']}</b> "
            
            for i, sub in enumerate(s['subs']):
                gram = f"<code>[{sub['gram']}]</code> " if sub['gram'] else ""
                if i == 0:
                    sub_prefix = f"<b>{sub['letter']})</b> " if sub['letter'] else ""
                    res += f"{line_start}{extra}{sub_prefix}{gram}{sub['def']}\n"
                else:
                    sub_prefix = f"  <b>{sub['letter']})</b> "
                    res += f"{sub_prefix}{gram}{sub['def']}\n"
                
                for ex in sub['examples']:
                    res += f"    • <i>{ex}</i>\n"
            res += "\n"
            global_counter += 1
    return res

# --- 4. BOT HANDLERLARI ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom {m.from_user.first_name}! Longman AI Dictionary'ga xush kelibsiz.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_merged, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pos in data.keys():
            kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(chat_id)
        if not data: return await call.answer("Qayta qidiring.")

        final_msg = ""
        if choice == "all":
            for pos, content in data.items():
                final_msg += format_merged_style(pos, content) + "═" * 15 + "\n"
        else:
            final_msg = format_merged_style(choice, data[choice])

        if len(final_msg) > 4000:
            for i in range(0, len(final_msg), 4000): await call.message.answer(final_msg[i:i+4000])
        else: await call.message.answer(final_msg)
        await call.answer()

# --- 5. RUNNER (XAVFSIZ START) ---
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
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

# --- 6. UI ---
st.title("📕 Longman AI Dictionary")
start_bot_app()
st.success("✅ Bot Online holatda!")
st.info("So'z qidirilsa, barcha turkumlar birlashtirib ko'rsatiladi.")
