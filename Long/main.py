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
st.set_page_config(page_title="Longman Ultimate Edition", layout="centered")

class Config:
    try:
        BOT_TOKEN = st.secrets["BOT_TOKEN"]
    except:
        st.error("❌ Secrets bo'limida BOT_TOKEN kiritilmagan!")
        st.stop()
    DB_FILE = "user_settings_v13.json"

def get_user_data(user_id):
    if not os.path.exists(Config.DB_FILE):
        return {"history": [], "show_examples": True, "show_translation": False}
    with open(Config.DB_FILE, "r") as f:
        try:
            data = json.load(f)
            return data.get(str(user_id), {"history": [], "show_examples": True, "show_translation": False})
        except: return {"history": [], "show_examples": True, "show_translation": False}

def save_user_data(user_id, user_dict):
    data = {}
    if os.path.exists(Config.DB_FILE):
        with open(Config.DB_FILE, "r") as f:
            try: data = json.load(f)
            except: data = {}
    data[str(user_id)] = user_dict
    with open(Config.DB_FILE, "w") as f: json.dump(data, f, indent=4)

def translate_to_uz(text):
    if not text: return ""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=uz&dt=t&q={text}"
        res = requests.get(url, timeout=5).json()
        return res[0][0][0]
    except: return "⚠️ Tarjima xatoligi."

def clean_text(element):
    if not element: return ""
    return " ".join(element.get_text(separator=" ", strip=True).split())

TEMP_CACHE = {}

# --- 2. PROFESSIONAL SKRAPER (PRON VA PHRASAL VERBS TUZATILGAN) ---
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
        # Umumiy talaffuzni saqlash uchun
        global_pron = ""

        for entry in entries:
            # 1. Talaffuzni qidirish (agar bo'lsa yangilaymiz)
            pron_tag = entry.find('span', class_='PRON')
            if pron_tag:
                global_pron = clean_text(pron_tag)

            # 2. Turkumni aniqlash
            pos_tag = entry.find('span', class_='POS')
            pos = clean_text(pos_tag).upper() if pos_tag else "WORD"
            
            # 3. Phrasal Verb ekanini tekshirish
            is_phrvb = "PhrVbEntry" in entry.get('class', []) or entry.find('span', class_='PHRVB')
            if is_phrvb: pos = "PHRASAL VERB"
            
            hwd = clean_text(entry.find('span', class_='HWD')) or word

            if pos not in merged:
                merged[pos] = {"word": hwd, "pron": global_pron, "data": []}
            elif not merged[pos]["pron"] and global_pron:
                merged[pos]["pron"] = global_pron

            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            for b in blocks:
                head_pv = b.find(['span'], class_=['Head', 'PHRVB', 'LEXUNIT'])
                pv_name = clean_text(head_pv)
                
                defs = b.find_all('span', class_='DEF')
                if not defs and not pv_name: continue

                sub_list = []
                subs = b.find_all('span', class_='Subsense')
                if subs:
                    for idx, sub in enumerate(subs):
                        d_text = sub.find('span', class_='DEF')
                        if not d_text: continue
                        sub_list.append({
                            "letter": chr(97 + idx),
                            "gram": clean_text(sub.find('span', class_='GRAM')),
                            "def": clean_text(d_text),
                            "exs": [clean_text(ex) for ex in sub.find_all('span', class_='EXAMPLE')]
                        })
                else:
                    for d in defs:
                        sub_list.append({
                            "letter": "",
                            "gram": clean_text(b.find('span', class_='GRAM')),
                            "def": clean_text(d),
                            "exs": [clean_text(ex) for ex in b.find_all('span', class_='EXAMPLE')]
                        })

                if sub_list or pv_name:
                    merged[pos]["data"].append({
                        "sign": clean_text(b.find('span', class_='SIGNPOST')).upper(),
                        "lex": pv_name, "subs": sub_list
                    })
        return merged
    except: return None

# --- 3. FORMATLASH VA BO'LISH ---
def format_output(pos, content, show_examples, show_translation):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    # Har doim PRON bo'lsa chiqaramiz
    if content['pron']:
        res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    cnt = 1
    for s in content['data']:
        line_head = f"<b>{cnt}.</b> "
        sign = f"<u>{s['sign']}</u> " if s['sign'] else ""
        lex = f"<b>{s['lex']}</b> " if s['lex'] else ""
        
        for i, sub in enumerate(s['subs']):
            gram = f"<code>[{sub['gram'].strip('[]')}]</code> " if sub['gram'] else ""
            letter = f"<b>{sub['letter']})</b> " if sub['letter'] else ""
            copy_def = f"<b><code>{sub['def']}</code></b>"
            
            if i == 0: res += f"{line_head}{sign}{lex}{letter}{gram}{copy_def}\n"
            else: res += f"  {letter}{gram}{copy_def}\n"
            
            if show_translation:
                res += f"🇺🇿 <i>{translate_to_uz(sub['def'])}</i>\n"
            
            if show_examples:
                for ex in sub['exs']: res += f"    • <i>{ex}</i>\n"
        if not s['subs'] and lex: res += f"{line_head}{sign}{lex}\n"
        res += "\n"
        cnt += 1
    return res

async def send_sequential_messages(message, text):
    limit = 4000
    if len(text) <= limit: await message.answer(text)
    else:
        while len(text) > 0:
            split_at = text.rfind('\n', 0, limit) if len(text) > limit else len(text)
            if split_at == -1: split_at = limit
            await message.answer(text[:split_at])
            text = text[split_at:].strip()

# --- 4. HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    def get_main_kb(u_data):
        kb = ReplyKeyboardBuilder()
        kb.button(text="📜 Tarix")
        kb.button(text="🚫 Misollarsiz" if u_data['show_examples'] else "📝 Misollar bilan")
        kb.button(text="🔤 Tarjimasiz" if u_data['show_translation'] else "🌐 Tarjima bilan")
        kb.adjust(1, 2)
        return kb.as_markup(resize_keyboard=True)

    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer("Salom! So'z yuboring:", reply_markup=get_main_kb(get_user_data(m.from_user.id)))

    @dp.message(F.text == "📜 Tarix")
    async def btn_history(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        if not u_data['history']: return await m.answer("Tarix bo'sh.")
        msg = "📜 <b>Oxirgi qidiruvlar:</b>\n\n"
        for i, word in enumerate(u_data['history'], 1): msg += f"{i}. <code>{word}</code>\n"
        await m.answer(msg)

    @dp.message(F.text.in_(["🚫 Misollarsiz", "📝 Misollar bilan", "🔤 Tarjimasiz", "🌐 Tarjima bilan"]))
    async def toggle_settings(m: types.Message):
        u_data = get_user_data(m.from_user.id)
        if "Misol" in m.text: u_data['show_examples'] = not u_data['show_examples']
        else: u_data['show_translation'] = not u_data['show_translation']
        save_user_data(m.from_user.id, u_data)
        await m.answer("Sozlamalar yangilandi.", reply_markup=get_main_kb(u_data))

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
        await m.answer(      f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:\n\n"
            f"<i>Ma'nolarni ko'rish uchun pastdagi turkumlardan (Noun, Verb, Adj) birini bosing.</i>", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        await call.answer() # Timeout oldini olish uchun
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        u_data = get_user_data(call.from_user.id)
        if not data: return await call.message.answer("Qayta qidiring.")
        
        prog = await call.message.edit_text("🔍")
        for em in ["🎗", "✍️", "⌛"]:
            await asyncio.sleep(0.3)
            try: await prog.edit_text(em)
            except: pass
        
        if choice == "all":
            full_text = ""
            for pos, content in data.items():
                full_text += format_output(pos, content, u_data['show_examples'], u_data['show_translation']) + "═"*15 + "\n"
            await send_sequential_messages(call.message, full_text)
        else:
            await send_sequential_messages(call.message, format_output(choice, data[choice], u_data['show_examples'], u_data['show_translation']))
        
        try: await prog.delete()
        except: pass

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
    
    if "bot_thread" not in st.session_state:
        st.session_state.bot_thread = threading.Thread(target=_run, daemon=True)
        st.session_state.bot_thread.start()

st.title("📕 Longman Ultimate Pro")
start_bot()
st.success("✅ Bot Online!")
                



