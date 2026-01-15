import streamlit as st
import os, json, base64, pytz, time
from datetime import datetime
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR VA SECRETS ---
uz_tz = pytz.timezone('Asia/Tashkent')

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    st.error("❌ Secrets bo'limida 'GROQ_API_KEY' topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered")

# --- 2. KUCHAYTIRILGAN NEON DIZAYN ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    /* Neon Selectbox */
    div[data-baseweb="select"] > div {
        background-color: #000 !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 10px #00e5ff;
        border-radius: 10px;
    }
    div[data-baseweb="select"] span { color: #00e5ff !important; font-weight: bold; }
    
    /* BARCHA TUGMALAR (Boshlash va Yuklab olish) */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000 !important;
        color: #00e5ff !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff;
        border-radius: 12px;
        font-weight: bold;
        width: 100%;
        transition: 0.3s;
        text-transform: uppercase;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #00e5ff !important;
        color: #000 !important;
        box-shadow: 0 0 35px #00e5ff;
    }

    /* --- FAYL YUKLASH BO'LIMI (CUSTOM NEON BUTTON) --- */
    [data-testid="stFileUploader"] section { 
        background-color: #000 !important; 
        border: 2px dashed #00e5ff !important; 
        border-radius: 15px;
        padding: 30px;
        box-shadow: 0 0 10px rgba(0, 229, 255, 0.1);
    }
    
    /* Browse tugmasini butunlay neon qilish va matnini o'zgartirish */
    [data-testid="stFileUploader"] button {
         background-color: #000 !important;
         color: #00e5ff !important;
         border: 2px solid #00e5ff !important;
         box-shadow: 0 0 10px #00e5ff;
         border-radius: 8px;
         font-weight: bold;
         padding: 8px 20px;
    }
    
    /* Tugma matnini "fayl tanlash uchun bosing" ga o'zgartirish */
    [data-testid="stFileUploader"] button span::before {
        content: "fayl tanlash uchun bosing";
        visibility: visible;
    }
    [data-testid="stFileUploader"] button span {
        visibility: hidden;
        white-space: nowrap;
    }

    /* Yuklash oynasidagi boshqa matnlar */
    [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] small {
        color: #00e5ff !important;
        text-shadow: 0 0 5px #00e5ff;
    }
    
    /* Neon Player Box */
    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0,229,255,0.4); border-radius: 20px; padding: 25px; margin-top: 25px; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    transcript_json = json.dumps(transcript_data)
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; text-shadow: 0 0 10px #00e5ff;">🎵 NEON KARAOKE PLAYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 8px #00e5ff); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:15px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {transcript_json};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #222'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444;">${{line.text}}</div>` + 
                            (line.translated ? `<div style="font-size:17px; color:#333; margin-top:5px;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el) {{ el.children[0].style.color='#444'; el.style.borderLeft='none'; }}
            }});
            if(idx !== -1){{
                let el = document.getElementById('L-'+idx);
                if(el) {{ 
                    el.children[0].style.color='#00e5ff'; 
                    el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.borderLeft='5px solid #00e5ff';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=620)

# --- 4. ASOSIY LOGIKA ---
st.title("🎧 NEON TRANSCRIPT WEB")

# Fayl yuklovchi
up = st.file_uploader("", type=['mp3', 'wav'])

lang = st.selectbox("Tarjima tilini tanlang:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 TAHLILNI BOSHLASH") and up:
    path = f"tmp_{time.time()}.mp3"
    try:
        with st.spinner("⚡ AI tahlil qilmoqda..."):
            with open(path, "wb") as f: f.write(up.getbuffer())
            
            with open(path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(path, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )
            
            p_data = []
            txt_out = f"📄 TRANSKRIPSIYA: {up.name}\n📅 {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n---\n\n"
            t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)

            for s in transcription.segments:
                orig_text = s['text'].strip()
                tr = GoogleTranslator(source='auto', target=t_code).translate(orig_text) if t_code else None
                p_data.append({"start": s['start'], "end": s['end'], "text": orig_text, "translated": tr})
                
                tm = f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}]"
                txt_out += f"{tm} {orig_text}\n" + (f"Tarjima: {tr}\n" if tr else "") + "\n"

            txt_out += f"\n---\n👤 Shodlik (Otavaliyev_M) | ⏰ {datetime.now(uz_tz).strftime('%H:%M:%S')} (UZB)"
            
            render_neon_player(up.getvalue(), p_data)
            st.download_button("📄 TXT FAYLNI YUKLAB OLISH", txt_out, file_name=f"{up.name}.txt")

    except Exception as e:
        st.error(f"Xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

st.caption("© Shodlik (Otavaliyev_M)")
