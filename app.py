import streamlit as st
import whisper
import os
import json
import base64
import pytz
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR ---
uz_tz = pytz.timezone('Asia/Tashkent')

# 'base' model jumlalarni nuqtadan aniqroq ajratadi
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

model = load_whisper_model()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", page_icon="🎵")

# --- 2. DIZAYN ( FAQAT NEON VA QORA ) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    [data-testid="stFileUploader"] section {
        background-color: #000 !important;
        border: 2px dashed #00e5ff !important;
        border-radius: 15px;
    }
    [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] small {
        color: #00e5ff !important;
        text-shadow: 0 0 5px #00e5ff;
    }

    div[data-baseweb="select"] > div {
        background-color: #000000 !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff;
    }
    div[data-baseweb="select"] span {
        color: #00e5ff !important;
        font-weight: bold;
    }

    div.stButton > button, div.stDownloadButton > button {
        background-color: #000 !important;
        color: #00e5ff !important;
        border: 2px solid #00e5ff !important;
        border-radius: 12px;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 0 15px #00e5ff;
        text-transform: uppercase;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #00e5ff !important;
        color: #000 !important;
        box-shadow: 0 0 35px #00e5ff;
    }

    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0,229,255,0.4); border-radius: 20px; padding: 25px; margin-top: 25px; }
    .stProgress > div > div > div { background-color: #00e5ff !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER (TIME-LIPS OLIB TASHLANGAN) ---
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
            // TIME LIPS BU YERDAN OLIB TASHLANDI
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444;">${{line.text}}</div>` + 
                            (line.translated ? `<div style="font-size:17px; color:#555;">${{line.translated}}</div>` : '');
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
    st.components.v1.html(html, height=620)

# --- 4. ASOSIY QISM ---
st.title("🎧 NEON TRANSCRIPT WEB")

uploaded_file = st.file_uploader("MP3 fayl yuklang", type=['mp3', 'wav'])
lang_choice = st.selectbox("Tarjima tili:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        temp_path = f"t_{time.time()}.mp3"
        try:
            status = st.empty()
            bar = st.progress(0)
            
            status.markdown("⚡ **AI tahlil qilmoqda (Base Model)...**")
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            bar.progress(30)
            # Tahlil jarayoni
            result = model.transcribe(temp_path)
            bar.progress(70)
            
            status.markdown("🌐 **Matnlar tayyorlanmoqda...**")
            p_data = []
            txt_full = f"📄 TRANSKRIPSIYA: {uploaded_file.name}\n📅 Sana: {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n\n"
            target_lang = {"🇺🇿 O'zbek": "uz", "🇷🇺 Rus": "ru", "🇬🇧 Ingliz": "en"}.get(lang_choice)

            for s in result['segments']:
                text = s['text'].strip()
                # Nuqtadan keyin yangi qatorga o'tish Whisper'ning 'base' modelida yaxshi ishlaydi
                trans = GoogleTranslator(source='auto', target=target_lang).translate(text) if target_lang else None
                
                p_data.append({"start": s['start'], "end": s['end'], "text": text, "translated": trans})
                
                # TXT fayl uchun vaqtlar saqlanadi
                start_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                txt_full += f"[{start_f}] {text}\n" + (f"Tarjima: {trans}\n" if trans else "") + "\n"
            
            txt_full += f"\n---\n👤 Shodlik (Otavaliyev_M) | ⏰ {datetime.now(uz_tz).strftime('%H:%M:%S')}"
            
            bar.progress(100)
            status.success("✅ Tahlil yakunlandi!")
            
            render_neon_player(uploaded_file.getvalue(), p_data)
            st.download_button("📄 TXT Yuklab olish", txt_full, file_name=f"{uploaded_file.name}.txt")
            
        except Exception as e:
            st.error(f"Xato: {e}")
        finally:
            # AUTO CLEAR
            if os.path.exists(temp_path): os.remove(temp_path)
    else:
        st.error("Iltimos, fayl yuklang!")

st.caption("© Shodlik (Otavaliyev_M)")
