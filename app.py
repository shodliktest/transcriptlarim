import streamlit as st
import telebot
from telebot import types
import whisper
import os
import requests
import json
import base64
import threading
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
SITE_URL = "https://shodlik1transcript.streamlit.app"

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. KUCHAYTIRILGAN QORA & NEON DIZAYN (CSS) ---
st.markdown("""
<style>
    /* 1. ASOSIY FON - QOP-QORA */
    .stApp {
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    
    /* Neon Sarlavhalar */
    h1, h2, h3 { 
        text-align: center; 
        color: #fff; 
        text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff, 0 0 40px #00e5ff;
        font-weight: bold;
    }
    
    /* 2. UPLOAD KNOPKASI (Fayl yuklash joyi) */
    [data-testid="stFileUploader"] {
        background-color: #000000 !important; /* Qora fon */
        border: 2px dashed #00e5ff !important; /* Neon chiziq */
        border-radius: 15px;
        padding: 20px;
        color: #00e5ff !important;
    }
    /* Upload ichidagi kichik tugma va yozuvlar */
    [data-testid="stFileUploader"] button, 
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] div {
         color: #ffffff !important; /* Oq yozuv */
         border-color: #00e5ff !important;
    }

    /* 3. BOSHLASH KNOPKASI (st.button) - Qora va Neon */
    div.stButton > button:first-child {
        background-color: #000000 !important; /* Qora fon */
        color: #00e5ff !important; /* Neon yozuv */
        border: 3px solid #00e5ff !important; /* Qalin neon hoshiya */
        border-radius: 12px;
        padding: 12px 30px;
        font-size: 20px !important;
        font-weight: bold;
        transition: all 0.3s ease-in-out;
        box-shadow: 0 0 10px #00e5ff;
        width: 100%; /* To'liq eniga */
    }
    /* Knopka ustiga borganda (Hover effect) */
    div.stButton > button:first-child:hover {
        background-color: #00e5ff !important; /* Neon fon */
        color: #000000 !important; /* Qora yozuv */
        box-shadow: 0 0 30px #00e5ff, 0 0 60px #00e5ff; /* Kuchli nur */
        border-color: #ffffff !important;
        transform: scale(1.02);
    }

    /* Selectbox (Til tanlash) foni ham qora */
    div[data-baseweb="select"] > div {
        background-color: #050505 !important; color: white !important; border: 1px solid #00e5ff !important;
    }

    /* Neon Box (Player oynasi) */
    .neon-box {
        background: #000000; /* Qora */
        border: 3px solid #00e5ff;
        box-shadow: 0 0 30px rgba(0, 229, 255, 0.5);
        border-radius: 25px;
        padding: 25px;
        margin-top: 30px;
        color: white;
    }
    
    /* Bot statusi */
    .bot-status {
        position: fixed; bottom: 10px; right: 10px;
        color: #00e5ff; font-size: 12px; background: #000; 
        border: 1px solid #00e5ff; padding: 5px 10px; border-radius: 10px;
        box-shadow: 0 0 5px #00e5ff;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:20px; text-shadow: 0 0 15px #00e5ff;">🎵 NEON PLEYER AKTIV 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 5px #00e5ff); margin-bottom:25px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:15px; border-top:2px solid #00e5ff;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i;
            div.style.padding='18px'; div.style.marginBottom='12px'; div.style.transition='0.3s'; div.style.cursor='pointer'; div.style.borderBottom='1px solid #333'; div.style.borderRadius='10px';
            div.innerHTML = `<div style="font-size:24px; font-weight:bold; color:#777;">${{line.text}}</div>` + (line.translated ? `<div style="font-size:18px; color:#555; margin-top:5px;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#777'; el.style.transform='scale(1)'; el.style.border='none'; el.style.borderBottom='1px solid #333'; el.style.background='transparent'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 20px #00e5ff';
                    el.style.transform='scale(1.08)'; 
                    el.style.border='2px solid #00e5ff';
                    el.style.background='rgba(0, 229, 255, 0.1)';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=650)

# --- 4. SAYT INTERFEYSI ---
st.title("🎧 KARAOKE PRO")
st.markdown("<h3>Audioni yuklang va Neon effektidan zavqlaning!</h3>", unsafe_allow_html=True)

# Fayl yuklash
uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])

# Til tanlash
lang_options = {"🇺🇿 O'zbek": "uz", "🇷🇺 Rus": "ru", "🇬🇧 Ingliz": "en", "📄 Original": "original"}
lang_choice = st.selectbox("Tarjima tili", list(lang_options.keys()))

st.write("") # Bo'sh joy
# Boshlash tugmasi
if st.button("🚀 BOSHLASH (TAHLIL & PLEYER)"):
    if uploaded_file:
        with st.spinner("⚡ Sun'iy intellekt ishlamoqda... (Kuting)"):
            with open("temp_site.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
            model = whisper.load_model("base")
            result = model.transcribe("temp_site.mp3")
            
            t_data = []
            target_lang = lang_options[lang_choice]
            
            for s in result['segments']:
                orig = s['text'].strip(); trans = None
                if target_lang != "original":
                    try: trans = GoogleTranslator(source='auto', target=target_lang).translate(orig)
                    except: pass
                t_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
            
            render_neon_player(uploaded_file.getvalue(), t_data)
            os.remove("temp_site.mp3")
    else:
        st.error("⚠️ Iltimos, avval audio fayl yuklang!")

# --- 5. TELEGRAM BOT (ORQA FONDA) ---
def run_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    
    def save_firebase(uid, uname, fname, data):
        try:
            url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
            payload = {"fields": {"uid": {"stringValue": str(uid)}, "username": {"stringValue": str(uname)}, "filename": {"stringValue": fname}, "data": {"stringValue": json.dumps(data)}, "created_at": {"stringValue": str(datetime.now())}}}
            requests.post(url, json=payload)
        except: pass

    @bot.message_handler(commands=['start'])
    def start(m):
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("🌐 Saytda Neon Pleyer", url=SITE_URL))
        bot.reply_to(m, "👋 Assalomu alaykum!\nEng zo'r karaoke effekti uchun saytga kiring:", reply_markup=mark)

    @bot.message_handler(content_types=['audio', 'voice'])
    def audio(m):
        try:
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            path = f"bot_{m.chat.id}.mp3"; 
            with open(path, "wb") as f: f.write(down)
            model = whisper.load_model("base"); res = model.transcribe(path)
            
            txt = f"Fayl: {fn}\n\n"
            data = []
            for s in res['segments']:
                txt += f"[{int(s['start'])}] {s['text']}\n"
                data.append({"start":s['start'], "text":s['text']})
            
            save_firebase(m.chat.id, m.from_user.first_name, fn, data)
            with open("bot_res.txt", "w", encoding="utf-8") as f: f.write(txt)
            
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton("🎵 Saytda Pleyerni Ochish", url=SITE_URL))
            
            with open("bot_res.txt", "rb") as f:
                bot.send_document(m.chat.id, f, caption="✅ Matn tayyor! Pleyer uchun saytga o'ting.", reply_markup=mark)
            os.remove(path); os.remove("bot_res.txt")
        except Exception as e: bot.send_message(m.chat.id, f"Xato: {e}")

    try: bot.infinity_polling()
    except: pass

if 'bot_started' not in st.session_state:
    st.session_state['bot_started'] = True
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
st.markdown('<div class="bot-status">● Bot: Online</div>', unsafe_allow_html=True)
        
