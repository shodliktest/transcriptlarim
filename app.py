import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import base64
import threading
import pytz
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
SITE_URL = "https://shodlik1transcript.streamlit.app"
uz_tz = pytz.timezone('Asia/Tashkent')

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    FB_API_KEY = st.secrets.get("FB_API_KEY", "")
    PROJECT_ID = st.secrets.get("PROJECT_ID", "")
except:
    st.error("❌ Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. ASOSIY NEON DIZAYN (KUCHAYTIRILGAN) ---
st.markdown("""
<style>
    /* Umumiy fon */
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    /* SELECTBOX (MENYU) VA UNING ICHIDAGI MATNLARNI NEON QILISH */
    div[data-baseweb="select"] > div {
        background-color: #000000 !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff;
        border-radius: 10px;
    }
    
    /* Tanlangan matn rangi */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
        color: #00e5ff !important;
        text-shadow: 0 0 8px #00e5ff;
        font-weight: bold;
        font-size: 18px;
    }

    /* Ro'yxat ochilgandagi neon ko'rinishi */
    ul[role="listbox"] {
        background-color: #000000 !important;
        border: 1px solid #00e5ff !important;
    }
    ul[role="listbox"] li {
        color: #00e5ff !important;
        text-shadow: 0 0 5px #00e5ff;
        transition: 0.3s;
    }
    ul[role="listbox"] li:hover {
        background-color: rgba(0, 229, 255, 0.2) !important;
    }

    /* Fayl yuklash qismi */
    [data-testid="stFileUploader"] section { 
        background-color: #0a0a0a; 
        border: 2px dashed #00e5ff !important; 
        border-radius: 12px; 
    }
    
    /* Boshlash tugmasi */
    div.stButton > button:first-child {
        background-color: #000; color: #00e5ff; border: 2px solid #00e5ff; 
        border-radius: 12px; padding: 12px; font-size: 20px; font-weight: bold; width: 100%; 
        box-shadow: 0 0 15px #00e5ff; transition: 0.3s;
    }
    div.stButton > button:first-child:hover { background-color: #00e5ff; color: #000; box-shadow: 0 0 30px #00e5ff; }

    /* Player oynasi */
    .neon-box { 
        background: #000; border: 2px solid #00e5ff; 
        box-shadow: 0 0 25px rgba(0,229,255,0.4); border-radius: 20px; padding: 25px; 
    }
</style>
""", unsafe_allow_html=True)

# --- 3. PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:15px;">🎵 NEON KARAOKE 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 8px #00e5ff); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #222'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444;">${{line.time}} | ${{line.text}}</div>` + 
                            (line.translated ? `<div style="font-size:16px; color:#333;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#444'; el.style.borderLeft='none'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.borderLeft='5px solid #00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=650)

# --- 4. ASOSIY SAHIFA ---
st.title("🎧 NEON TRANSCRIPT PRO")

uid_url = st.query_params.get("uid", None)
if uid_url:
    st.success(f"✅ Telegram orqali ulandingiz (ID: {uid_url})")

uploaded_file = st.file_uploader("Faylni shu yerga tashlang", type=['mp3', 'wav', 'ogg'])

# --- NEON TIL TANLASH QISMI ---
st.markdown("<h3 style='text-align:left; font-size:18px;'>🌐 Tilni tanlang:</h3>", unsafe_allow_html=True)
options = ["📄 Original", "🇺🇿 Uzbekcha", "🇷🇺 Ruscha", "🇬🇧 Inglizcha"]
choice = st.selectbox("", options, index=0, label_visibility="collapsed")

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        t_path = f"tmp_{datetime.now().timestamp()}.mp3"
        try:
            with st.spinner("⚡ Whisper AI ishlamoqda..."):
                with open(t_path, "wb") as f: f.write(uploaded_file.getbuffer())
                model = whisper.load_model("base")
                res = model.transcribe(t_path)
                
                t_lang = {"🇺🇿 Uzbekcha": "uz", "🇷🇺 Ruscha": "ru", "🇬🇧 Inglizcha": "en"}.get(choice)
                p_data = []
                txt = f"TRANSKRIPSIYA - {uploaded_file.name}\nSana: {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n\n"

                for s in res['segments']:
                    st_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                    orig = s['text'].strip()
                    tr = GoogleTranslator(source='auto', target=t_lang).translate(orig) if t_lang else None
                    
                    p_data.append({"start": s['start'], "end": s['end'], "time": st_f, "text": orig, "translated": tr})
                    txt += f"[{st_f}] {orig}\n" + (f"Tarjima: {tr}\n" if tr else "") + "\n"
                
                txt += f"\n---\n© Shodlik | O'zbekiston: {datetime.now(uz_tz).strftime('%H:%M:%S')}"
                
                render_neon_player(uploaded_file.getvalue(), p_data)
                st.download_button("📄 TXT Faylni yuklash", txt, file_name=f"{uploaded_file.name}.txt")
                
                if uid_url:
                    b_temp = telebot.TeleBot(BOT_TOKEN)
                    with open("res.txt", "w", encoding="utf-8") as f: f.write(txt)
                    with open("res.txt", "rb") as f: b_temp.send_document(uid_url, f, caption="✅ Natija tayyor!")
                    os.remove("res.txt")
        except Exception as e: st.error(f"Xato: {e}")
        finally:
            if os.path.exists(t_path): os.remove(t_path) # AUTO CLEAR
    else: st.error("Fayl yo'q!")

# --- 5. BOT (THREAD) ---
def run_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    @bot.message_handler(commands=['start'])
    def s(m):
        m_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        m_markup.add("🌐 Saytga kirish")
        bot.send_message(m.chat.id, "Audio yuboring yoki saytga o'ting!", reply_markup=m_markup)

    @bot.message_handler(func=lambda msg: msg.text == "🌐 Saytga kirish")
    def o(m):
        link = f"{SITE_URL}/?uid={m.chat.id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Saytni ochish", url=link))
        bot.reply_to(m, "Sizning shaxsiy havolangiz:", reply_markup=markup)

    @bot.message_handler(content_types=['audio', 'voice'])
    def h(m):
        p = f"b_{m.chat.id}.mp3"
        try:
            bot.reply_to(m, "⏳ Tahlil ketmoqda...")
            f_id = m.audio.file_id if m.content_type=='audio' else m.voice.file_id
            f_info = bot.get_file(f_id); d_file = bot.download_file(f_info.file_path)
            with open(p, "wb") as f: f.write(d_file)
            
            mdl = whisper.load_model("base"); r = mdl.transcribe(p)
            res_txt = f"TRANSKRIPSIYA\n\n"
            for s in r['segments']:
                res_txt += f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {s['text']}\n"
            
            with open("b_res.txt", "w", encoding="utf-8") as f: f.write(res_txt)
            with open("b_res.txt", "rb") as f: bot.send_document(m.chat.id, f, caption="✅ Tayyor!")
        finally:
            if os.path.exists(p): os.remove(p)
            if os.path.exists("b_res.txt"): os.remove("b_res.txt")

    bot.infinity_polling()

if 'bot_on' not in st.session_state:
    st.session_state['bot_on'] = True
    threading.Thread(target=run_bot, daemon=True).start()

st.markdown('<div style="position:fixed; bottom:0; right:0; color:#00e5ff; font-size:10px;">● Server Live</div>', unsafe_allow_html=True)
