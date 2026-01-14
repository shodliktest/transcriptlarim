import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- CUSTOM CSS (Tashqi interfeysni rasmdagi holatga keltirish) ---
st.markdown("""
<style>
    /* Umumiy fon */
    .stApp {
        background: linear-gradient(135deg, #2e1065 0%, #4c1d95 50%, #701a75 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sarlavha dizayni (Rasmdagi "Audio Karaoke") */
    .header-container {
        text-align: center;
        padding: 40px 0 20px 0;
    }
    .main-title {
        color: #ffffff;
        font-size: 55px;
        font-weight: 900;
        margin-bottom: 0px;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
    }
    .sub-title {
        color: #ddd6fe;
        font-size: 18px;
        font-weight: 300;
        letter-spacing: 1px;
    }

    /* Shaffof Glass Card (Konteyner) */
    .glass-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 35px;
        padding: 30px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        margin-top: 20px;
    }

    /* MATN RANGI: Vidjetlar tepasidagi matnlarni tiniq qilish */
    label p {
        color: #ffffff !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
        margin-bottom: 10px;
    }

    /* Fayl yuklash oynasini (Dashed box) rasmdagi holatga keltirish */
    [data-testid="stFileUploader"] {
        background: rgba(0, 0, 0, 0.15);
        border: 2px dashed rgba(255, 255, 255, 0.2) !important;
        border-radius: 20px !important;
        padding: 10px;
    }
    [data-testid="stFileUploader"] section {
        background: transparent !important;
    }
    [data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
    }

    /* Selectbox (Tarjima tili) dizayni */
    div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 15px !important;
    }
    div[data-baseweb="select"] div {
        color: white !important;
        font-size: 16px;
    }

    /* Boshlash tugmasi (Pink-Purple Gradient) */
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%) !important;
        color: white !important;
        border: none !important;
        padding: 15px 30px !important;
        border-radius: 20px !important;
        font-size: 22px !important;
        font-weight: 700 !important;
        transition: 0.4s all !important;
        margin-top: 25px;
        box-shadow: 0 4px 15px rgba(236, 72, 153, 0.3) !important;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 8px 25px rgba(236, 72, 153, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. MODEL VA TARJIMA ---
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except: return ""

def get_audio_base64(binary_data):
    b64 = base64.b64encode(binary_data).decode()
    return f"data:audio/mp3;base64,{b64}"

# --- 3. KARAOKE RENDER (Qora fon va neon text) ---
def render_karaoke_neon(audio_url, transcript_json):
    html_code = f"""
    <style>
        .karaoke-black-box {{ 
            background-color: #000000; 
            font-family: 'Segoe UI', sans-serif; 
            padding: 30px; 
            border-radius: 25px;
            border: 1px solid #333;
            margin-top: 30px;
        }}
        audio {{ 
            width: 100%; 
            filter: invert(100%) hue-rotate(180deg) brightness(1.5); 
            margin-bottom: 25px;
        }}
        #transcript-box {{ 
            height: 400px; 
            overflow-y: auto; 
            padding: 20px; 
            line-height: 1.8; 
            font-size: 22px; 
            scroll-behavior: smooth; 
        }}
        .word-segment {{ 
            color: #444; 
            transition: all 0.3s ease; 
            cursor: pointer; 
            display: block;
            margin-bottom: 15px;
        }}
        /* NEON YONUVCHI EFFEKT */
        .word-segment.active {{ 
            color: #00e5ff !important; 
            text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; 
            transform: scale(1.05);
            font-weight: bold;
        }}
        .translated-sub {{ 
            font-size: 16px; 
            color: #666; 
            font-style: italic; 
            display: block;
        }}
        #transcript-box::-webkit-scrollbar {{ width: 5px; }}
        #transcript-box::-webkit-scrollbar-thumb {{ background: #222; border-radius: 10px; }}
    </style>

    <div class="karaoke-black-box">
        <audio id="audio-player" controls src="{audio_url}"></audio>
        <div id="transcript-box"></div>
    </div>

    <script>
        const audio = document.getElementById('audio-player');
        const box = document.getElementById('transcript-box');
        const data = {transcript_json};

        data.forEach((item, index) => {{
            const div = document.createElement('div');
            div.className = 'word-segment'; div.id = 'seg-' + index;
            let html = '<span>' + item.text + '</span>';
            if(item.translated) {{
                html += '<span class="translated-sub">' + item.translated + '</span>';
            }}
            div.innerHTML = html;
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        let lastIdx = -1;
        audio.ontimeupdate = () => {{
            const cur = audio.currentTime;
            let idx = data.findIndex(i => cur >= i.start && cur <= i.end);
            if (idx !== -1 && idx !== lastIdx) {{
                if (lastIdx !== -1) document.getElementById('seg-'+lastIdx).classList.remove('active');
                const el = document.getElementById('seg-'+idx);
                el.classList.add('active');
                el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                lastIdx = idx;
            }}
        }};
    </script>
    """
    components.html(html_code, height=600)

# --- 4. ASOSIY INTERFEYS ---

# Header qismi
st.markdown("""
<div class="header-container">
    <div class="main-title">Audio Karaoke</div>
    <div class="sub-title">Audio transkriptsiya va sinxronlashgan karaoke tajribasi</div>
</div>
""", unsafe_allow_html=True)

# Shaffof Glass Card boshlanishi
st.markdown('<div class="glass-card">', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Audio fayl yuklash", type=["mp3", "wav", "m4a", "flac"])

lang_options = {
    "Tanlanmagan (Faqat asl tilda)": "original",
    "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"
}
target_lang_label = st.selectbox("Tarjima tili", list(lang_options.keys()))
target_lang_code = lang_options[target_lang_label]

if st.button("✨ Boshlash"):
    if uploaded_file:
        with open("temp.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("Tahlil qilinmoqda..."):
            result = model.transcribe("temp.mp3")
            transcript_data = []
            for s in result['segments']:
                orig = s['text'].strip()
                trans = translate_text(orig, target_lang_code) if target_lang_code != "original" else None
                transcript_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
            
            audio_url = get_audio_base64(uploaded_file.getvalue())
            render_karaoke_neon(audio_url, json.dumps(transcript_data))
            
            st.success("Tahlil yakunlandi!")
    else:
        st.error("Iltimos, avval audio fayl yuklang!")

st.markdown('</div>', unsafe_allow_html=True) # Karta tugashi

# Mualliflik imzosi
st.markdown(f"<div style='color: #8b5cf6; text-align: center; margin-top: 30px; font-size: 14px;'>{os.linesep.join(os.linesep.join(os.linesep.join('Shodlik (Otavaliyev_M)'.split()).split()).split())}</div>", unsafe_allow_html=True)
