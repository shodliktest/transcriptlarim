import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
from deep_translator import GoogleTranslator

# --- 1. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Shodlik Karaoke Pro", layout="wide", initial_sidebar_state="collapsed")

# --- 2. MUALLIFLIK IMZOSI ---
SIGNATURE_TEXT = """
------------------------------
Shodlik (Otavaliyev_M) Tomondan yaratilgan dasturdan foydalanildi,
Telegram: @Otavaliyev_M  Instagram: @SHodlik1221
"""

# --- 3. WHISPER VA TARJIMA FUNKSIYALARI ---
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text

def get_audio_base64(binary_data):
    b64 = base64.b64encode(binary_data).decode()
    return f"data:audio/mp3;base64,{b64}"

# --- 4. ASOSIY VIZUAL KOMPONENT (REACT DIZAYNI) ---
def render_modern_karaoke(audio_url, transcript_json, target_lang):
    # JavaScript ichida foydalanish uchun JSON'ni stringga aylantiramiz
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/lucide@latest"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
            body {{ font-family: 'Inter', sans-serif; background: transparent; color: white; }}
            .scrollbar-custom::-webkit-scrollbar {{ width: 6px; }}
            .scrollbar-custom::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.05); }}
            .scrollbar-custom::-webkit-scrollbar-thumb {{ background: linear-gradient(to bottom, #ec4899, #a855f7); border-radius: 10px; }}
            .active-segment {{ background: linear-gradient(to right, rgba(236, 72, 153, 0.2), rgba(168, 85, 247, 0.2)); border-left: 4px solid #ec4899; transform: scale(1.02); }}
        </style>
    </head>
    <body class="p-2">
        <div class="max-w-5xl mx-auto bg-white/5 backdrop-blur-2xl rounded-[2rem] p-8 border border-white/10 shadow-2xl">
            
            <div class="mb-10 min-h-[140px] flex flex-col items-center justify-center text-center">
                <p id="main-lyric" class="text-3xl md:text-5xl font-extrabold text-white leading-tight transition-all duration-300">
                    Audio ijro etishni boshlang...
                </p>
                <p id="sub-lyric" class="text-xl md:text-2xl text-pink-400/80 mt-4 font-light italic transition-all duration-300 h-8">
                </p>
            </div>

            <div class="space-y-6">
                <audio id="audio-element" src="{audio_url}"></audio>
                
                <div class="relative group">
                    <input type="range" id="progress-bar" value="0" step="0.1" class="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer accent-pink-500">
                </div>

                <div class="flex items-center justify-between">
                    <span id="time-current" class="text-purple-300 font-mono text-sm">0:00</span>
                    <button id="play-btn" class="bg-gradient-to-r from-pink-500 to-purple-600 hover:scale-110 text-white p-5 rounded-full transition-all shadow-lg shadow-pink-500/25">
                        <i data-lucide="play" id="play-icon"></i>
                    </button>
                    <span id="time-duration" class="text-purple-300 font-mono text-sm">0:00</span>
                </div>
            </div>

            <div id="transcript-list" class="mt-10 space-y-3 max-h-72 overflow-y-auto pr-4 scrollbar-custom">
                </div>
        </div>

        <script>
            const audio = document.getElementById('audio-element');
            const playBtn = document.getElementById('play-btn');
            const playIcon = document.getElementById('play-icon');
            const progressBar = document.getElementById('progress-bar');
            const timeCurrent = document.getElementById('time-current');
            const timeDuration = document.getElementById('time-duration');
            const mainLyric = document.getElementById('main-lyric');
            const subLyric = document.getElementById('sub-lyric');
            const listContainer = document.getElementById('transcript-list');
            
            const data = {transcript_json};

            // Initialize Lucide icons
            lucide.createIcons();

            // Populate list
            data.forEach((seg, idx) => {{
                const div = document.createElement('div');
                div.id = 'seg-' + idx;
                div.className = "p-4 rounded-2xl cursor-pointer border border-transparent hover:bg-white/5 transition-all duration-300";
                div.innerHTML = `
                    <div class="flex gap-4">
                        <span class="text-pink-400 font-mono text-xs mt-1">${{formatTime(seg.start)}}</span>
                        <div>
                            <p class="text-white font-medium">${{seg.text}}</p>
                            ${{seg.translated ? `<p class="text-gray-400 text-sm mt-1 italic">${{seg.translated}}</p>` : ''}}
                        </div>
                    </div>
                `;
                div.onclick = () => {{ audio.currentTime = seg.start; audio.play(); if(audio.paused) togglePlay(); }};
                listContainer.appendChild(div);
            }});

            function formatTime(seconds) {{
                const m = Math.floor(seconds / 60);
                const s = Math.floor(seconds % 60);
                return m + ":" + (s < 10 ? '0' : '') + s;
            }}

            function togglePlay() {{
                if (audio.paused) {{
                    audio.play();
                    playBtn.innerHTML = '<i data-lucide="pause"></i>';
                }} else {{
                    audio.pause();
                    playBtn.innerHTML = '<i data-lucide="play"></i>';
                }}
                lucide.createIcons();
            }}

            playBtn.onclick = togglePlay;

            audio.onloadedmetadata = () => {{
                progressBar.max = audio.duration;
                timeDuration.innerText = formatTime(audio.duration);
            }};

            audio.ontimeupdate = () => {{
                const cur = audio.currentTime;
                progressBar.value = cur;
                timeCurrent.innerText = formatTime(cur);

                let activeIdx = data.findIndex(i => cur >= i.start && cur <= i.end);
                
                // Update UI for active segment
                data.forEach((_, idx) => {{
                    const el = document.getElementById('seg-' + idx);
                    if (idx === activeIdx) {{
                        if(!el.classList.contains('active-segment')) {{
                            el.classList.add('active-segment');
                            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            mainLyric.innerText = data[idx].text;
                            subLyric.innerText = data[idx].translated || '';
                        }}
                    }} else {{
                        el.classList.remove('active-segment');
                    }}
                }});
            }};

            progressBar.oninput = () => {{ audio.currentTime = progressBar.value; }};
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=750)

# --- 5. STREAMLIT ASOSIY QISMI ---
st.markdown("""
    <style>
    .main { background: linear-gradient(to bottom right, #0f172a, #581c87, #831843); }
    .stSelectbox label, .stFileUploader label { color: #f9a8d4 !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Header
col1, col2 = st.columns([1, 5])
with col1:
    st.write("") # Bo'shliq
with col2:
    st.markdown("<h1 style='color: white; font-size: 3rem;'>🎙️ Audio Karaoke Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #d8b4fe;'>Sinxronlashtirilgan transkripsiya va tarjima tizimi</p>", unsafe_allow_html=True)

# Sidebar / Sozlamalar
with st.container():
    c1, c2 = st.columns(2)
    with c1:
        uploaded_file = st.file_uploader("Audio faylni tanlang (MP3)", type=["mp3"])
    with c2:
        lang_options = {
            "Asl tilda (Tarjimasiz)": "original",
            "O'zbek tili": "uz",
            "Rus tili": "ru",
            "Ingliz tili": "en"
        }
        target_lang_label = st.selectbox("Tarjima tilini tanlang:", list(lang_options.keys()))
        target_lang_code = lang_options[target_lang_label]

if uploaded_file:
    if st.button("🚀 Jarayonni boshlash", use_container_width=True):
        with st.spinner("Sun'iy intellekt ishlamoqda..."):
            # Faylni saqlash
            with open("temp_audio.mp3", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Tahlil
            result = model.transcribe("temp_audio.mp3")
            
            transcript_data = []
            file_output = "--- SHODLIK TRANSCRIPTION REPORT ---\n\n"
            
            for segment in result['segments']:
                orig = segment['text'].strip()
                trans = ""
                if target_lang_code != "original":
                    trans = translate_text(orig, target_lang_code)
                
                transcript_data.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": orig,
                    "translated": trans
                })
                
                file_output += f"[{segment['start']:.2f}s] {orig}\n"
                if trans: file_output += f"TARJIMA: {trans}\n"
                file_output += "\n"

            file_output += SIGNATURE_TEXT
            
            # Karaoke render
            audio_url = get_audio_base64(uploaded_file.getvalue())
            render_modern_karaoke(audio_url, json.dumps(transcript_data), target_lang_code)
            
            # Download
            st.download_button(
                label="📄 Matnni (.txt) yuklab olish",
                data=file_output,
                file_name="shodlik_karaoke.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        os.remove("temp_audio.mp3")

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: #9ca3af;'>Shodlik (Otavaliyev_M) &copy; 2026</p>", unsafe_allow_html=True)
