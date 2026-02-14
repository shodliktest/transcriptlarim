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

# --- 1. CONFIG ---
class Config:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]

TEMP_CACHE = {}

# --- 2. MUKAMMAL SKRAPER (PHRASAL VERBS VA TO'LIQ FORMAT) ---
def scrape_longman_final(word):
    try:
        url = f"https://www.ldoceonline.com/dictionary/{word.lower().strip().replace(' ', '-')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None

        soup = BeautifulSoup(res.text, 'lxml')
        # Sahifadagi barcha lug'at kirishlarini olamiz
        entries = soup.find_all('span', class_='dictentry')
        if not entries: return None

        all_data = {}
        
        for entry_idx, entry in enumerate(entries):
            # 1. So'z va Turkum
            hwd_tag = entry.find('span', class_='HWD')
            hwd = hwd_tag.text if hwd_tag else word
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().upper() if pos_tag else "WORD"
            
            # 2. Talaffuz
            pron_tag = entry.find('span', class_='PRON')
            pron = pron_tag.text if pron_tag else ""

            # 3. Ma'nolar (Senses)
            senses_data = []
            # 'Sense' yoki 'PhrVbEntry' (Ibora fe'llar) bloklarini qidiramiz
            blocks = entry.find_all(['span'], class_=['Sense', 'PhrVbEntry'])
            
            valid_counter = 1
            for b in blocks:
                definition = b.find('span', class_='DEF')
                lexunit = b.find('span', class_='LEXUNIT')
                # Phrasal verb sarlavhasi ba'zan 'Head' ichida keladi
                head_pv = b.find('span', class_='Head')
                
                if not definition and not lexunit and not head_pv: continue

                signpost = b.find('span', class_='SIGNPOST')
                sign_text = signpost.text.strip().upper() if signpost else ""
                
                # Ibora nomi (agar bo'lsa)
                lex_text = lexunit.text.strip() if lexunit else (head_pv.text.strip() if head_pv else "")

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
                    gram = b.find('span', class_='GRAM')
                    sub_senses.append({
                        "letter": "",
                        "gram": gram.text.strip() if gram else "",
                        "def": definition.text.strip() if definition else "",
                        "examples": [ex.text.strip() for ex in b.find_all('span', class_='EXAMPLE')]
                    })

                senses_data.append({
                    "id": valid_counter,
                    "signpost": sign_text,
                    "lexunit": lex_text,
                    "subs": sub_senses
                })
                valid_counter += 1

            if senses_data:
                # Agar bu ibora fe'li bo'lsa, turkumni 'PHRASAL VERB' deb belgilaymiz
                if "PhrVbEntry" in b.get('class', []):
                    pos_text = "PHRASAL VERB"
                
                # Agar pos_text lug'atda bo'lsa, unikal qilish
                key = f"{pos_text}_{entry_idx}"
                all_data[key] = {
                    "word": hwd,
                    "pos": pos_text,
                    "pron": pron,
                    "data": senses_data
                }
        
        return all_data
    except: return None

# --- 3. FORMATLASH (RAQAM VA MA'NO BIR QATORDA) ---
def format_pro_style(data):
    # Sarlavha: 📕 WORD [POS]
    # 🗣 /pron/
    header_part = f"📕 <b>{data['word'].upper()}</b> [{data['pos']}]\n"
    if data['pron']:
        header_part += f"🗣 /{data['pron']}/\n"
    header_part += "━━━━━━━━━━━━━━━\n\n"
    
    body_part = ""
    for s in data['data']:
        # Ma'no raqami
        line = f"<b>{s['id']}.</b> "
        
        # Agar signpost bo'lsa yoniga qo'shish
        if s['signpost']: line += f"<u>{s['signpost']}</u> "
        if s['lexunit']: line += f"<b>{s['lexunit']}</b> "
        
        # Har bir bandni (a, b, c yoki asosiy) qayta ishlash
        for i, sub in enumerate(s['subs']):
            prefix = ""
            # Agar bu b, c... band bo'lsa yangi qatordan boshlash
            if i > 0: prefix = f"\n  <b>{sub['letter']})</b> "
            elif sub['letter']: prefix = f"<b>{sub['letter']})</b> "
            
            gram = f"<code>[{sub['gram']}]</code> " if sub['gram'] else ""
            
            # Birinchi band raqam bilan bir qatorda chiqadi
            if i == 0:
                body_part += line + prefix + gram + sub['def'] + "\n"
            else:
                body_part += prefix + gram + sub['def'] + "\n"
            
            # Misollar har doim ostidan
            for ex in sub['examples']:
                body_part += f"    • <i>{ex}</i>\n"
        body_part += "\n"
    
    return header_part + body_part

# --- 4. BOT RUNNER VA HANDLERLAR ---
def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(m: types.Message):
        await m.answer(f"👋 Salom {m.from_user.first_name}!\nInglizcha so'z yoki Phrasal verb yuboring.")

    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_final, word)
        await wait.delete()

        if not data:
            return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        for pk, content in data.items():
            # Tugma nomini chiroyli qilish (NOUN, VERB, PHRASAL VERB)
            btn_name = pk.split('_')[0]
            kb.button(text=btn_name, callback_data=f"sh_{pk}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="sh_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("sh_"))
    async def process_view(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        choice = call.data.replace("sh_", "")
        data = TEMP_CACHE.get(chat_id)
        if not data: return await call.answer("Qayta qidiring.")

        res_text = ""
        if choice == "all":
            for pk in data: res_text += format_pro_style(data[pk]) + "═" * 15 + "\n"
        else:
            res_text = format_pro_style(data[choice])

        if len(res_text) > 4000:
            for i in range(0, len(res_text), 4000): await call.message.answer(res_text[i:i+4000])
        else: await call.message.answer(res_text)
        await call.answer()

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

st.title("📕 Longman Ultimate (Fixed Formatting)")
start_bot()
st.success("Bot Online! Raqamlar va ma'no bir qatorda, Phrasal verblar qo'shildi.")
                
