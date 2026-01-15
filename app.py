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

# Kalitlarni olish
try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    # Firebase kalitlari bot orqasidan ma'lumot yig'ish uchun qolaversin
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke", layout="centered", page_icon="🎵")

# --- 2. DIZAYN (NEON PLAYER) ---
st.markdown("""
<style>
    /* Umumiy fon */
    .stApp { background-color: #050505; color: white; }
    
    /* Neon Sarlavhalar */
    h1, h2 { 
        text-align: center; 
        color: #fff; 
        text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff, 0 0 40px #00e5ff;
    }
    
    /* Fayl yuklash joyi */
    .stFileUploader {
        border: 1px dashed #00e5ff;
        border-radius: 10px;
        padding: 10px;
    }

    /* Neon Box (Player) */
    .neon-box {
        background: #000;
        border: 2px solid #00e5ff;
        box-shadow: 0 0 20px rgba(0, 229, 255, 0.4);
        border-radius: 20px;
        padding: 20px;
        margin-top: 20px;
        color: white;
    }
    
    /* Bot statusi (kichkina yozuv) */
    .bot-status {
        position: fixed; bottom: 10px; right: 10px;
        color: lime; font-size: 12px; background: rgba(0,0,0,0.5); padding: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:15px;">🎵 NEON KARAOKE 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1); margin-bottom:20px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:400px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i;
            div.style.padding='15px'; div.style.marginBottom='10px'; div.style.transition='0.3s'; div.style.cursor='pointer'; div.style.borderBottom='1px solid #222';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#666;">${{line.text}}</div>` + (line.translated ? `<div style="font-size:16px; color:#444;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#666'; el.style.transform='scale(1)'; el.style.borderLeft='none'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.transform='scale(1.05)'; el.style.borderLeft='4px solid #00e5ff';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. SAYT INTERFEYSI (ASOSIY QISM) ---
st.title("🎧 AUDIO TRANSCRIPT PRO")
st.write("Audioni yuklang va Neon Karaoke effektidan zavqlaning!")

# Fayl yuklash
uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])

# Til tanlash
lang_options = {"🇺🇿 O'zbek": "uz", "🇷🇺 Rus": "ru", "🇬🇧 Ingliz": "en", "📄 Original": "original"}
lang_choice = st.selectbox("Tarjima tili", list(lang_options.keys()))

if st.button("🚀 TAHLIL QILISH VA PLEYERNI YOQISH"):
    if uploaded_file:
        with st.spinner("Sun'iy intellekt ishlamoqda..."):
            # Whisper ishlashi
            with open("temp_site.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
            model = whisper.load_model("base")
            result = model.transcribe("temp_site.mp3")
            
            # Formatlash
            t_data = []
            txt_down = f"Fayl: {uploaded_file.name}\n\n"
            target_lang = lang_options[lang_choice]
            
            for s in result['segments']:
                orig = s['text'].strip()
                trans = None
                if target_lang != "original":
                    try: trans = GoogleTranslator(source='auto', target=target_lang).translate(orig)
                    except: pass
                
                t_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
                txt_down += f"[{int(s['start'])}] {orig}\n" + (f"Tarjima: {trans}\n" if trans else "") + "\n"
            
            # 1. NEON PLAYERNI CHIZISH
            render_neon_player(uploaded_file.getvalue(), t_data)
            
            # 2. TXT YUKLASH TUGMASI
            st.download_button("📄 Matnni yuklab olish (TXT)", txt_down, file_name="transcript.txt")
            
            # Tozalash
            os.remove("temp_site.mp3")
    else:
        st.warning("Iltimos, avval audio yuklang!")


# --- 5. TELEGRAM BOT (ORQA FONDA ISHLAYDI) ---
# Bot funksiyasini alohida yozamiz
def run_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    
    # Bazaga yozish (Faqat bot uchun)
    def save_firebase(uid, uname, fname, data):
        try:
            url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
            payload = {"fields": {"uid": {"stringValue": str(uid)}, "username": {"stringValue": str(uname)}, "filename": {"stringValue": fname}, "data": {"stringValue": json.dumps(data)}, "created_at": {"stringValue": str(datetime.now())}}}
            requests.post(url, json=payload)
        except: pass

    @bot.message_handler(commands=['start'])
    def start(m):
        # Bot to'g'ridan-to'g'ri Saytga havola beradi
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("🌐 Saytga kirish & Player", url=SITE_URL))
        bot.reply_to(m, "Assalomu alaykum! \n\nMen audioni tahlil qilib beraman.\nLekin eng zo'r effekt saytda bo'ladi:", reply_markup=mark)

    @bot.message_handler(content_types=['audio', 'voice'])
    def audio(m):
        try:
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            path = f"bot_{m.chat.id}.mp3"; 
            with open(path, "wb") as f: f.write(down)
            
            # Oddiy Whisper (Bot uchun tezkor)
            model = whisper.load_model("base")
            res = model.transcribe(path)
            
            txt = f"Fayl: {fn}\n\n"
            data = []
            for s in res['segments']:
                txt += f"[{int(s['start'])}] {s['text']}\n"
                data.append({"start":s['start'], "text":s['text']})
            
            # Bazaga tashlab qo'yamiz (Arxiv uchun)
            save_firebase(m.chat.id, m.from_user.first_name, fn, data)
            
            # TXT yuborish
            with open("bot_res.txt", "w", encoding="utf-8") as f: f.write(txt)
            
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton("🎵 Neon Playerda ochish (Sayt)", url=SITE_URL))
            
            with open("bot_res.txt", "rb") as f:
                bot.send_document(m.chat.id, f, caption="✅ Matn tayyor!\n\nAudioni Neon Playerda ko'rish uchun saytga kiring va faylni u yerga ham yuklang.", reply_markup=mark)
            
            os.remove(path); os.remove("bot_res.txt")
        except Exception as e:
            bot.send_message(m.chat.id, f"Xato: {e}")

    # Botni cheksiz aylantirish
    try:
        bot.infinity_polling()
    except:
        pass

# --- 6. BOTNI ALOHIDA OQIMDA (THREAD) YURGIZISH ---
# Bu juda muhim: Streamlit qotib qolmasligi uchun botni boshqa "xona"da ishlatamiz.
if 'bot_started' not in st.session_state:
    st.session_state['bot_started'] = True
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
st.markdown('<div class="bot-status">● Bot: Online</div>', unsafe_allow_html=True)
