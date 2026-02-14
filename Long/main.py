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

# --- 1. KONFIGURATSIYA ---
st.set_page_config(page_title="Longman AI Text Pro", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ Secrets'da BOT_TOKEN topilmadi!")
        st.stop()
    DB_FILE = "user_data.json"

# Foydalanuvchi sozlamalari va tarixini saqlash
def get_user_data(user_id):
    if not os.path.exists(Config.DB_FILE):
        return {"history": [], "show_examples": True}
    with open(Config.DB_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), {"history": [], "show_examples": True})

def save_user_data(user_id, user_dict):
    data = {}
    if os.path.exists(Config.DB_FILE):
        with open(Config.DB_FILE, "r") as f:
            try: data = json.load(f)
            except: data = {}
    data[str(user_id)] = user_dict
    with open(Config.DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

TEMP_CACHE = {}

# --- 2. MATNLI SKRAPER ---
def scrape_longman_clean(word):
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
            pos_tag = entry.find('span', class_='POS')
            pos = pos_tag.text.strip().upper() if pos_tag else "WORD"
            if "PhrVbEntry" in entry.get('class', []): pos = "PHRASAL VERB"
            
            hwd = entry.find('span', class_='HWD').text if entry.find('span', class_='HWD') else word
            pron = entry.find('span', class_='PRON').text if entry.find('span', class_='PRON') else ""

            if pos not in merged:
                merged[pos] = {"word": hwd, "pron": pron, "entries": []}

            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            entry_senses = []
            for b in blocks:
                definition = b.find('span', class_='DEF')
                if not definition: continue
                
                entry_senses.append({
                    "sign": b.find('span', class_='SIGNPOST').text.strip().upper() if b.find('span', class_='SIGNPOST') else "",
                    "lex": b.find('span', class_='LEXUNIT').text.strip() if b.find('span', class_='LEXUNIT') else "",
                    "def": definition.text.strip(),
                    "exs": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                })
            if entry_senses:
                merged[pos]["entries"].append(entry_senses)
        return merged
    except: return None

# --- 3. FORMATLASH ---
def format_output(pos, content, show_examples):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']: res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    cnt = 1
    for group in content['entries']:
        for s in group:
            sign = f"<u>{s['sign']}</u> " if s['sign'] else ""
            lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
            # NUSXALANADIGAN VA QALIN TA'RIF
            res += f"<b>{cnt}.</b> {sign}{lex}<b><code>{s['def']}</code></b>\n"
            
            if show_examples:
                for ex in s['exs']:
                    res += f"  • <i>{ex}</i>\n"
            res += "\n"
            cnt += 1
    return res

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        user_id = m.from_user.id
        u_data = get_user_data(user_id)
        
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        mode_text = "🚫 Misollarsiz" if u_data['show_examples'] else "📝 Misollar bilan"
        kb.button(text=mode_text)
        kb.adjust(2)
        
        await m.answer(f"Salom {m.from_user.first_name}! Inglizcha so'z yuboring:", 
                       reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text == "📜 Tarix")
    async def btn_history(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        if not u_data['history']: return await m.answer("Tarix bo'sh.")
        
        kb = InlineKeyboardBuilder()
        for w in u_data['history']: kb.button(text=w, callback_data=f"h_{w}")
        kb.adjust(2)
        await m.answer("Oxirgi qidiruvlar:", reply_markup=kb.as_markup())

    @dp.message(F.text.in_(["🚫 Misollarsiz", "📝 Misollar bilan"]))
    async def btn_toggle_mode(m: types.Message):
        user_id = m.from_user.id
        u_data = get_user_data(user_id)
        
        # Rejimni almashtirish
        new_mode = not u_data['show_examples']
        u_data['show_examples'] = new_mode
        save_user_data(user_id, u_data)
        
        # Yangi tugmalarni yasash
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        mode_btn = "🚫 Misollarsiz" if new_mode else "📝 Misollar bilan"
        kb.button(text=mode_btn)
        kb.adjust(2)
        
        status = "faollashtirildi" if new_mode else "o'chirildi"
        await m.answer(f"Rejim o'zgardi: Misollar {status}.", 
                       reply_markup=kb.as_markup(resize_keyboard=True))

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        # Tarixga saqlash
        u_data = get_user_data(m.from_user.id)
        if word in u_data['history']: u_data['history'].remove(word)
        u_data['history'].insert(0, word)
        u_data['history'] = u_data['history'][:15]
        save_user_data(m.from_user.id, u_data)
        
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_clean, word)
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
        u_data = get_user_data(call.from_user.id)
        if not data: return await call.answer("Qayta qidiring.")

        if choice == "all":
            for pos, content in data.items():
                await call.message.answer(format_output(pos, content, u_data['show_examples']))
        else:
            await call.message.answer(format_output(choice, data[choice], u_data['show_examples']))
        await call.answer()

    @dp.callback_query(F.data.startswith("h_"))
    async def history_search(call: types.CallbackQuery):
        word = call.data.replace("h_", "")
        await call.answer(f"Qidirilmoqda: {word}")
        data = await asyncio.to_thread(scrape_longman_clean, word)
        if data:
            TEMP_CACHE[call.message.chat.id] = data
            kb = InlineKeyboardBuilder()
            for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
            await call.message.answer(f"📦 {word.upper()}:", reply_markup=kb.as_markup())

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

st.title("📕 Longman AI Text Pro")
start_bot()
st.success("✅ Bot Online holatda!")
st.info("So'z qidirilsa, tanlangan rejim bo'yicha ma'lumot chiqadi.")
        
