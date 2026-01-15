import streamlit as st
import os, json, base64, pytz, time
from datetime import datetime
from groq import Groq # Whisper o'rniga yengil Groq ishlatamiz

# --- 1. SOZLAMALAR ---
uz_tz = pytz.timezone('Asia/Tashkent')
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Neon Karaoke", layout="centered")

# --- 2. SIZNING ASLIY NEON DIZAYNINGIZ ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #000000 !important; color: white !important; }
    
    div[data-baseweb="select"] > div { background-color: #000 !important; border: 2px solid #00e5ff !important; box-shadow: 0 0 10px #00e5ff; }
    div[data-baseweb="select"] span { color: #00e5ff !important; font-weight: bold; }
    
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000 !important; color: #00e5ff !important; border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff; border-radius: 12px; font-weight: bold; width: 100%;
    }
    div.stButton > button:hover { background-color: #00e5ff !important; color: #000 !important; box-shadow: 0 0 30px #00e5ff; }

    [data-testid="stFileUploader"] section { background-color: #000 !important; border: 2px dashed #00e5ff !important; }
    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 20px rgba(0,229,255,0.4); border-radius: 20px; padding: 25px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; text-shadow: 0 0 10px #00e5ff;">🎵 NEON KARAOKE PLAYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 5px #00e5ff); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:400px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #222'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444;">${{line.text}}</div>`;
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
                    el.style.borderLeft='5px solid #00e5ff';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. ASOSIY QISM ---
st.title("🎧 NEON TRANSCRIPT WEB")

up = st.file_uploader("MP3 yuklang", type=['mp3'])

if st.button("🚀 TAHLILNI BOSHLASH") and up:
    path = f"tmp_{time.time()}.mp3"
    try:
        with st.spinner("⚡ O'ta tezkor AI tahlil qilmoqda..."):
            with open(path, "wb") as f: f.write(up.getbuffer())
            
            # GROQ API orqali Whisper (Base modeldan ham aniqroq va 100x tezroq)
            with open(path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(path, file.read()),
                    model="whisper-large-v3-turbo", # Eng kuchli va tezkor model
                    response_format="verbose_json",
                )
            
            p_data = []
            txt_out = f"📄 TRANSKRIPSIYA: {up.name}\n📅 {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n\n"

            for s in transcription.segments:
                text = s['text'].strip()
                p_data.append({"start": s['start'], "end": s['end'], "text": text})
                txt_out += f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {text}\n"

            txt_out += f"\n---\n👤 Shodlik (Otavaliyev_M)"
            
            render_neon_player(up.getvalue(), p_data)
            st.download_button("📄 TXT YUKLAB OLISH", txt_out, file_name=f"{up.name}.txt")

    except Exception as e:
        st.error(f"Xatolik: API kalitni tekshiring! {e}")
    finally:
        if os.path.exists(path): os.remove(path)

st.caption("© Shodlik (Otavaliyev_M)")
