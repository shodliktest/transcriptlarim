import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import base64
import threading
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
# ⚠️ DIQQAT: Saytingiz manzilini shu yerga to'g'ri yozing!
SITE_URL = "https://shodlik1transcript.streamlit.app"

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    # Firebase shart emas, lekin xato bermasligi uchun qoldiramiz
    FB_API_KEY = st.secrets.get("FB_API_KEY", "")
    PROJECT_ID = st.secrets.get("PROJECT_ID", "")
except:
    st.error("❌ Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. DIZAYN (QORA & NEON) ---
st.markdown("""
<style>
    /* Asosiy Fon */
    .stApp { background-color: #000000 !important; color: white !important; }
    
    /* Sarlavhalar */
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    /* Upload Box */
    [data-testid="stFileUploader"] section { background-color: #111; border: 2px dashed #00e5ff; border-radius: 10px; }
    [data-testid="stFileUploader"] span, div, small { color: white !important; }
    [data-testid="stFileUploader"] button { background-color: #00e5ff; color: black; font-weight: bold; border: none; }

    /* Boshlash tugmasi */
    div.stButton > button:first-child {
        background-color: #000; color: #00e5ff; border: 2px solid #00e5ff; 
        border-radius: 10px; padding: 10px; font-size: 18px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button:first-child:hover { background-color: #00e5ff; color: #000; box-shadow: 0 0 20px #00e5ff; }

    /* Telegram Statusi */
    .tg-status {
        background-color: #003300; border: 1px solid #00ff00; color: #00ff00;
        padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 20px; font-weight: bold;
    }
    
    /* Neon Player */
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

# Telegramdan kirganligini tekshirish
uid_from_url = st.query_params.get("uid", None)

if uid_from_url:
    st.markdown(f'<div class="tg-status">🟢 Siz Telegram orqali ulandingiz!<br>Natija avtomatik ravishda botga yuboriladi.</div>', unsafe_allow_html=True)
else:
    st.info("ℹ️ Saytga shunchaki kirdingiz. Botga ulanish uchun Telegramdagi /start buyrug'idan foydalaning.")

uploaded_file = st.file_uploader("MP3 fayl yuklang (Maks: 25MB)", type=['mp3', 'wav', 'ogg'])
lang_options = ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"]
lang_choice = st.selectbox("Tarjima tili", lang_options, index=3)

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        with st.spinner("⚡ Sun'iy intellekt ishlamoqda..."):
            with open("temp.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
            model = whisper.load_model("base")
            result = model.transcribe("temp.mp3")
            
            # --- TXT va FORMATLASH ---
            txt_full = f"TRANSKRIPSIYA\nFayl: {uploaded_file.name}\nSana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            player_data = []
            
            target_lang = None
            if "O'zbek" in lang_choice: target_lang = "uz"
            elif "Rus" in lang_choice: target_lang = "ru"
            elif "Ingliz" in lang_choice: target_lang = "en"

            for s in result['segments']:
                start_fmt = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                end_fmt = f"{int(s['end']//60):02d}:{int(s['end']%60):02d}"
                time_lip = f"[{start_fmt} - {end_fmt}]" 
                
                text = s['text'].strip()
                trans = None
                
                if target_lang:
                    try: trans = GoogleTranslator(source='auto', target=target_lang).translate(text)
                    except: pass
                
                player_data.append({
                    "start": s['start'], 
                    "end": s['end'], 
                    "time": start_fmt,
                    "text": text, 
                    "translated": trans
                })
                
                txt_full += f"{time_lip} {text}\n"
                if trans: txt_full += f"Tarjima: {trans}\n"
                txt_full += "\n"
            
            txt_full += "\n---\n© Yaratuvchi: Shodlik (Otavaliyev_M)\n🤖 Bot: @KaraokeProBot"
            
            # 1. Pleyerni chizish
            render_neon_player(uploaded_file.getvalue(), player_data)
            
            # 2. Yuklab olish tugmasi
            st.download_button("📄 TXT Yuklab olish", txt_full, file_name=f"{uploaded_file.name}.txt")
            
            # 3. Telegramga yuborish (Agar ID bo'lsa)
            if uid_from_url:
                try:
                    bot_temp = telebot.TeleBot(BOT_TOKEN)
                    with open("temp_res.txt", "w", encoding="utf-8") as f: f.write(txt_full)
                    with open("temp_res.txt", "rb") as f:
                        bot_temp.send_document(uid_from_url, f, caption=f"✅ **Saytdan natija keldi!**\nFayl: {uploaded_file.name}")
                    st.toast("Natija Telegramingizga yuborildi!", icon="🚀")
                    os.remove("temp_res.txt")
                except Exception as e:
                    print(f"Xato: {e}")
            
            os.remove("temp.mp3")
    else:
        st.error("Audio yuklanmadi!")

# --- 5. ORQA FONDA ISHLAYDIGAN BOT ---
def background_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    
    # ---------------------------------------------
    # YANGILIK: ASOSIY MENU TUGMALARI (REPLY KEYBOARD)
    # ---------------------------------------------
    @bot.message_handler(commands=['start'])
    def start_msg(m):
        # Pastdagi doimiy tugmalar
        menu = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton("🌐 Saytga kirish (Login)")
        btn2 = types.KeyboardButton("ℹ️ Yordam")
        menu.add(btn1, btn2)
        
        bot.send_message(m.chat.id, 
                         "👋 **Assalomu alaykum!**\n\n"
                         "Menga audio yuboring yoki pastdagi tugmalar orqali saytga kiring.", 
                         reply_markup=menu)

    # Tugmalar bosilganda ishlaydigan qism
    @bot.message_handler(func=lambda message: message.text == "🌐 Saytga kirish (Login)")
    def open_site_login(m):
        link = f"{SITE_URL}/?uid={m.chat.id}"
        
        # Linkni Inline Button qilib beramiz (chunki Reply tugmada URL ochilmaydi)
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(types.InlineKeyboardButton("🚀 Saytni Ochish", url=link))
        
        bot.reply_to(m, "Shaxsiy kabinetingizga kirish uchun bosing:", reply_markup=inline_markup)

    @bot.message_handler(func=lambda message: message.text == "ℹ️ Yordam")
    def help_msg(m):
        bot.reply_to(m, "1. Menga audio yuboring -> Men TXT qilib beraman.\n2. 'Saytga kirish' ni bosing -> Neon Playerda ko'rasiz.")

    # Audio qabul qilish
    @bot.message_handler(content_types=['audio', 'voice'])
    def handle_docs(m):
        try:
            bot.reply_to(m, "⏳ Tahlil qilinmoqda... (Biroz kuting)")
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name or "audio.mp3"
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            path = f"b_{m.chat.id}.mp3"; 
            with open(path, "wb") as f: f.write(down)
            
            model = whisper.load_model("base"); res = model.transcribe(path)
            
            txt = f"TRANSKRIPSIYA\nFayl: {fn}\nSana: {datetime.now()}\n\n"
            for s in res['segments']:
                start_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                end_f = f"{int(s['end']//60):02d}:{int(s['end']%60):02d}"
                txt += f"[{start_f} - {end_f}] {s['text']}\n"
            
            txt += "\n---\n© Shodlik (Otavaliyev_M)"
            
            # Saytga o'tish tugmasi
            link = f"{SITE_URL}/?uid={m.chat.id}"
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton("🎵 Pleyerda ochish (Sayt)", url=link))
            
            with open("res.txt", "w", encoding="utf-8") as f: f.write(txt)
            with open("res.txt", "rb") as f: 
                bot.send_document(m.chat.id, f, caption="✅ Marhamat, natija!", reply_markup=mark)
            
            os.remove(path); os.remove("res.txt")
        except Exception as e:
            bot.send_message(m.chat.id, f"Xato: {e}")

    try: bot.infinity_polling()
    except: pass

# Botni alohida oqimda yurgizish
if 'bot_active' not in st.session_state:
    st.session_state['bot_active'] = True
    t = threading.Thread(target=background_bot, daemon=True)
    t.start()

# Footer status
st.markdown('<div style="position:fixed; bottom:0; right:0; padding:5px; background:black; color:lime; font-size:10px;">Bot: Online</div>', unsafe_allow_html=True)
                
