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

st.set_page_config(page_title="Neon Karaoke AI", layout="centered")

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
    [data-testid="stFileUploader"] button span::before { content: "FAYL YUKLASH"; visibility: visible; }
    [data-testid="stFileUploader"] button span { visibility: hidden; }

    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0,229,255,0.2); border-radius: 20px; padding: 25px; margin-top: 20px; }
    
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000; color: #00e5ff; border: 2px solid #00e5ff;
        box-shadow: 0 0 15px #00e5ff; border-radius: 12px; font-weight: bold; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. PLAYER ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
    <div class="neon-box">
        <h3 style="color:#00e5ff;">🎵 NEON SMART PLAYER</h3>
        <audio id="player" controls style="width:100%; filter:invert(1); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #222;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {json.dumps(transcript_data)};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.marginBottom='5px'; div.style.cursor='pointer';
            div.style.transition='0.3s'; div.style.borderLeft='4px solid #111';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444;">${{line.text}}</div>` + 
                            (line.tr ? `<div style="font-size:16px; color:#222; margin-top:5px;">${{line.tr}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el) {{ el.children[0].style.color='#444'; el.style.borderLeftColor='#111'; el.style.background='none'; }}
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
    st.components.v1.html(html, height=620)

# --- 4. ASOSIY LOGIKA ---
st.title("🎧 NEON AI TRANSCRIPT")

up = st.file_uploader("", type=['mp3', 'wav'], label_visibility="collapsed")
lang_choice = st.selectbox("Tarjima tili:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 AQLLI TAHLILNI BOSHLASH") and up:
    path = f"t_{time.time()}.mp3"
    progress_placeholder = st.empty() 

    try:
        with progress_placeholder.container():
            st.markdown("<p style='color:#00e5ff; text-align:center;'>⚡ Mazmuniy tahlil qilinmoqda...</p>", unsafe_allow_html=True)
            bar = st.progress(0)
            with open(path, "wb") as f: f.write(up.getbuffer())
            bar.progress(20)
            
            # Groq API call
            with open(path, "rb") as file:
                trans = client.audio.transcriptions.create(
                    file=(path, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json"
                )
            bar.progress(70)
            
            p_data = []; txt_out = ""; t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang_choice)

            for s in trans.segments:
                raw_text = s['text'].strip()
                
                # 1. GRAMMATIK BO'LISH (Punctuation)
                # Gaplarni . ! ? bo'yicha bo'lamiz
                sentences = re.split(r'(?<=[.!?])\s+', raw_text)
                
                segment_duration = s['end'] - s['start']
                total_chars = len(raw_text) if len(raw_text) > 0 else 1

                current_start = s['start']

                for part in sentences:
                    if not part: continue
                    
                    # 2. MAZMUNIY BO'LISH (Length/Sense)
                    # Agar birorta gap juda uzun bo'lsa (6 tadan ko'p so'z), uni ham bo'lamiz
                    words = part.split()
                    if len(words) > 7:
                        sub_chunks = [words[i:i + 6] for i in range(0, len(words), 6)]
                    else:
                        sub_chunks = [words]

                    for chunk in sub_chunks:
                        chunk_text = " ".join(chunk)
                        # Vaqtni harflar soniga qarab adolatli taqsimlaymiz
                        chunk_weight = len(chunk_text) / total_chars
                        chunk_duration = segment_duration * chunk_weight
                        
                        chunk_end = current_start + chunk_duration
                        
                        tr = GoogleTranslator(source='auto', target=t_code).translate(chunk_text) if t_code else None
                        p_data.append({"start": current_start, "end": chunk_end, "text": chunk_text, "tr": tr})
                        
                        tm = f"[{int(current_start//60):02d}:{int(current_start%60):02d}]"
                        txt_out += f"{tm} {chunk_text}\n" + (f"T: {tr}\n" if tr else "") + "\n"
                        
                        current_start = chunk_end
            
            uz_now = datetime.now(uz_tz).strftime('%H:%M:%S')
            pechat = f"\n---\n👤 Shodlik (Otavaliyev_M) | ⏰ {uz_now}\n🤖 Neon Semantic Server"
            txt_out += pechat
            
            bar.progress(100); time.sleep(0.5); progress_placeholder.empty()

        render_neon_player(up.getvalue(), p_data)
        st.download_button("📄 TXT YUKLAB OLISH", txt_out, file_name=f"tahlil_{up.name}.txt")

    except Exception as e: st.error(f"Xato: {e}")
    finally:
        if os.path.exists(path): os.remove(path)

st.caption("© Shodlik (Otavaliyev_M)")
