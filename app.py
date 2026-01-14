import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
import time

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Shodlik Transcribe", layout="centered")

# --- 2. MUALLIFLIK IMZOSI (Signature) ---
SIGNATURE_TEXT = """
------------------------------
Shodlik (Otavaliyev_M) Tomondan yaratilgan dasturdan foydalanildi,
Telegram: @Otavaliyev_M  Instagram: @SHodlik1221
"""

# --- 3. WHISPER MODELINI YUKLASH (Keshlanadi) ---
@st.cache_resource
def load_model():
    # 'base' model tez ishlaydi, 'medium' yoki 'large' aniqroq lekin sekinroq
    return whisper.load_model("base")

model = load_model()

# --- 4. AUDIO FAYLNI BASE64 GA O'TKAZISH ---
def get_audio_base64(binary_data):
    b64 = base64.b64encode(binary_data).decode()
    return f"data:audio/mp3;base64,{b64}"

# --- 5. INTERAKTIV KARAOKE HTML/JS/CSS KOMPONENTI ---
def render_karaoke(audio_url, transcript_json):
    html_code = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        
        .main-container {{
            background-color: #0e1117;
            font-family: 'Inter', sans-serif;
            color: #ffffff;
            padding: 20px;
            border-radius: 15px;
        }}

        audio {{
            width: 100%;
            margin-bottom: 20px;
            filter: invert(100%) hue-rotate(180deg) brightness(1.5); /* Dark mode audio player */
        }}

        #transcript-box {{
            height: 350px;
            overflow-y: auto;
            padding: 20px;
            background: #161b22;
            border-radius: 12px;
            line-height: 1.8;
            font-size: 19px;
            scroll-behavior: smooth;
        }}

        .word {{
            color: #5f6c7b;
            transition: all 0.25s ease;
            display: inline-block;
            margin-right: 5px;
            cursor: pointer;
        }}

        .word.active {{
            color: #00e5ff;
            font-weight: 600;
            transform: scale(1.1);
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
        }}

        #transcript-box::-webkit-scrollbar {{ width: 6px; }}
        #transcript-box::-webkit-scrollbar-thumb {{ background: #2d3748; border-radius: 10px; }}
    </style>

    <div class="main-container">
        <audio id="audio-player" controls src="{audio_url}"></audio>
        <div id="transcript-box"></div>
    </div>

    <script>
        const audio = document.getElementById('audio-player');
        const box = document.getElementById('transcript-box');
        const data = {transcript_json};

        // Matnni yaratish
        data.forEach((item, index) => {{
            const span = document.createElement('span');
            span.className = 'word';
            span.id = 'word-' + index;
            span.innerText = item.text;
            span.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(span);
        }});

        let currentIndex = -1;

        audio.ontimeupdate = () => {{
            const time = audio.currentTime;
            let activeIdx = data.findIndex(i => time >= i.start && time <= i.end);
            
            if (activeIdx !== -1 && activeIdx !== currentIndex) {{
                if (currentIndex !== -1) document.getElementById('word-'+currentIndex).classList.remove('active');
                const activeEl = document.getElementById('word-'+activeIdx);
                activeEl.classList.add('active');
                activeEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                currentIndex = activeIdx;
            }}
        }};
    </script>
    """
    components.html(html_code, height=500)

# --- 6. STREAMLIT INTERFEYSI ---
st.markdown(f"### 🎙️ Shodlik Transcribe & Karaoke")
st.caption("Dasturchi: @Otavaliyev_M")

uploaded_file = st.file_uploader("Audio faylni yuklang (MP3 formatda)", type=["mp3"])

if uploaded_file:
    # Faylni vaqtinchalik saqlash
    with open("temp_audio.mp3", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    if st.button("Transkripsiyani boshlash"):
        with st.spinner("Matnga o'girilmoqda, kuting..."):
            # Whisper orqali transkripsiya
            result = model.transcribe("temp_audio.mp3", verbose=False)
            
            # Segmentlarni tayyorlash
            transcript_data = []
            full_text = ""
            for segment in result['segments']:
                transcript_data.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": segment['text'].strip()
                })
                full_text += f"[{segment['start']:.2f}s] {segment['text'].strip()}\n"
            
            # Imzoni qo'shish
            final_text = full_text + SIGNATURE_TEXT
            
            st.success("Tayyor!")

            # Karaoke pleerni ko'rsatish
            audio_b64 = get_audio_base64(uploaded_file.getvalue())
            render_karaoke(audio_b64, json.dumps(transcript_data))

            # Yuklab olish tugmasi
            st.download_button(
                label="Matnni (.txt) yuklab olish",
                data=final_text,
                file_name="transkripsiya_shodlik.txt",
                mime="text/plain"
            )

    # Vaqtinchalik faylni o'chirish (tozalash)
    if os.path.exists("temp_audio.mp3"):
        os.remove("temp_audio.mp3")

st.markdown("---")
st.markdown("👨‍💻 **Dastur muallifi:** Shodlik (Otavaliyev_M)")
st.markdown("Links: [Telegram](https://t.me/Otavaliyev_M) | [Instagram](https://instagram.com/SHodlik1221)")
