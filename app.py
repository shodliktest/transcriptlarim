import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import base64
import threading
import gc
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
SITE_URL = "https://shodlik1transcript.streamlit.app"

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
except:
    st.error("❌ Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. XOTIRANI TOZALASH ---
def clear_ram():
    gc.collect()

# --- 3. DIZAYN (QORA & NEON) ---
st.markdown("""
#00ff00
""", unsafe_allow_html=True)

# --- 4. NEON PLAYER FUNKSIYASI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff;">🎵 NEON PLEYER (BASE) 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 5px #00e5ff); margin-bottom:15px;">
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
            div.style.padding='12px'; div.style.borderBottom='1px solid #333'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:18px; font-weight:bold; color:#777;">${{line.time}} | ${{line.text}}</div>` + (line.translated ? `<div style="font-size:14px; color:#555;">${{line.translated}}</div>` : '');
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
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 10px #00e5ff';
                    el.style.borderLeft='3px solid #00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=550)

# --- 5. SAYT QISMI (WEB) ---
st.title("🎧 KARAOKE PRO")
uid_from_url = st.query_params.get("uid", None)

if uid_from_url:
    st.success(f"Telegram ulangan! (ID: {uid_from_url})")

uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav', 'ogg'])
lang_options = ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"]
lang_choice = st.selectbox("Tarjima tili", lang_options, index=3)

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        with st.spinner("⚡ Base Model ishlamoqda... (Iltimos kuting)"):
            with open("temp.mp3", "wb") as f: f.write(uploaded_file.getbuffer())
            
            # 1. MODELNI ISHLATISH
            model = whisper.load_model("base")
            result = model.transcribe("temp.mp3")
            
            # 2. XOTIRANI TOZALASH
            del model
            clear_ram()
            
            # 3. FORMATLASH VA YANGI IMZO QO'SHISH
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            txt_full = f"TRANSKRIPSIYA\nFayl: {uploaded_file.name}\n\n"
            
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
                
                player_data.append({"start": s['start'], "end": s['end'], "time": start_fmt, "text": text, "translated": trans})
                txt_full += f"{time_lip} {text}\n" + (f"Tarjima: {trans}\n" if trans else "") + "\n"
            
            # --- YANGI IMZO (WEB UCHUN) ---
            txt_full += f"\n\n---\nYaratuvchi: Shodlik (Otavaliyev_M)\nTelegram: @Transcript_Robot\nSana: {now_time}"
            
            render_neon_player(uploaded_file.getvalue(), player_data)
            st.download_button("📄 TXT Yuklab olish", txt_full, file_name="natija.txt")
            
            if uid_from_url:
                try:
                    bot_temp = telebot.TeleBot(BOT_TOKEN)
                    with open("temp_res.txt", "w", encoding="utf-8") as f: f.write(txt_full)
                    with open("temp_res.txt", "rb") as f:
                        bot_temp.send_document(uid_from_url, f, caption=f"✅ **Saytdan natija keldi!**\nFayl: {uploaded_file.name}")
                    os.remove("temp_res.txt")
                except: pass
            
            os.remove("temp.mp3")
    else:
        st.error("Audio yuklanmadi!")


# --- 6. TELEGRAM BOT (SERVER) ---
def background_bot():
    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=['start'])
    def start_handler(m):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton("🌐 Saytga kirish (Login)")
        btn2 = types.KeyboardButton("ℹ️ Yordam")
        markup.add(btn1, btn2)
        
        bot.send_message(m.chat.id, "👋 Assalomu alaykum! Audio yuboring yoki menyuni tanlang:", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text == "🌐 Saytga kirish (Login)")
    def login_btn(m):
        link = f"{SITE_URL}/?uid={m.chat.id}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🚀 Kabinetga kirish", url=link))
        bot.reply_to(m, "Shaxsiy kabinetingizga havola:", reply_markup=kb)

    @bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
    def help_btn(m):
        bot.reply_to(m, "Audio tashlang -> TXT olasiz.\nSaytga kiring -> Neon Player.")

    @bot.message_handler(content_types=['audio', 'voice'])
    def audio_handler(m):
        try:
            bot.reply_to(m, "⏳ Tahlil ketmoqda... (Base Model)")
            
            if m.content_type=='audio': fid=m.audio.file_id; fn=m.audio.file_name or "audio.mp3"
            else: fid=m.voice.file_id; fn="voice.ogg"
            
            f_info = bot.get_file(fid); down = bot.download_file(f_info.file_path)
            temp_name = f"b_{m.chat.id}.mp3"
            with open(temp_name, "wb") as f: f.write(down)
            
            # Model yuklash va tozalash
            model = whisper.load_model("base")
            res = model.transcribe(temp_name)
            del model
            clear_ram()

            # --- FORMATLASH VA YANGI IMZO ---
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            txt = f"TRANSKRIPSIYA\nFayl: {fn}\n\n"
            
            for s in res['segments']:
                start_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                end_f = f"{int(s['end']//60):02d}:{int(s['end']%60):02d}"
                txt += f"[{start_f} - {end_f}] {s['text']}\n"
            
            # --- IMZO QO'SHISH (BOT UCHUN) ---
            txt += f"\n\n---\nYaratuvchi: Shodlik (Otavaliyev_M)\nTelegram: @Transcript_Robot\nSana: {now_time}"
            
            link = f"{SITE_URL}/?uid={m.chat.id}"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🎵 Saytda Pleyer", url=link))
            
            with open("res.txt", "w", encoding="utf-8") as f: f.write(txt)
            with open("res.txt", "rb") as f: 
                bot.send_document(m.chat.id, f, caption="✅ Natija tayyor!", reply_markup=kb)
            
            os.remove(temp_name); os.remove("res.txt")
            
        except Exception as e:
            bot.send_message(m.chat.id, "⚠️ Server band. Birozdan keyin urinib ko'ring.")
            clear_ram()

    try: bot.infinity_polling()
    except: pass

if 'bot_active' not in st.session_state:
    st.session_state['bot_active'] = True
    t = threading.Thread(target=background_bot, daemon=True)
    t.start()

