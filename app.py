import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
import base64

# --- 1. SOZLAMALAR ---
SITE_URL = "https://shodlik1transcript.streamlit.app"

try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    FB_API_KEY = st.secrets["FB_API_KEY"]
    PROJECT_ID = st.secrets["PROJECT_ID"]
except:
    st.error("❌ Secrets kalitlari topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke", layout="centered", page_icon="🎵")

# --- 2. CSS DIZAYN (NEON PLAYER UCHUN) ---
st.markdown("""
<style>
    .stApp { background-color: #000000; color: white; }
    h1, h2, h3 { color: white; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; text-align: center; }
    
    /* Neon Player Qutisi */
    .neon-box {
        background: #050505;
        border: 2px solid #00e5ff;
        box-shadow: 0 0 15px #00e5ff;
        border-radius: 20px;
        padding: 20px;
        margin-top: 20px;
        color: white;
    }
    
    .status-ok { border: 1px solid lime; color: lime; padding: 5px; text-align: center; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNKSIYA: NEON PLEYERNI CHIZISH ---
def render_neon_player(audio_bytes, transcript_data):
    # Audioni base64 qilish (HTML ichida o'qish uchun)
    audio_b64 = base64.b64encode(audio_bytes).decode()
    
    # HTML + JS Kod (Siz yoqtirgan Neon effekt)
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:10px;">🎵 NEON KARAOKE 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1); margin-bottom:20px;">
            <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:400px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #333;"></div>
    </div>

    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        // Matnlarni joylashtirish
        data.forEach((line, index) => {{
            const div = document.createElement('div');
            div.id = 'line-' + index;
            div.style.padding = '15px';
            div.style.marginBottom = '10px';
            div.style.transition = 'all 0.3s ease';
            div.style.cursor = 'pointer';
            div.style.borderBottom = '1px solid #222';
            
            let htmlContent = `<div style="font-size:20px; font-weight:bold; color:#555;">${{line.text}}</div>`;
            if (line.translated) {{
                htmlContent += `<div style="font-size:16px; color:#444; font-style:italic;">${{line.translated}}</div>`;
            }}
            div.innerHTML = htmlContent;
            
            // Bosganda o'sha joyga o'tish
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});

        // Vaqt bo'yicha yurish
        audio.ontimeupdate = () => {{
            let activeIdx = data.findIndex(item => audio.currentTime >= item.start && audio.currentTime < item.end); // aniqroq vaqt
            
            // Hamma qatorlarni o'chirish
            data.forEach((_, i) => {{
                const el = document.getElementById('line-' + i);
                if (el) {{
                    el.children[0].style.color = '#555'; // Asl matn xira
                    el.style.transform = 'scale(1)';
                    el.style.borderLeft = 'none';
                }}
            }});

            // Aktiv qatorni yoqish
            if (activeIdx !== -1) {{
                const activeEl = document.getElementById('line-' + activeIdx);
                if (activeEl) {{
                    activeEl.children[0].style.color = '#00e5ff'; // Neon rang
                    activeEl.children[0].style.textShadow = '0 0 15px #00e5ff';
                    activeEl.style.transform = 'scale(1.05)';
                    activeEl.style.borderLeft = '4px solid #00e5ff';
                    activeEl.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=550)


# --- 4. SAYT QISMI (FOYDALANUVCHI UCHUN) ---
user_id = st.query_params.get("uid", None)

if user_id:
    st.title("📂 SHAXSIY ARXIV")
    
    # 1. BAZADAN O'QISH
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
            st.success(f"Sizda {len(res)} ta saqlangan fayl bor.")
            
            for i, item in enumerate(res):
                doc = item['document']['fields']
                fname = doc.get('filename', {}).get('stringValue', 'Audio')
                json_str = doc.get('data', {}).get('stringValue')
                
                if json_str:
                    t_data = json.loads(json_str)
                    
                    # HAR BIR FAYL UCHUN ALOHIDA OYNA
                    with st.expander(f"🎵 {i+1}. {fname} (Ochish)"):
                        st.write("### 1-qadam: Matn tayyor ✅")
                        st.caption("Bot matnni tayyorlab qo'ygan. Uni quyida o'qishingiz mumkin.")
                        
                        # -----------------------------------------------
                        # ENG MUHIM JOYI: AUDIO YUKLASH VA PLEYER
                        # -----------------------------------------------
                        st.write("### 2-qadam: Audioni yuklang (Pleyer uchun)")
                        st.info("⚠️ Audio Telegramda qolgan. Neon effektini ko'rish uchun o'sha audioni shu yerga tashlang:")
                        
                        audio_file = st.file_uploader(f"MP3 faylni yuklang ({i})", type=['mp3', 'wav', 'ogg'], key=f"up_{i}")
                        
                        if audio_file:
                            # AGAR AUDIO YUKLANSA -> NEON PLAYER ISHLAYDI
                            render_neon_player(audio_file.getvalue(), t_data)
                        else:
                            # AGAR AUDIO YO'Q BO'LSA -> FAQAT MATN
                            st.text_area("Matn ko'rinishi:", value="\n".join([f"{x['text']} ({x['translated'] or ''})" for x in t_data]), height=200)

        else:
            st.warning("📭 Arxiv bo'sh. Botga kirib audio yuboring.")
            
    except Exception as e:
        st.error(f"Xatolik: {e}")

    # Sayt shu yerda tugaydi, Bot qismiga o'tmaydi
    st.stop()


# --- 5. BOT SERVER QISMI (ADMIN UCHUN) ---
st.title("🤖 Bot Server")
st.markdown('<div class="status-ok">✅ AKTIV</div>', unsafe_allow_html=True)

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

def save_to_firestore(uid, username, filename, transcript_data):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
        payload = {"fields": {"uid": {"stringValue": str(uid)}, "username": {"stringValue": str(username)}, "filename": {"stringValue": filename}, "data": {"stringValue": json.dumps(transcript_data)}, "created_at": {"stringValue": now}}}
        requests.post(url, json=payload)
    except: pass

@bot.message_handler(commands=['start'])
def start(m):
    link = f"{SITE_URL}/?uid={m.chat.id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📂 Arxiv va Pleyer", url=link))
    bot.reply_to(m, "Assalomu alaykum! Audio yuboring.", reply_markup=markup)

@bot.message_handler(content_types=['audio', 'voice'])
def audio_handler(m):
    try:
        if m.content_type=='audio': fid=m.audio.file_id; fname=m.audio.file_name
        else: fid=m.voice.file_id; fname="voice.ogg"
        
        file_info = bot.get_file(fid)
        downloaded = bot.download_file(file_info.file_path)
        path = f"u_{m.chat.id}.mp3"
        with open(path, "wb") as f: f.write(downloaded)
        
        user_data[m.chat.id] = {"path": path, "name": fname}
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🇺🇿 O'zbek", callback_data="uz"), types.InlineKeyboardButton("🇷🇺 Rus", callback_data="ru"), types.InlineKeyboardButton("📄 Original", callback_data="original"))
        bot.send_message(m.chat.id, "Tilni tanlang:", reply_markup=markup)
    except: pass

@bot.callback_query_handler(func=lambda c: True)
def inline(c):
    cid = c.message.chat.id
    if cid not in user_data: return
    try: bot.delete_message(cid, c.message.message_id)
    except: pass
    
    msg = bot.send_message(cid, "⏳ Tahlil ketmoqda...")
    
    try:
        path = user_data[cid]["path"]; name = user_data[cid]["name"]; lang = c.data
        model = whisper.load_model("base"); res = model.transcribe(path)
        
        data = []; txt_out = f"Fayl: {name}\n\n"
        for s in res['segments']:
            t = s['text'].strip(); tr = None
            if lang != "original":
                try: tr = GoogleTranslator(source='auto', target=lang).translate(t)
                except: pass
            txt_out += f"[{int(s['start'])}] {t}\n"
            data.append({"start":s['start'], "text":t, "translated":tr})
            
        save_to_firestore(cid, c.from_user.first_name, name, data)
        
        with open("natija.txt", "w", encoding="utf-8") as f: f.write(txt_out)
        
        link = f"{SITE_URL}/?uid={cid}"
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("🎵 Saytda Pleyerda Ko'rish", url=link))
        
        with open("natija.txt", "rb") as f:
            bot.send_document(cid, f, caption="✅ Tayyor! Pleyerda ko'rish uchun audioni saytga yuklashingiz kerak bo'ladi.", reply_markup=mark)
            
        bot.delete_message(cid, msg.message_id)
        os.remove(path); os.remove("natija.txt")
        
    except Exception as e: bot.send_message(cid, f"Xato: {e}")

if __name__ == "__main__":
    try: bot.infinity_polling()
    except: pass
                            
