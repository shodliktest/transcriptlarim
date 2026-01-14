import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- CUSTOM CSS (Tashqi dizayn: Rasmdagidek shaffof binafsha) ---
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #3a1c71 0%, #20124d 100%);
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        color: #ffffff;
        font-size: 50px;
        font-weight: 800;
        text-align: center;
        margin-bottom: 5px;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
    }
    .sub-title {
        color: #e0d7f7;
        text-align: center;
        font-size: 18px;
        margin-bottom: 30px;
    }
    /* Shaffof karta dizayni */
    .glass-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(15px);
        border-radius: 30px;
        padding: 40px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
    }
    /* Matn ranglari yaxshi ajralib turishi uchun */
    label[data-testid="stWidgetLabel"] p {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 17px !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    /* Yuklash oynasi dizayni */
    [data-testid="stFileUploader"] {
        border: 2px dashed rgba(255, 255, 255, 0.3);
        border-radius: 20px;
        background: rgba(0, 0, 0, 0.1);
    }
    /* Tugma: Pink-Purple Gradient */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #ec407a 0%, #7e57c2 100%);
        color: white;
        border: none;
        padding: 15px 30px;
        border-radius: 20px;
        font-size: 20px;
        font-weight: 700;
        transition: 0.3s;
        margin-top: 20px;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 20px rgba(236, 64, 122, 0.6);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. MUALLIFLIK IMZOSI ---
SIGNATURE_TEXT = """
------------------------------
Shodlik (Otavaliyev_M) Tomondan yaratilgan dasturdan foydalanildi,
Telegram: @Otavaliyev_M  Instagram: @SHodlik1221
"""

# --- 3. WHISPER VA TARJIMA ---
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

# --- 4. KARAOKE RENDER (Avvalgi qora fondagi yonuvchi text effekti) ---
def render_karaoke_classic(audio_url, transcript_json):
    # CSS ichidagi { } qavslar f-string bilan adashmasligi uchun {{ }} qilingan
    html_code = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        .karaoke-wrapper {{ 
            background-color: #0e1117; 
            font-family: 'Inter', sans-serif; 
            padding: 25px; 
            border-radius: 20px;
            box-shadow: inset 0 0 15px rgba(0,0,0,0.5);
        }}
        audio {{ 
            width: 100%; 
            margin-bottom: 25px; 
            filter: invert(100%) hue-rotate(180deg) brightness(1.5); 
        }}
        #transcript-box {{ 
            height: 380px; 
            overflow-y: auto; 
            padding: 20px; 
            background: #161b22; 
            border-radius: 12px; 
            line-height: 1.8; 
            font-size: 19px; 
            scroll-behavior: smooth; 
        }}
        .segment {{ 
            margin-bottom: 20px; 
            color: #5f6c7b; 
            transition: all 0.3s ease; 
            cursor: pointer; 
            padding-left: 10px;
        }}
        /* Neon effektli yonuvchi text */
        .segment.active {{ 
            color: #00e5ff !important; 
            font-weight: 600; 
            transform: translateX(10px); 
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.6), 0 0 20px rgba(0, 229, 255, 0.3); 
        }}
        .translated-text {{ 
            display: block; 
            font-size: 15px; 
            color: #8b949e; 
            margin-top: 5px; 
            font-style: italic; 
        }}
        #transcript-box::-webkit-scrollbar {{ width: 6px; }}
        #transcript-box::-webkit-scrollbar-thumb {{ background: #2d3748; border-radius: 10px; }}
    </style>

    <div class="karaoke-wrapper">
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

        let currentIndex = -1;
        audio.ontimeupdate = () => {{
            const time = audio.currentTime;
            let activeIdx = data.findIndex(i => time >= i.start && time <= i.end);
            if (activeIdx !== -1 && activeIdx !== currentIndex) {{
                if (currentIndex !== -1) document.getElementById('seg-'+currentIndex).classList.remove('active');
                const activeEl = document.getElementById('seg-'+activeIdx);
                activeEl.classList.add('active');
                activeEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                currentIndex = activeIdx;
            }}
        }};
    </script>
    """
    components.html(html_code, height=580)

# --- 5. INTERFEYS ---
st.markdown('<div class="main-title">Audio Karaoke</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Audio transkriptsiya va sinxronlashgan karaoke tajribasi</div>', unsafe_allow_html=True)

# Shaffof Glass Card boshlanishi
st.markdown('<div class="glass-card">', unsafe_allow_html=True)

# Fayl yuklash
st.markdown('<div>📤 Audio fayl yuklash</div>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Faylni tanlang", type=["mp3", "wav", "m4a", "flac"], label_visibility="collapsed")

# Tarjima tili
st.markdown('<div style="margin-top:20px;">文<sub>A</sub> Tarjima tili</div>', unsafe_allow_html=True)
lang_options = {
    "Tanlanmagan (Faqat asl tilda)": "original",
    "O'zbek": "uz",
    "Rus": "ru",
    "Ingliz": "en"
}
target_lang_label = st.selectbox("Tanlang", list(lang_options.keys()), label_visibility="collapsed")
target_lang_code = lang_options[target_lang_label]

if st.button("✨ Boshlash"):
    if uploaded_file:
        # Faylni saqlash
        with open("temp_audio.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("Sun'iy intellekt matnga o'girmoqda..."):
            # Whisper transkripsiya
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
            
            st.success("Tahlil yakunlandi!")
            
            # Karaoke pleyerni ko'rsatish
            audio_url = get_audio_base64(uploaded_file.getvalue())
            render_karaoke_classic(audio_url, json.dumps(transcript_data))

            # TXT yuklab olish
            st.download_button(
                label="📄 Natijani (.txt) yuklab olish",
                data=final_file_text,
                file_name="shodlik_karaoke.txt",
                mime="text/plain"
            )
    else:
        st.error("Iltimos, avval audio faylni yuklang!")

st.markdown('</div>', unsafe_allow_html=True) # Glass card tugashi

# Tozalash
if os.path.exists("temp_audio.mp3"):
    try: os.remove("temp_audio.mp3")
    except: pass
