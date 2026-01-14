import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #4c1d95 0%, #6d28d9 50%, #8b5cf6 100%);
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        color: #ffffff;
        font-size: 55px;
        font-weight: 900;
        text-align: center;
        text-shadow: 2px 2px 10px rgba(0, 0, 0, 0.3);
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(20px);
        border-radius: 35px;
        padding: 30px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
    }
    label p {
        color: #ffffff !important;
        font-size: 18px !important;
        font-weight: 700 !important;
    }
    /* Selectbox ichidagi tanlangan matnni qora qilish */
    div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.9) !important;
        border-radius: 15px !important;
    }
    div[data-baseweb="select"] * {
        color: #000000 !important;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #f472b6 0%, #a78bfa 100%) !important;
        color: white !important;
        border-radius: 20px !important;
        font-size: 22px !important;
        font-weight: 800 !important;
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

# --- 3. KARAOKE RENDER (TO'G'RILANGAN QAVSLAR BILAN) ---
def render_karaoke_neon(audio_url, transcript_json):
    # Diqqat: f-string ichida CSS/JS jingalak qavslari {{ }} ko'rinishida bo'lishi shart
    html_code = f"""
    <style>
        .karaoke-black-box {{ 
            background-color: #000000; 
            font-family: 'Segoe UI', sans-serif; 
            padding: 30px; 
            border-radius: 25px;
            border: 2px solid #333;
            margin-top: 30px;
        }}
        audio {{ 
            width: 100%; 
            filter: invert(100%) hue-rotate(180deg) brightness(1.5); 
            margin-bottom: 25px;
        }}
        #transcript-box {{ 
            height: 450px; 
            overflow-y: auto; 
            padding: 20px; 
            scroll-behavior: smooth; 
        }}
        .word-segment {{ 
            display: flex;
            flex-direction: column;
            margin-bottom: 25px;
            padding: 10px;
            cursor: pointer;
            transition: 0.3s;
        }}
        .original-txt {{
            font-size: 24px;
            color: #555;
            transition: 0.3s;
        }}
        .translated-sub {{ 
            font-size: 16px; 
            color: #777; 
            margin-top: 5px;
            font-style: italic;
        }}
        .word-segment.active .original-txt {{ 
            color: #00e5ff !important; 
            text-shadow: 0 0 15px #00e5ff; 
            font-weight: bold;
        }}
        .word-segment.active .translated-sub {{ 
            color: #ccc;
        }}
        #transcript-box::-webkit-scrollbar {{ width: 5px; }}
        #transcript-box::-webkit-scrollbar-thumb {{ background: #222; }}
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
            div.innerHTML = `<span class="original-txt">${{item.text}}</span>` + 
                            (item.translated ? `<span class="translated-sub">${{item.translated}}</span>` : "");
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        let lastIdx = -1;
        audio.ontimeupdate = () => {{
            const cur = audio.currentTime;
            let idx = data.findIndex(i => cur >= i.start && cur <= i.end);
            if (idx !== -1 && idx !== lastIdx) {{
                if (lastIdx !== -1) {{
                    const prev = document.getElementById('seg-'+lastIdx);
                    if(prev) prev.classList.remove('active');
                }}
                const el = document.getElementById('seg-'+idx);
                if(el) {{
                    el.classList.add('active');
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
                lastIdx = idx;
            }}
        }};
    </script>
    """
    components.html(html_code, height=650)

# --- 4. ASOSIY INTERFEYS ---
st.markdown('<div class="main-title">Audio Karaoke</div>', unsafe_allow_html=True)

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Audio fayl yuklash", type=["mp3", "wav", "m4a", "flac"])

lang_options = {"Tanlanmagan": "original", "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"}
target_lang_label = st.selectbox("Tarjima tili", list(lang_options.keys()))
target_lang_code = lang_options[target_lang_label]

if st.button("✨ Boshlash"):
    if uploaded_file:
        with open("temp.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("AI tahlil qilmoqda..."):
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
        st.error("Iltimos, fayl yuklang!")
st.markdown('</div>', unsafe_allow_html=True)

# Mualliflik imzosi
st.markdown(f"<div style='color: white; text-align: center; margin-top: 20px;'>Shodlik (Otavaliyev_M)</div>", unsafe_allow_html=True)
