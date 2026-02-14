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

# --- 2. OPTIMALLASHTIRILGAN SKRAPER ---
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

        # Ma'lumotlarni turkum bo'yicha guruhlash uchun lug'at
        merged_data = {}
        
        for entry in entries:
            pos_tag = entry.find('span', class_='POS')
            pos_text = pos_tag.text.strip().upper() if pos_tag else "OTHER"
            
            # Agar bu Phrasal Verb bo'lsa, turkumni o'zgartiramiz
            if "PhrVbEntry" in entry.get('class', []):
                pos_text = "PHRASAL VERB"

            hwd_tag = entry.find('span', class_='HWD')
            hwd = hwd_tag.text if hwd_tag else word
            pron_tag = entry.find('span', class_='PRON')
            pron = pron_tag.text if pron_tag else ""

            if pos_text not in merged_data:
                merged_data[pos_text] = {
                    "word": hwd,
                    "pron": pron,
                    "entries": []
                }

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
    except Exception:
        return None

# --- 3. FORMATLASH (BIRLASHTIRILGAN) ---
def format_merged_style(pos, content):
    res = f"📕 <b>{content['word'].upper()}</b> [{pos}]\n"
    if content['pron']:
        res += f"🗣 /{content['pron']}/\n"
    res += "━━━━━━━━━━━━━━━\n\n"
    
    global_counter = 1
    for entry_senses in content['entries']:
        for s in entry_senses:
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
    @dp.message(F.text)
    async def handle_word(m: types.Message):
        if m.text.startswith('/'): return
        word = m.text.strip().lower()
        wait = await m.answer("🔍 Qidirilmoqda...")
        data = await asyncio.to_thread(scrape_longman_merged, word)
        await wait.delete()

        if not data:
            return await m.answer("❌ So'z topilmadi.")

        TEMP_CACHE[m.chat.id] = data
        kb = InlineKeyboardBuilder()
        # Endi har bir turkum uchun faqat bitta tugma chiqadi
        for pos in data.keys():
            kb.button(text=pos, callback_data=f"v_{pos}")
        if len(data) > 1: kb.button(text="📚 All", callback_data="v_all")
        kb.adjust(2)
        await m.answer(f"📦 <b>{word.upper()}</b> uchun bo'limni tanlang:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("v_"))
    async def process_view(call: types.CallbackQuery):
        choice = call.data.replace("v_", "")
        data = TEMP_CACHE.get(call.message.chat.id)
        if not data: return await call.answer("Qayta qidiring.")

        final_msg = ""
        if choice == "all":
            for pos, content in data.items():
                final_msg += format_merged_style(pos, content) + "═" * 15 + "\n"
        else:
            final_msg = format_merged_style(choice, data[choice])

        if len(final_msg) > 4000:
            for i in range(0, len(final_msg), 4000): 
                await call.message.answer(final_msg[i:i+4000])
        else: 
            await call.message.answer(final_msg)
        await call.answer()
                      
