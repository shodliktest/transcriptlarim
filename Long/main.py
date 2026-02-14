import asyncio
import os
import json
import threading
import requests
from bs4 import BeautifulSoup
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- 1. CONFIG ---
st.set_page_config(page_title="Longman AI Pro", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ Secrets'da BOT_TOKEN topilmadi!")
        st.stop()
    HISTORY_DB = "history_db.json"

TEMP_CACHE = {}

# --- 2. HISTORY LOGIC ---
def save_to_history(user_id, word):
    db_file = Config.HISTORY_DB
    if not os.path.exists(db_file):
        with open(db_file, "w") as f: json.dump({}, f)
    
    with open(db_file, "r") as f:
        try: data = json.load(f)
        except: data = {}
    
    uid = str(user_id)
    if uid not in data: data[uid] = []
    
    if word in data[uid]: data[uid].remove(word)
    data[uid].insert(0, word)
    data[uid] = data[uid][:15] # Oxirgi 15 ta so'z
    
    with open(db_file, "w") as f:
        json.dump(data, f, indent=4)

def get_history(user_id):
    if not os.path.exists(Config.HISTORY_DB): return []
    with open(Config.HISTORY_DB, "r") as f:
        try: data = json.load(f)
        except: return []
    return data.get(str(user_id), [])

# --- 3. MERGED SCRAPER ---
def scrape_longman_merged(word):
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
            if "PhrVbEntry" in entry.get('class', []): pos_text = "PHRASAL VERB"

            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""

            if pos_text not in merged_data:
                merged_data[pos_text] = {"word": hwd, "pron": pron, "entries": []}

            senses = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            senses_data = []
            for b in senses:
                definition = b.find('span', class_='DEF')
                lexunit = b.find('span', class_='LEXUNIT')
                head_pv = b.find('span', class_='Head')
                if not definition and not lexunit and not head_pv: continue

                sub_list = []
                subs = b.find_all('span', class_='Subsense')
                if subs:
                    for sub_idx, sub in enumerate(subs):
                        sub_def = sub.find('span', class_='DEF')
                        if not sub_def: continue
                        sub_list.append({
                            "letter": chr(97 + sub_idx),
                            "gram": sub.find('span', class_='GRAM').text.strip() if sub.find('span', class_='GRAM') else "",
                            "def": sub_def.text.strip(),
                            "examples": [ex.text.strip() for ex in sub.find_all('span', class_='EXAMPLE')]
                        })
                else:
                    sub_list.append({
                        "letter": "",
                        "gram": b.find('span', class_='GRAM').text.strip() if b.find('span', class_='GRAM') else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                    })

                senses_data.append({
                    "signpost": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lexunit": lexunit.text.strip() if lexunit else (head_pv.text.strip() if head_pv else ""),
                    "subs": sub_list
                })
            if senses_data: merged_data[pos_text]["entries"].append(senses_data)
        return merged_data
    except: return None

# --- 4. FORMATTING (FIXED NAMEERROR) ---
def format_merged_style(pos, content):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']: res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    cnt = 1
    for entry_senses in content['entries']:
        for s in entry_senses:
            line_head = f"<b>{cnt}.</b> "
            sign = f"<u>{s['signpost']}</u> " if s['signpost'] else ""
            lex = f"<b>{s['lexunit']}</b> " if s['lexunit'] else ""
            
            for i, sub in enumerate(s['subs']):
                gram = f"[{sub['gram']}] " if sub['gram'] else ""
                letter = f"<b>{sub['letter']})</b> " if sub['letter'] else ""
                
                # NUSXALANADIGAN QISM (<code> tegi ichida)
                copyable_def = f"<code>{sub['def']}</code>"
                
                if i == 0:
                    # Raqam bilan bir qatorda
                    res += f"{line_head}{sign}{lex}{letter}{gram}{copyable_def}\n"
                else:
                    # Bandlar yangi qatorda
                    res += f"  {letter}{gram}{copyable_def}\n"
                
                # MISOLLAR (Oddiy matn - nusxalanmaydi)
                for ex in sub['examples']:
                    res += f"    • <i>{ex}</i>\n"
            res += "\n"
            cnt += 1
    return res

# --- 5. HANDLERS ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        await m.answer(f"Salom {m.from_user.first_name}! Inglizcha so'z yuboring:", 
                       reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "📜 Tarix")
    async def show_history(m: types.Message):
        history = get_history(m.from_user.id)
        if not history:
            return await m.answer("Sizda hali qidiruvlar tarixi yo'q.")
        
        kb = InlineKeyboardBuilder()
        for word in history:
            kb.button(text=word, callback_data=f"h_{word}")
        kb.adjust(2)
        await m.answer("Oxirgi qidiruvlaringiz:", reply_markup=kb.as_markup())

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        if len(word.split()) > 1: return await m.answer("Faqat bitta so'z yuboring.")
        
        save_to_history(m.from_user.id, word)
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_merged, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("h_"))
    async def history_search(call: types.CallbackQuery):
        word = call.data.replace("h_", "")
        # Tarixdan bosilganda avtomatik qidirish
        wait = await call.message.answer(f"🔍 <b>{word}</b> qayta qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_merged, word)
        await wait.delete()
        if not data: return await call.message.answer("So'z topilmadi.")
        TEMP_CACHE[call.message.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await call.message.answer(f"📦 <b>{word.upper()}</b> bo'limini tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")
        
        msg = ""
        if choice == "all":
            for pos, content in data.items(): msg += format_merged_style(pos, content) + "═" * 15 + "\n"
        else:
            msg = format_merged_style(choice, data[choice])
        
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000): await call.message.answer(msg[i:i+4000])
        else: await call.message.answer(msg)
        await call.answer()

# --- 6. RUNNER ---
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

st.title("📕 Longman AI Pro")
start_bot_app()
st.success("✅ Bot Online!")
