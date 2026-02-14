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
st.set_page_config(page_title="Longman Ultimate Pro", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ Secrets'da BOT_TOKEN topilmadi!")
        st.stop()
    DB_FILE = "user_settings_v5.json"

# Foydalanuvchi ma'lumotlarini boshqarish
def get_user_data(user_id):
    if not os.path.exists(Config.DB_FILE):
        return {"history": [], "show_examples": True, "show_translation": False}
    with open(Config.DB_FILE, "r") as f:
        try:
            data = json.load(f)
            user_info = data.get(str(user_id), {"history": [], "show_examples": True, "show_translation": False})
            # Agar eski versiyadan show_translation bo'lmasa, qo'shib qo'yamiz
            if "show_translation" not in user_info: user_info["show_translation"] = False
            return user_info
        except:
            return {"history": [], "show_examples": True, "show_translation": False}

def save_user_data(user_id, user_dict):
    data = {}
    if os.path.exists(Config.DB_FILE):
        with open(Config.DB_FILE, "r") as f:
            try: data = json.load(f)
            except: data = {}
    data[str(user_id)] = user_dict
    with open(Config.DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Tarjima funksiyasi (Google Translate API orqali)
def translate_to_uz(text):
    if not text: return ""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=uz&dt=t&q={text}"
        res = requests.get(url, timeout=5).json()
        return res[0][0][0]
    except:
        return "⚠️ Tarjima qilishda xatolik."

TEMP_CACHE = {}

# --- 2. PROFESSIONAL SKRAPER ---
def scrape_longman_ultimate(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip().replace(' ', '-')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=12)
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
                merged[pos] = {"word": hwd, "pron": pron, "data": []}

            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            for b in blocks:
                head_pv = b.find(['span'], class_=['Head', 'PHRVB', 'LEXUNIT'])
                pv_name = head_pv.get_text(strip=True) if head_pv else ""
                
                defs = b.find_all('span', class_='DEF')
                if not defs and not pv_name: continue

                sub_list = []
                subs = b.find_all('span', class_='Subsense')
                if subs:
                    for sub_idx, sub in enumerate(subs):
                        d_text = sub.find('span', class_='DEF')
                        if not d_text: continue
                        sub_list.append({
                            "letter": chr(97 + sub_idx),
                            "gram": sub.find('span', class_='GRAM').text.strip() if sub.find('span', class_='GRAM') else "",
                            "def": d_text.get_text(strip=True),
                            "exs": [ex.get_text(strip=True) for ex in sub.find_all('span', class_='EXAMPLE')]
                        })
                else:
                    for d in defs:
                        gram = b.find('span', class_='GRAM')
                        sub_list.append({
                            "letter": "",
                            "gram": gram.get_text(strip=True) if gram else "",
                            "def": d.get_text(strip=True),
                            "exs": [ex.get_text(strip=True) for ex in b.find_all('span', class_='EXAMPLE')]
                        })

                if sub_list or pv_name:
                    merged[pos]["data"].append({
                        "sign": b.find('span', class_='SIGNPOST').get_text(strip=True).upper() if b.find('span', class_='SIGNPOST') else "",
                        "lex": pv_name,
                        "subs": sub_list
                    })
        return merged
    except: return None

# --- 3. FORMATLASH (NUSXALASH, QALINLIK VA TARJIMA) ---
def format_output(pos, content, show_examples, show_translation):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']: res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    cnt = 1
    for s in content['data']:
        line_head = f"<b>{cnt}.</b> "
        sign = f"<u>{s['sign']}</u> " if s['sign'] else ""
        lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
        
        for i, sub in enumerate(s['subs']):
            gram = f"<code>[{sub['gram']}]</code> " if sub['gram'] else ""
            letter = f"<b>{sub['letter']})</b> " if sub['letter'] else ""
            
            # ASOSIY TA'RIF: QALIN VA NUSXALANADIGAN
            copy_def = f"<b><code>{sub['def']}</code></b>"
            
            if i == 0: res += f"{line_head}{sign}{lex}{letter}{gram}{copy_def}\n"
            else: res += f"  {letter}{gram}{copy_def}\n"
            
            # Tarjima qo'shish
            if show_translation:
                tr_text = translate_to_uz(sub['def'])
                res += f"🇺🇿 <i>{tr_text}</i>\n"
            
            if show_examples:
                for ex in sub['exs']: res += f"    • <i>{ex}</i>\n"
        
        if not s['subs'] and lex: res += f"{line_head}{sign}{lex}\n"
        res += "\n"
        cnt += 1
    return res

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    # Reply Keyboard yasash funksiyasi
    def get_main_kb(u_data):
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        mode_ex = "🚫 Misollarsiz" if u_data['show_examples'] else "📝 Misollar bilan"
        mode_tr = "🔤 Tarjimasiz" if u_data['show_translation'] else "🌐 Tarjima bilan"
        kb.button(text=mode_ex)
        kb.button(text=mode_tr)
        kb.adjust(2, 1)
        return kb.as_markup(resize_keyboard=True)

    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        await m.answer(f"Xush kelibsiz! Inglizcha so'z yuboring:", reply_markup=get_main_kb(u_data))

    @dp.message(F.text == "📜 Tarix")
    async def btn_history(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        history = u_data.get('history', [])
        if not history: return await m.answer("📭 Tarix hali bo'sh.")
        msg = "📜 <b>Oxirgi qidiruvlar:</b>\n\n"
        for i, word in enumerate(history, 1): msg += f"{i}. <code>{word}</code>\n"
        await m.answer(msg)

    @dp.message(F.text.in_(["🚫 Misollarsiz", "📝 Misollar bilan"]))
    async def toggle_examples(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        u_data['show_examples'] = not u_data['show_examples']
        save_user_data(m.from_user.id, u_data)
        await m.answer(f"Misollar rejimi o'zgardi.", reply_markup=get_main_kb(u_data))

    @dp.message(F.text.in_(["🔤 Tarjimasiz", "🌐 Tarjima bilan"]))
    async def toggle_translation(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        u_data['show_translation'] = not u_data['show_translation']
        save_user_data(m.from_user.id, u_data)
        status = "yoqildi" if u_data['show_translation'] else "o'chirildi"
        await m.answer(f"O'zbekcha tarjima {status}.", reply_markup=get_main_kb(u_data))

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        
        u_data = get_user_data(m.from_user.id)
        if word in u_data['history']: u_data['history'].remove(word)
        u_data['history'].insert(0, word); u_data['history'] = u_data['history'][:15]
        save_user_data(m.from_user.id, u_data)
        
        wait = await m.answer("⏳") 
        data = await asyncio.to_thread(scrape_longman_ultimate, word)
        await wait.delete()

        if not data: return await m.answer("❌ So'z topilmadi.")
        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pos in data.keys(): kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b>:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        u_data = get_user_data(call.from_user.id)
        if not data: return await call.answer("Qayta qidiring.")
        
        if choice == "all":
            for pos, content in data.items(): 
                await call.message.answer(format_output(pos, content, u_data['show_examples'], u_data['show_translation']))
        else: 
            await call.message.answer(format_output(choice, data[choice], u_data['show_examples'], u_data['show_translation']))
        await call.answer()

# --- 5. RUNNER ---
@st.cache_resource
def start_bot():
    def _run():
        async def main():
            bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher(); register_handlers(dp)
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(main())
    threading.Thread(target=_run, daemon=True).start()

st.title("📕 Longman Ultimate Pro + Translation")
start_bot()
st.success("✅ Bot faol!")
                
