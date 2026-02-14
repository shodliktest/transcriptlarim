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

# --- 1. KONFIGURATSIYA ---
class Config:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    # TEMP_CACHE bot oqimi uchun xavfsiz xotira vazifasini bajaradi
TEMP_CACHE = {}

# --- 2. PROFESSIONAL SKRAPER (Hamma narsani oluvchi) ---
def scrape_longman_perfect(word):
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
            # Asosiy ma'lumotlar
            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().lower() if pos_tag else "word"
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""
            
            senses_data = []
            # Barcha Sense va Phrasal Verblarni qidiramiz
            senses = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            
            valid_counter = 1
            for s in senses:
                # Ta'rif yoki Birikmani aniqlash
                definition = s.find('span', class_='DEF')
                lexunit = s.find('span', class_='LEXUNIT')
                
                # Agar ta'rif ham, birikma ham bo'lmasa - bu bo'sh blok
                if not definition and not lexunit: continue

                signpost = s.find('span', class_='SIGNPOST')
                gram = s.find('span', class_='GRAM')
                
                # Misollarni yig'ish (Hech birini qoldirmay)
                examples = [ex.text.strip() for ex in s.find_all('span', class_='EXAMPLE') if ex.text.strip()]

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
                        "gram": gram.text.strip() if gram else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": examples
                    })

                senses_data.append({
                    "id": valid_counter,
                    "signpost": signpost.text.strip().upper() if signpost else "",
                    "lexunit": lexunit.text.strip() if lexunit else "",
                    "subs": sub_senses
                })
                valid_counter += 1

            if senses_data:
                pos_key = f"{pos_text}_{entry_idx}"
                all_data[pos_key] = {"word": hwd, "pos": pos_text.upper(), "pron": pron, "data": senses_data}
        return all_data
    except: return None

# --- 3. FORMATLASH ---
def format_pro(data):
    text = f"📕 <b>{data['word'].upper()}</b> /{data['pron']}/ <i>{data['pos'].lower()}</i>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    for s in data['data']:
        header = f"<b>{s['id']}</b> "
        if s['signpost']: header += f"<u>{s['signpost']}</u> "
        if s['lexunit']: header += f"<b>{s['lexunit']}</b> "
        text += header.strip() + "\n"

        for sub in s['subs']:
            prefix = f"  <b>{sub['letter']})</b> " if sub['letter'] else "  "
            gram = f"<code>{sub['gram']}</code> " if sub['gram'] else ""
            text += f"{prefix}{gram}{sub['def']}\n"
            for ex in sub['examples']:
                text += f"    • <i>{ex}</i>\n"
        text += "\n"
    return text

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer("👋 Salom! Inglizcha so'z yuboring, barcha ma'nolarni Longmandan to'liq olib beraman.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_perfect, word)
        await wait.delete()

        if not data:
            return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            kb.button(text=content['pos'], callback_data=f"x_{pk}")
        if len(data) > 1: kb.button(text="📚 Hammasi", callback_data="x_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("x_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("x_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")

        res = ""
        if choice == "all":
            for pk in data: res += format_pro(data[pk]) + "═" * 15 + "\n"
        else:
            res = format_pro(data[choice])

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

st.title("📕 Longman Perfect Scraper")
start_bot()
st.success("Bot Online! Endi barcha bloklar (Gloss finish, Phrasal verbs va h.k.) chiqadi.")
