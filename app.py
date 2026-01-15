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

# --- 2. DIZAYN (KUCHAYTIRILGAN NEON) ---
st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    /* Neon Selectbox (Til tanlash oynasi va matni) */
    div[data-baseweb="select"] > div {
        background-color: #000000 !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff;
        border-radius: 10px;
    }
    
    /* Tanlangan yozuv (Original, Uzbek va h.k) neon rangda */
    div[data-baseweb="select"] span {
        color: #00e5ff !important;
        text-shadow: 0 0 10px #00e5ff;
        font-weight: bold;
    }

    /* Ro'yxat ochilgandagi yozuvlar ham neon */
    div[role="listbox"] ul li {
        color: #00e5ff !important;
        text-shadow: 0 0 5px #00e5ff;
        background-color: #000 !important;
    }
    
    /* TXT Yuklab olish tugmasi (Neon dizayn) */
    div.stDownloadButton > button {
        background-color: #000 !important;
        color: #00e5ff !important;
        border: 2px solid #00e5ff !important;
        border-radius: 10px;
        padding: 10px;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 0 10px #00e5ff;
        transition: 0.3s;
        text-transform: uppercase;
    }
    div.stDownloadButton > button:hover {
        background-color: #00e5ff !important;
        color: #000 !important;
        box-shadow: 0 0 25px #00e5ff;
    }

    /* Boshlash tugmasi */
    div.stButton > button:first-child {
        background-color: #000; color: #00e5ff; border: 2px solid #00e5ff; 
        border-radius: 10px; padding: 10px; font-size: 18px; font-weight: bold; width: 100%; transition: 0.3s;
        box-shadow: 0 0 10px #00e5ff;
    }
    div.stButton > button:first-child:hover { background-color: #00e5ff; color: #000; box-shadow: 0 0 25px #00e5ff; }

    /* Neon Player va boshqalar */
    [data-testid="stFileUploader"] section { background-color: #111; border: 2px dashed #00e5ff; border-radius: 10px; }
    .tg-status { background-color: #001a00; border: 1px solid #00ff00; color: #00ff00; padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 20px; font-weight: bold; }
    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 20px rgba(0,229,255,0.3); border-radius: 20px; padding: 20px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER CHIZISH ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:15px;">🎵 NEON PLEYER 🎵</h3>
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
            div.id = 'L-'+i;
            div.style.padding='15px'; div.style.borderBottom='1px solid #333'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:20px; font-weight:bold; color:#777;">${{line.time}} | ${{line.text}}</div>` + (line.translated ? `<div style="font-size:16px; color:#555;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#777'; el.style.borderLeft='none'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.borderLeft='4px solid #00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. ASOSIY INTERFEYS ---
st.title("🎧 KARAOKE & TRANSCRIPT")

uid_from_url = st.query_params.get("uid", None)
if uid_from_url:
    st.markdown(f'<div class="tg-status">🟢 Siz Telegram orqali ulandingiz! (ID: {uid_from_url})</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])

# --- NEON MENYU (Til Tanlash) ---
st.markdown("### 🌐 Tarjima tilini tanlang:")
lang_options = ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"]
lang_choice = st.selectbox("", lang_options, index=3, label_visibility="collapsed")

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        temp_path = f"site_temp_{datetime.now().timestamp()}.mp3"
        try:
            with st.spinner("⚡ AI tahlil qilmoqda..."):
                with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
                model = whisper.load_model("base")
                result = model.transcribe(temp_path)
                
                txt_full = f"TRANSKRIPSIYA\nFayl: {uploaded_file.name}\nSana: {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n\n"
                player_data = []
                
                target_lang = {"🇺🇿 O'zbek": "uz", "🇷🇺 Rus": "ru", "🇬🇧 Ingliz": "en"}.get(lang_choice)

                for s in result['segments']:
                    start_fmt = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                    time_lip = f"[{start_fmt} - {int(s['end']//60):02d}:{int(s['end']%60):02d}]"
                    text = s['text'].strip()
                    trans = GoogleTranslator(source='auto', target=target_lang).translate(text) if target_lang else None
                    
                    player_data.append({"start": s['start'], "end": s['end'], "time": start_fmt, "text": text, "translated": trans})
                    txt_full += f"{time_lip} {text}\n" + (f"Tarjima: {trans}\n" if trans else "") + "\n"
                
                txt_full += f"\n---\n© Shodlik (Otavaliyev_M)\nO'zbekiston vaqti: {datetime.now(uz_tz).strftime('%H:%M:%S')}"
                
                render_neon_player(uploaded_file.getvalue(), player_data)
                
                # TXT Yuklab olish tugmasi (Endi bu ham neon dizaynda)
                st.download_button("📄 TXT Yuklab olish", txt_full, file_name=f"{uploaded_file.name}.txt")
                
                if uid_from_url:
                    bot_temp = telebot.TeleBot(BOT_TOKEN)
                    with open("res.txt", "w", encoding="utf-8") as f: f.write(txt_full)
                    with open("res.txt", "rb") as f: bot_temp.send_document(uid_from_url, f, caption="✅ Saytdan natija keldi!")
                    os.remove("res.txt")
        except Exception as e: st.error(f"Xato: {e}")
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path): os.remove(temp_path) 
    else:
        st.error("Audio yuklanmadi!")

# --- 5. ORQA FONDA ISHLAYDIGAN BOT ---
def background_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    
    @bot.message_handler(commands=['start'])
    def start_msg(m):
        menu = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        menu.add(types.KeyboardButton("🌐 Saytga kirish (Login)"), types.KeyboardButton("ℹ️ Yordam"))
        bot.send_message(m.chat.id, "👋 Assalomu alaykum! Audio yuboring.", reply_markup=menu)

    @bot.message_handler(func=lambda message: message.text == "🌐 Saytga kirish (Login)")
    def open_site(m):
        link = f"{SITE_URL}/?uid={m.chat.id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Saytni Ochish", url=link))
        bot.reply_to(m, "Shaxsiy havola:", reply_markup=markup)

    @bot.message_handler(content_types=['audio', 'voice'])
    def handle_docs(m):
        path = f"b_{m.chat.id}_{datetime.now().timestamp()}.mp3"
        try:
            bot.reply_to(m, "⏳ Tahlil qilinmoqda...")
            fid = m.audio.file_id if m.content_type=='audio' else m.voice.file_id
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            with open(path, "wb") as f: f.write(down)
            
            model = whisper.load_model("base"); res = model.transcribe(path)
            txt = f"TRANSKRIPSIYA\nSana: {datetime.now(uz_tz)}\n\n"
            for s in res['segments']:
                txt += f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {s['text']}\n"
            
            txt += "\n---\n© Shodlik"
            with open("res_bot.txt", "w", encoding="utf-8") as f: f.write(txt)
            with open("res_bot.txt", "rb") as f: bot.send_document(m.chat.id, f, caption="✅ Tayyor!")
            os.remove("res_bot.txt")
        except Exception as e: bot.send_message(m.chat.id, f"Xato: {e}")
        finally:
            if os.path.exists(path): os.remove(path) 

    bot.infinity_polling()

if 'bot_active' not in st.session_state:
    st.session_state['bot_active'] = True
    threading.Thread(target=background_bot, daemon=True).start()

st.markdown('<div style="position:fixed; bottom:0; right:0; padding:5px; color:lime; font-size:10px;">Bot: Online</div>', unsafe_allow_html=True)
