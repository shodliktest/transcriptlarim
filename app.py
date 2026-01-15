import streamlit as st
import telebot
from telebot import types
import whisper
import os
import requests
import json
import base64
import threading
import pytz
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
SITE_URL = "https://shodlik1transcript.streamlit.app"
uz_tz = pytz.timezone('Asia/Tashkent')

# Papka yaratish (Audiolarni vaqtinchalik saqlash uchun)
if not os.path.exists("temp_audio"):
    os.makedirs("temp_audio")

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. CSS DIZAYN (QORA & NEON) ---
st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff; font-weight: bold; }
    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 20px rgba(0,229,255,0.3); border-radius: 20px; padding: 20px; margin-top: 20px; }
    [data-testid="stFileUploader"] section { background-color: #111; border: 1px dashed #00e5ff; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:15px;">🎵 AVTOMATIK PLEYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 5px #00e5ff); margin-bottom:15px;">
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
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #333'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:20px; font-weight:bold; color:#777;">${{line.time}} | ${{line.text}}</div>` + (line.translated ? `<div style="font-size:16px; color:#555;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ let el = document.getElementById('L-'+i); if(el){{ el.children[0].style.color='#777'; el.style.borderLeft='none'; }} }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff'; el.style.borderLeft='4px solid #00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}}); }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. ASOSIY INTERFEYS ---
# URL parametrlarini o'qiymiz
u_params = st.query_params
uid = u_params.get("uid")
auto_file = u_params.get("file")

if uid and auto_file:
    # --- AVTOMATIK REJIM ---
    st.title("🚀 Avtomatik Karaoke")
    file_path = f"temp_audio/{auto_file}"
    
    if os.path.exists(file_path):
        # Firebase'dan oxirgi tahlilni olish
        url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents:runQuery?key={FB_API_KEY}"
        query = {"structuredQuery": {"from": [{"collectionId": "transcriptions"}], "where": {"fieldFilter": {"field": {"fieldPath": "uid"}, "op": "EQUAL", "value": {"stringValue": str(uid)}}}, "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}], "limit": 1}}
        
        res = requests.post(url, json=query).json()
        if res and 'document' in res[0]:
            doc = res[0]['document']['fields']
            t_data = json.loads(doc['data']['stringValue'])
            
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
            
            render_neon_player(audio_bytes, t_data)
            st.success("Botdan kelgan audio yuklandi!")
        else:
            st.error("Tahlil ma'lumotlari topilmadi.")
    else:
        st.warning("Audio fayl serverda eskirgan yoki topilmadi. Iltimos, qayta yuklang.")
        st.stop()

else:
    # --- ODDIY REJIM (Saytning o'zi) ---
    st.title("🎧 KARAOKE & TRANSCRIPT")
    uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])
    lang_choice = st.selectbox("Tarjima tili", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

    if st.button("🚀 TAHLILNI BOSHLASH"):
        if uploaded_file:
            with st.spinner("⚡ Tahlil qilinmoqda..."):
                with open("temp.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
                model = whisper.load_model("base")
                result = model.transcribe("temp.mp3")
                
                player_data = []
                txt_full = f"Sana: {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n\n"
                
                for s in result['segments']:
                    start_fmt = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                    player_data.append({"start": s['start'], "end": s['end'], "time": start_fmt, "text": s['text'].strip(), "translated": None})
                    txt_full += f"[{start_fmt}] {s['text']}\n\n"
                
                render_neon_player(uploaded_file.getvalue(), player_data)
                st.download_button("📄 TXT Yuklab olish", txt_full, file_name="karaoke.txt")
                os.remove("temp.mp3")

# --- 5. TELEGRAM BOT (ORQA FONDA) ---
def background_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    
    @bot.message_handler(commands=['start'])
    def start(m):
        bot.reply_to(m, "Menga audio yuboring!")

    @bot.message_handler(content_types=['audio', 'voice'])
    def handle_audio(m):
        try:
            bot.reply_to(m, "⏳ Tahlil qilinmoqda...")
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name or "audio.mp3"
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            
            # Faylni maxsus papkaga saqlaymiz (Sayt o'qishi uchun)
            file_key = f"rec_{int(datetime.now().timestamp())}.mp3"
            save_path = f"temp_audio/{file_key}"
            with open(save_path, "wb") as f: f.write(down)
            
            model = whisper.load_model("base")
            res = model.transcribe(save_path)
            
            # Firebase'ga saqlash (ID va vaqt bilan)
            data = []
            for s in res['segments']:
                data.append({"start": s['start'], "end": s['end'], "time": f"{int(s['start']//60):02d}:{int(s['start']%60):02d}", "text": s['text'].strip()})
            
            url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
            payload = {"fields": {"uid": {"stringValue": str(m.chat.id)}, "filename": {"stringValue": fn}, "data": {"stringValue": json.dumps(data)}, "created_at": {"stringValue": str(datetime.now(uz_tz))}}}
            requests.post(url, json=payload)
            
            # Saytga avtomatik link
            auto_link = f"{SITE_URL}/?uid={m.chat.id}&file={file_key}"
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton("🎵 Neon Pleyerda ochish (Avtomatik)", url=auto_link))
            bot.send_message(m.chat.id, "✅ Tahlil tayyor! Saytda ko'rish uchun pastdagi tugmani bosing:", reply_markup=mark)
            
        except Exception as e: bot.send_message(m.chat.id, f"Xato: {e}")

    bot.infinity_polling()

if 'bot_run' not in st.session_state:
    st.session_state['bot_run'] = True
    threading.Thread(target=background_bot, daemon=True).start()
