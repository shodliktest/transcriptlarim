import streamlit as st
import os, json, base64, pytz, time, re
from datetime import datetime
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
uz_tz = pytz.timezone('Asia/Tashkent')

@st.cache_resource
def get_groq_client():
    try:
        return Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        return None

client = get_groq_client()
if not client:
    st.error("❌ Secrets bo'limida 'GROQ_API_KEY' topilmadi!")
    st.stop()

st.set_page_config(page_title="Neon Karaoke Ultra", layout="centered")

# --- 2. DIZAYN (NEON) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stApp { background-color: #000; color: white; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff; font-weight: bold; }

    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #00e5ff, #00ff88);
        box-shadow: 0 0 20px #00e5ff; border-radius: 10px;
    }

    [data-testid="stFileUploader"] section { 
        background-color: #000; border: 3px dashed #00e5ff; 
        border-radius: 20px; padding: 40px;
    }
    [data-testid="stFileUploader"] svg { display: none; }
    [data-testid="stFileUploader"] button {
         background-color: #000; color: #00e5ff;
         border: 2px solid #00e5ff; box-shadow: 0 0 15px #00e5ff;
         border-radius: 10px; font-weight: bold; width: 100%;
    }
    [data-testid="stFileUploader"] button span::before { content: "FAYL TANLASH"; visibility: visible; }
    [data-testid="stFileUploader"] button span { visibility: hidden; }

    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0,229,255,0.3); border-radius: 20px; padding: 25px; margin-top: 20px; }
    .limit-text { color: #ff0055; text-shadow: 0 0 10px #ff0055; text-align: center; font-weight: bold; }
    
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000; color: #00e5ff; border: 2px solid #00e5ff;
        box-shadow: 0 0 15px #00e5ff; border-radius: 12px; font-weight: bold; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="color:#00e5ff;">🎵 NEON KARAOKE PLAYER</h3>
        <audio id="player" controls style="width:100%; filter:invert(1); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:10px;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='12px'; div.style.borderLeft='3px solid #111'; div.style.marginBottom='5px';
            div.innerHTML = `<div style="font-size:20px; font-weight:bold; color:#333;">${{line.text}}</div>` + 
                            (line.tr ? `<div style="font-size:15px; color:#222;">${{line.tr}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el) {{ el.children[0].style.color='#333'; el.style.borderLeftColor='#111'; el.style.background='none'; }}
            }});
            if(idx !== -1){{
                let el = document.getElementById('L-'+idx);
                if(el) {{ 
                    el.children[0].style.color='#00e5ff'; 
                    el.style.borderLeftColor='#00e5ff';
                    el.style.background='rgba(0, 229, 255, 0.05)';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=600)

# --- 4. ASOSIY LOGIKA ---
st.title("🎧 NEON TRANSCRIPT PRO")
st.markdown('<p class="limit-text">⚠️ MAKSIMAL 25MB | MP3, WAV</p>', unsafe_allow_html=True)

up = st.file_uploader("", type=['mp3', 'wav'], label_visibility="collapsed")
lang_choice = st.selectbox("Tarjima tili:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 TAHLILNI BOSHLASH") and up:
    path = f"t_{time.time()}.mp3"
    progress_placeholder = st.empty() 

    try:
        with progress_placeholder.container():
            st.markdown("<p style='color:#00e5ff; text-align:center;'>⚡ AI soniyalarni hisoblamoqda...</p>", unsafe_allow_html=True)
            bar = st.progress(0)
            with open(path, "wb") as f: f.write(up.getbuffer())
            bar.progress(25)
            
            with open(path, "rb") as file:
                trans = client.audio.transcriptions.create(
                    file=(path, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json"
                )
            bar.progress(75)
            
            p_data = []; txt_out = f"📄 TRANSKRIPSIYA: {up.name}\n\n"; t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang_choice)

            for s in trans.segments:
                words = s['text'].strip().split()
                if not words: continue
                
                # HAR 4 TA SO'ZDAN KEYIN YANGI QATORGA BO'LAMIZ (Maydalash)
                chunk_size = 4
                chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
                
                duration = s['end'] - s['start']
                chunk_duration = duration / len(chunks)

                for i, chunk in enumerate(chunks):
                    chunk_text = " ".join(chunk)
                    c_start = s['start'] + (i * chunk_duration)
                    c_end = c_start + chunk_duration
                    
                    tr = GoogleTranslator(source='auto', target=t_code).translate(chunk_text) if t_code else None
                    p_data.append({"start": c_start, "end": c_end, "text": chunk_text, "tr": tr})
                    
                    tm = f"[{int(c_start//60):02d}:{int(c_start%60):02d}]"
                    txt_out += f"{tm} {chunk_text}\n" + (f"T: {tr}\n" if tr else "") + "\n"
            
            uz_now = datetime.now(uz_tz).strftime('%H:%M:%S')
            pechat = f"\n---\n👤 Shodlik (Otavaliyev_M) | ⏰ {uz_now} (UZB)\n🤖 Neon Ultra Server"
            txt_out += pechat
            
            bar.progress(100); time.sleep(0.5); progress_placeholder.empty()

        render_neon_player(up.getvalue(), p_data)
        st.markdown(f'<div style="text-align:right; color:#00e5ff; font-size:11px;">{pechat.replace("---\\n", "").replace("\\n", "<br>")}</div>', unsafe_allow_html=True)
        st.download_button("📄 TXT YUKLAB OLISH", txt_out, file_name=f"{up.name}.txt")

    except Exception as e: st.error(f"Xato: {e}")
    finally:
        if os.path.exists(path): os.remove(path)

st.caption("© Shodlik (Otavaliyev_M)")
