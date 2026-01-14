import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Shodlik Transcribe Pro", layout="centered")

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
        .main-container {{ background-color: #0e1117; font-family: 'Inter', sans-serif; color: #ffffff; padding: 20px; border-radius: 15px; }}
        audio {{ width: 100%; margin-bottom: 20px; filter: invert(100%) hue-rotate(180deg) brightness(1.5); }}
        #transcript-box {{ height: 400px; overflow-y: auto; padding: 25px; background: #161b22; border-radius: 12px; line-height: 1.6; font-size: 18px; scroll-behavior: smooth; }}
        .segment {{ margin-bottom: 20px; color: #5f6c7b; transition: all 0.3s ease; cursor: pointer; border-left: 3px solid transparent; padding-left: 15px; }}
        .segment.active {{ color: #00e5ff; border-left: 3px solid #00e5ff; transform: translateX(5px); text-shadow: 0 0 5px rgba(0, 229, 255, 0.3); }}
        .translated-text {{ display: block; font-size: 15px; color: #8b949e; margin-top: 4px; font-style: italic; }}
    </style>
    <div class="main-container">
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
            
            // Asl matn va tarjimani (agar bo'lsa) qo'shish
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
    components.html(html_code, height=550)

# --- 7. INTERFEYS ---
st.title("🎙️ Shodlik: Transcribe & Multi-Translate")

# Til tanlash
lang_options = {
    "Tanlanmagan (Faqat asl tilda)": "original",
    "O'zbek tili": "uz",
    "Rus tili": "ru",
    "Ingliz tili": "en"
}
target_lang_label = st.selectbox("Tarjima kerakmi? (Ixtiyoriy):", list(lang_options.keys()))
target_lang_code = lang_options[target_lang_label]

uploaded_file = st.file_uploader("MP3 faylni tanlang", type=["mp3"])

if uploaded_file:
    with open("temp_audio.mp3", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    if st.button("Jarayonni boshlash"):
        with st.spinner("Tahlil qilinmoqda..."):
            result = model.transcribe("temp_audio.mp3")
            
            transcript_data = []
            final_file_text = "--- TRANSKRIPSIYA HISOBOTI ---\n\n"
            
            for segment in result['segments']:
                original = segment['text'].strip()
                translated = ""
                
                if target_lang_code != "original":
                    # TARJIMA REJIMI
                    translated = translate_text(original, target_lang_code)
                    transcript_data.append({
                        "start": segment['start'], "end": segment['end'], 
                        "text": original, "translated": translated
                    })
                    final_file_text += f"[{segment['start']:.2f}s] {original}\nTARJIMA: {translated}\n\n"
                else:
                    # ODDIY REJIM
                    transcript_data.append({
                        "start": segment['start'], "end": segment['end'], 
                        "text": original, "translated": None
                    })
                    final_file_text += f"[{segment['start']:.2f}s] {original}\n"
            
            final_file_text += SIGNATURE_TEXT
            
            st.success("Bajarildi!")
            
            # Pleer
            audio_b64 = get_audio_base64(uploaded_file.getvalue())
            render_karaoke(audio_b64, json.dumps(transcript_data))

            # TXT fayl
            st.download_button(
                label="Natijani .txt faylda yuklab olish",
                data=final_file_text,
                file_name="shodlik_result.txt",
                mime="text/plain"
            )

    if os.path.exists("temp_audio.mp3"):
        os.remove("temp_audio.mp3")
