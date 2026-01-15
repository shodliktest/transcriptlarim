import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
# Sizning Sayt manzilingiz (Aniq yozildi)
SITE_URL = "https://shodlik1transcript.streamlit.app"

# Maxfiy kalitlarni olish (Secrets)
try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("❌ Xatolik: Streamlit Secrets sozlanmagan!")
    st.stop()

# Sahifa sozlamalari
st.set_page_config(page_title="Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. CSS DIZAYN (NEON & DARK) ---
st.markdown("""
<style>
    .stApp { background-color: #050505; color: white; }
    h1, h2, h3 { color: #ffffff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; text-align: center; }
    .karaoke-box {
        background: rgba(20, 20, 20, 0.9); border: 2px solid #00e5ff;
        border-radius: 15px; padding: 20px;
        box-shadow: 0 0 20px rgba(0, 229, 255, 0.2); margin-top: 20px;
    }
    .lyric-line { padding: 10px; border-bottom: 1px solid #333; margin-bottom: 5px; }
    .lyric-text { font-size: 20px; font-weight: bold; color: #fff; }
    .lyric-trans { font-size: 16px; color: #aaa; font-style: italic; }
    .status-ok { color: #0f0; border: 1px solid #0f0; padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASTUR MANTIQI (ROUTER) ---
user_id = st.query_params.get("uid", None)

# --- A) KARAOKE PLEYER REJIMI ---
if user_id:
    st.markdown("<h1>🎵 KARAOKE TARIXI</h1>", unsafe_allow_html=True)
    
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents:runQuery?key={FB_API_KEY}"
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "transcriptions"}],
            "where": {"fieldFilter": {"field": {"fieldPath": "uid"}, "op": "EQUAL", "value": {"stringValue": str(user_id)}}},
            "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}]
        }
    }
    
    try:
        res = requests.post(url, json=query).json()
        if res and len(res) > 0 and 'document' in res[0]:
            for item in res:
                doc = item['document']['fields']
                fname = doc['filename']['stringValue']
                json_str = doc.get('data', doc.get('transcript', {})).get('stringValue')
                if json_str:
                    t_data = json.loads(json_str)
                    with st.expander(f"🎧 {fname}"):
                        html = f"""<div class="karaoke-box"><h3 style="color:#00e5ff; text-align:center;">{fname}</h3><div style="height:400px; overflow-y:auto;">"""
                        for line in t_data:
                            html += f"""<div class="lyric-line"><div class="lyric-text">{line['text']}</div>{'<div class="lyric-trans">'+line['translated']+'</div>' if line.get('translated') else ''}</div>"""
                        html += "</div></div>"
                        st.components.v1.html(html, height=450, scrolling=True)
        else:
            st.warning("Tarix bo'sh.")
    except Exception as e:
        st.error(f"Xato: {e}")
    st.stop()

# --- B) BOT SERVER REJIMI ---
st.title("🤖 Bot Server Statusi")
st.markdown('<div class="status-ok">✅ TIZIM AKTIV</div>', unsafe_allow_html=True)

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

def save_to_firestore(uid, username, filename, transcript_data):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
        payload = {"fields": {"uid": {"stringValue": str(uid)}, "username": {"stringValue": str(username)}, "filename": {"stringValue": filename}, "data": {"stringValue": json.dumps(transcript_data)}, "created_at": {"stringValue": now}}}
        requests.post(url, json=payload)
    except Exception as e: print(f"Save Error: {e}")

@bot.message_handler(commands=['start'])
def welcome(m):
    my_link = f"{SITE_URL}/?uid={m.chat.id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📂 Mening Arxivim (Sayt)", url=my_link))
    bot.reply_to(m, "👋 Assalomu alaykum! Audio yuboring.", reply_markup=markup)

@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(m):
    try:
        if m.content_type=='audio': fid=m.audio.file_id; fname=m.audio.file_name or "audio.mp3"
        else: fid=m.voice.file_id; fname="voice.ogg"
            
        f_info = bot.get_file(fid)
        down_file = bot.download_file(f_info.file_path)
        path = f"u_{m.chat.id}_{int(datetime.now().timestamp())}.mp3"
        with open(path, "wb") as f: f.write(down_file)
        
        user_data[m.chat.id] = {"path": path, "name": fname}
        
        mark = types.InlineKeyboardMarkup(row_width=2)
        mark.add(types.InlineKeyboardButton("🇺🇿 O'zbek", callback_data="uz"), types.InlineKeyboardButton("🇷🇺 Rus", callback_data="ru"), types.InlineKeyboardButton("🇬🇧 Ingliz", callback_data="en"), types.InlineKeyboardButton("📄 Original", callback_data="original"))
        
        bot.send_message(m.chat.id, "Tarjima tilini tanlang:", reply_markup=mark)
    except Exception as e: bot.send_message(m.chat.id, f"Xato: {e}")

@bot.callback_query_handler(func=lambda c: True)
def process_callback(c):
    cid = c.message.chat.id
    if cid not in user_data: 
        bot.answer_callback_query(c.id, "Eskirgan so'rov.")
        return

    # 1. Eski menyuni o'chiramiz (Til tanlash knopkasi yo'qoladi)
    try: bot.delete_message(cid, c.message.message_id)
    except: pass

    # 2. "Kuting" xabarini chiqaramiz
    msg = bot.send_message(cid, "⏳ Tahlil va Tarjima ketmoqda... (Kuting)")
    
    try:
        path = user_data[cid]["path"]
        name = user_data[cid]["name"]
        lang = c.data
        
        model = whisper.load_model("base")
        res = model.transcribe(path)
        
        data = []
        txt_out = f"TRANSKRIPSIYA: {name}\nSana: {datetime.now()}\n\n"
        
        for s in res['segments']:
            t = s['text'].strip()
            tr = None
            if lang != "original":
                try: tr = GoogleTranslator(source='auto', target=lang).translate(t)
                except: pass
            
            time_str = f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}]"
            txt_out += f"{time_str} {t}\n"
            if tr: txt_out += f"Tarjima: {tr}\n"
            txt_out += "\n"
            data.append({"start":s['start'], "text":t, "translated":tr})
            
        txt_out += "\n---\nBot by Shodlik"
        
        uname = c.from_user.username or c.from_user.first_name
        save_to_firestore(cid, uname, name, data)
        
        out_name = f"{name}_natija.txt"
        with open(out_name, "w", encoding="utf-8") as f: f.write(txt_out)
        
        # 3. Saytga Link yasaymiz
        link = f"{SITE_URL}/?uid={cid}"
        mark = types.InlineKeyboardMarkup()
        # MANA BU YERDA TUGMA QO'SHILDI
        mark.add(types.InlineKeyboardButton("🎵 Neon Pleyerda ochish", url=link))
        
        with open(out_name, "rb") as f:
            bot.send_document(cid, f, caption="✅ Tahlil yakunlandi!", reply_markup=mark)
            
        # 4. "Kuting" xabarini O'CHIRAMIZ (Chat toza bo'ladi)
        try: bot.delete_message(cid, msg.message_id)
        except: pass

        os.remove(path)
        os.remove(out_name)
        
    except Exception as e:
        bot.send_message(cid, f"Xato: {e}")
        if os.path.exists(path): os.remove(path)

if __name__ == "__main__":
    try: bot.infinity_polling()
    except: pass
