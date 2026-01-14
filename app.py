import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- CUSTOM CSS (Rasmdagi dizaynni yaratish uchun) ---
st.markdown("""
<style>
    /* Umumiy fon */
    .stApp {
        background: linear-gradient(180deg, #3a1c71 0%, #20124d 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sarlavha dizayni */
    .main-title {
        color: #fce4ec;
        font-size: 50px;
        font-weight: 800;
        text-align: center;
        margin-bottom: 5px;
        line-height: 1;
    }
    .sub-title {
        color: #d1c4e9;
        text-align: center;
        font-size: 18px;
        margin-bottom: 30px;
    }

    /* Asosiy konteyner (Frosted Glass effect) */
    .main-card {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(15px);
        border-radius: 30px;
        padding: 40px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }

    /* Audio yuklash qismi (Dashed box) */
    [data-testid="stFileUploader"] {
        border: 2px dashed rgba(255, 255, 255, 0.2);
        border-radius: 20px;
        padding: 20px;
        background: transparent;
    }
    [data-testid="stFileUploader"] section {
        background-color: transparent !important;
    }
    .upload-label {
        color: white;
        font-size: 18px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Selectbox (Dropdown) dizayni */
    label[data-testid="stWidgetLabel"] p {
        color: #d1c4e9 !important;
        font-size: 16px !important;
        font-weight: 400 !important;
    }
    div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    div[data-baseweb="select"] div {
        color: white !important;
    }

    /* Tugma dizayni (Pink-Purple Gradient) */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #ec407a 0%, #7e57c2 100%);
        color: white;
        border: none;
        padding: 15px 30px;
        border-radius: 20px;
        font-size: 20px;
        font-weight: 600;
        transition: 0.3s;
        margin-top: 20px;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(236, 64, 122, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. MUALLIFLIK IMZOSI ---
SIGNATURE_TEXT = """
------------------------------
Shodlik (Otavaliyev_M) Tomondan yaratilgan dasturdan foydalanildi,
Telegram: @Otavaliyev_M  Instagram: @SHodlik1221
"""

# --- 3. WHISPER MODELINI YUKLASH ---
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

# --- 4. TARJIMA FUNKSIYASI ---
def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return ""

# --- 5. AUDIO BASE64 ---
def get_audio_base64(binary_data):
    b64 = base64.b64encode(binary_data).decode()
    return f"data:audio/mp3;base64,{b64}"

# --- 6. KARAOKE RENDER ---
def render_karaoke(audio_url, transcript_json):
    html_code = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        .karaoke-container {{ 
            background: rgba(0, 0, 0, 0.2); 
            font-family: 'Inter', sans-serif; 
            color: #ffffff; 
            padding: 20px; 
            border-radius: 15px;
            margin-top: 20px;
        }}
        audio {{ width: 100%; margin-bottom: 20px; filter: invert(1) hue-rotate(180deg); }}
        #transcript-box {{ height: 300px; overflow-y: auto; padding: 20px; line-height: 1.6; font-size: 18px; scroll-behavior: smooth; }}
        .segment {{ margin-bottom: 15px; color: #aab; transition: 0.3s; cursor: pointer; }}
        .segment.active {{ color: #ff4081; font-weight: 600; transform: scale(1.02); }}
        .translated-text {{ display: block; font-size: 14px; color: #889; margin-top: 4px; }}
    </style>
    <div class="karaoke-container">
        <audio id="audio-player" controls src="{audio_url}"></audio>
        <div id="transcript-box"></div>
    </div>
    <script>
        const audio = document.getElementById('audio-player');
        const box = document.getElementById('transcript-box');
        const data = {transcript_json};

        data.forEach((item, index) => {{
            const div = document.createElement('div');
            div.className = 'segment'; div.id = 'seg-' + index;
            let content = '<span>' + item.text + '</span>';
            if(item.translated) {{
                content += '<span class="translated-text">' + item.translated + '</span>';
            }}
            div.innerHTML = content;
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            const time = audio.currentTime;
            let activeIdx = data.findIndex(i => time >= i.start && time <= i.end);
            if (activeIdx !== -1) {{
                document.querySelectorAll('.segment').forEach(s => s.classList.remove('active'));
                const activeEl = document.getElementById('seg-'+activeIdx);
                activeEl.classList.add('active');
                activeEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }};
    </script>
    """
    components.html(html_code, height=450)

# --- 7. INTERFEYS ---

# Sarlavha qismi
st.markdown('<div class="main-title">Audio Karaoke</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Audio transkriptsiya va sinxronlashgan karaoke tajribasi</div>', unsafe_allow_html=True)

# Asosiy dizayn kartasi
with st.container():
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    
    st.markdown('<div class="upload-label">📤 Audio fayl yuklash</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Audio fayl tanlang (MP3, WAV, M4A, FLAC)", type=["mp3", "wav", "m4a", "flac"], label_visibility="collapsed")

    st.markdown('<div class="upload-label" style="margin-top:20px;">文<sub>A</sub> Tarjima tili</div>', unsafe_allow_html=True)
    lang_options = {
        "Tanlanmagan (Faqat asl tilda)": "original",
        "O'zbek": "uz",
        "Rus": "ru",
        "Ingliz": "en"
    }
    target_lang_label = st.selectbox("Tarjima tili", list(lang_options.keys()), label_visibility="collapsed")
    target_lang_code = lang_options[target_lang_label]

    if st.button("✨ Boshlash"):
        if uploaded_file:
            with open("temp_audio.mp3", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            with st.spinner("Tahlil qilinmoqda..."):
                result = model.transcribe("temp_audio.mp3")
                
                transcript_data = []
                final_file_text = "--- TRANSKRIPSIYA HISOBOTI ---\n\n"
                
                for segment in result['segments']:
                    original = segment['text'].strip()
                    translated = translate_text(original, target_lang_code) if target_lang_code != "original" else None
                    
                    transcript_data.append({
                        "start": segment['start'], "end": segment['end'], 
                        "text": original, "translated": translated
                    })
                    
                    final_file_text += f"[{segment['start']:.2f}s] {original}\n"
                    if translated: final_file_text += f"TARJIMA: {translated}\n\n"

                final_file_text += SIGNATURE_TEXT
                
                audio_b64 = get_audio_base64(uploaded_file.getvalue())
                render_karaoke(audio_b64, json.dumps(transcript_data))

                st.download_button(
                    label="Natijani .txt faylda yuklab olish",
                    data=final_file_text,
                    file_name="shodlik_result.txt",
                    mime="text/plain"
                )
        else:
            st.error("Iltimos, avval audio fayl yuklang!")

    st.markdown('</div>', unsafe_allow_html=True)

# Tozalash
if os.path.exists("temp_audio.mp3"):
    try: os.remove("temp_audio.mp3")
    except: pass
