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
    # Firebase hozircha shart emas, lekin kodda xato bermasligi uchun qoldiramiz
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. CSS DIZAYN (MUAMMOLAR HAL QILINGAN) ---
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
        text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff;
        font-weight: bold;
    }

    /* 2. UPLOAD KNOPKASI (RANGI TO'G'IRLANDI) */
    [data-testid="stFileUploader"] section {
        background-color: #111111 !important; /* To'q kulrang fon */
        border: 2px dashed #00e5ff !important;
        padding: 20px;
        border-radius: 10px;
    }
    /* Upload ichidagi yozuvlar */
    [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] small {
        color: #ffffff !important; /* Oq yozuv */
    }
    /* "Browse files" tugmasi */
    [data-testid="stFileUploader"] button {
        background-color: #00e5ff !important;
        color: #000000 !important;
        font-weight: bold;
        border: none;
    }

    /* 3. BOSHLASH KNOPKASI */
    div.stButton > button:first-child {
        background-color: #000000 !important;
        color: #00e5ff !important;
        border: 2px solid #00e5ff !important;
        border-radius: 10px;
        padding: 10px 20px;
        font-size: 18px !important;
        font-weight: bold;
        width: 100%;
        transition: 0.3s;
    }
    div.stButton > button:first-child:hover {
        background-color: #00e5ff !important;
        color: #000 !important;
        box-shadow: 0 0 20px #00e5ff;
    }

    /* Neon Player Box */
    .neon-box {
        background: #050505;
        border: 2px solid #00e5ff;
        box-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
        border-radius: 20px;
        padding: 20px;
        margin-top: 20px;
        color: white;
    }
    
    /* Ogohlantirish qutisi */
    .warning-box {
        background: #331100; color: #ffaa00; padding: 10px; border-radius: 5px; 
        border: 1px solid #ffaa00; font-size: 14px; text-align: center; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:20px;">🎵 NEON PLEYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 5px #00e5ff); margin-bottom:20px;">
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
            div.style.padding='15px'; div.style.marginBottom='10px'; div.style.transition='0.3s'; div.style.cursor='pointer'; div.style.borderBottom='1px solid #333';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#777;">${{line.text}}</div>` + (line.translated ? `<div style="font-size:16px; color:#555;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#777'; el.style.transform='scale(1)'; el.style.border='none'; el.style.background='transparent'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.transform='scale(1.05)'; el.style.borderLeft='4px solid #00e5ff'; el.style.background='rgba(0, 229, 255, 0.1)';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. SAYT INTERFEYSI (ASOSIY QISM) ---
st.title("🎧 KARAOKE PRO")
st.markdown('<div class="warning-box">⚠️ Eslatma: Audio hajmi 25MB dan oshmasligi tavsiya etiladi.</div>', unsafe_allow_html=True)

# URL dan foydalanuvchi ID sini olish (Botdan kirganini bilish uchun)
uid_from_url = st.query_params.get("uid", None)

# Fayl yuklash
uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])

# Til tanlash (DEFAULT: ORIGINAL)
# Ro'yxat tartibi: 0:Uz, 1:Ru, 2:En, 3:Original
lang_options = ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"]
lang_choice = st.selectbox("Tarjima tili", lang_options, index=3) # index=3 bu "Original"

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        with st.spinner("⚡ Sun'iy intellekt ishlamoqda..."):
            # Vaqtinchalik saqlash
            with open("temp_site.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
            
            # Whisper Tahlili
            model = whisper.load_model("base")
            result = model.transcribe("temp_site.mp3")
            
            # Ma'lumotlarni yig'ish
            t_data = []
            
            # TXT fayl yaratish (Vaqt va Imzo bilan)
            txt_content = f"TRANSKRIPSIYA HISOBOTI\n"
            txt_content += f"Fayl: {uploaded_file.name}\n"
            txt_content += f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            
            target_lang_code = None
            if lang_choice == "🇺🇿 O'zbek": target_lang_code = "uz"
            elif lang_choice == "🇷🇺 Rus": target_lang_code = "ru"
            elif lang_choice == "🇬🇧 Ingliz": target_lang_code = "en"
            
            for s in result['segments']:
                orig = s['text'].strip()
                trans = None
                
                if target_lang_code:
                    try: trans = GoogleTranslator(source='auto', target=target_lang_code).translate(orig)
                    except: pass
                
                # Formatlash
                time_str = f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}]"
                
                t_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
                
                # TXT ga qo'shish
                txt_content += f"{time_str} {orig}\n"
                if trans:
                    txt_content += f"Tarjima: {trans}\n"
                txt_content += "\n"
            
            # IMZO QO'SHISH
            txt_content += "\n---\n"
            txt_content += "© Yaratuvchi: Shodlik (Otavaliyev_M)\n"
            txt_content += "🤖 Telegram Bot: @KaraokeProBot"

            # 1. NEON PLAYERNI CHIZISH
            render_neon_player(uploaded_file.getvalue(), t_data)
            
            # 2. TXT YUKLASH TUGMASI (SAYT UCHUN)
            st.download_button(
                label="📄 Natijani yuklab olish (TXT)",
                data=txt_content,
                file_name=f"{uploaded_file.name}_natija.txt",
                mime="text/plain"
            )

            # 3. TELEGRAMGA AVTOMATIK YUBORISH (Agar botdan kirgan bo'lsa)
            if uid_from_url:
                try:
                    bot_temp = telebot.TeleBot(BOT_TOKEN)
                    # Fayl yaratish
                    with open("temp_res.txt", "w", encoding="utf-8") as f: f.write(txt_content)
                    
                    with open("temp_res.txt", "rb") as f:
                        bot_temp.send_document(
                            uid_from_url, 
                            f, 
                            caption=f"✅ **Saytdan natija keldi!**\n\nFayl: {uploaded_file.name}\nSiz saytda tahlil qilgan faylingiz.",
                            parse_mode="Markdown"
                        )
                    st.toast("✅ Natija Telegramingizga ham yuborildi!", icon="telegram")
                    os.remove("temp_res.txt")
                except Exception as e:
                    print(f"Telegramga yuborishda xato: {e}")

            # Tozalash
            os.remove("temp_site.mp3")
    else:
        st.error("⚠️ Iltimos, avval audio fayl yuklang!")


# --- 5. TELEGRAM BOT (ORQA FONDA) ---
def run_bot():
    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=['start'])
    def start(m):
        # Saytga ID bilan link beramiz (Shunda sayt kim kirganini taniydi)
        personal_link = f"{SITE_URL}/?uid={m.chat.id}"
        
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("🌐 Saytda Karaoke & Tahlil", url=personal_link))
        
        bot.reply_to(m, 
                     "👋 **Assalomu alaykum!**\n\n"
                     "Eng sifatli Neon Karaoke va Tahlil uchun saytga kiring.\n"
                     "Saytda tahlil qilsangiz, natija shu yerga (Telegramga) avtomatik keladi! 👇", 
                     reply_markup=mark)

    # Botga to'g'ridan-to'g'ri tashlaganda
    @bot.message_handler(content_types=['audio', 'voice'])
    def audio(m):
        try:
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name or "audio.mp3"
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            path = f"bot_{m.chat.id}.mp3"; 
            with open(path, "wb") as f: f.write(down)
            
            model = whisper.load_model("base"); res = model.transcribe(path)
            
            # TXT Formatlash (Imzo bilan)
            txt = f"TRANSKRIPSIYA (BOT)\nFayl: {fn}\nSana: {datetime.now()}\n\n"
            data = []
            for s in res['segments']:
                txt += f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {s['text']}\n"
                data.append({"start":s['start'], "text":s['text']})
            
            txt += "\n---\n© Yaratuvchi: Shodlik (Otavaliyev_M)"
            
            with open("bot_res.txt", "w", encoding="utf-8") as f: f.write(txt)
            
            personal_link = f"{SITE_URL}/?uid={m.chat.id}"
            mark = types.InlineKeyboardMarkup()
            mark.add(types.InlineKeyboardButton("🎵 Saytda Pleyerni Ochish", url=personal_link))
            
            with open("bot_res.txt", "rb") as f:
                bot.send_document(m.chat.id, f, caption="✅ Matn tayyor! Pleyer uchun saytga o'ting.", reply_markup=mark)
            
            os.remove(path); os.remove("bot_res.txt")
        except Exception as e:
            bot.send_message(m.chat.id, f"Xato: {e}")

    try: bot.infinity_polling()
    except: pass

if 'bot_started' not in st.session_state:
    st.session_state['bot_started'] = True
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
# Yashirin footer
st.markdown('<div style="position:fixed; bottom:0; right:0; font-size:10px; color:#333;">Bot Active</div>', unsafe_allow_html=True)
            
