import streamlit as st
import whisper
import os, json, base64, pytz, threading, time
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. GLOBAL SOZLAMALAR ---
uz_tz = pytz.timezone('Asia/Tashkent')

@st.cache_resource
def load_model():
    return whisper.load_model("tiny")

model = load_model()

# Global Navbat boshqaruvchisi
if 'queue_lock' not in st.session_state:
    st.session_state.queue_lock = threading.Lock()

@st.cache_resource
def get_global_queue():
    return {"count": 0}

global_queue = get_global_queue()

st.set_page_config(page_title="Neon Karaoke Pro", layout="centered")

# --- 2. MAXSUS NEON DIZAYN ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #000000 !important; color: white !important; }
    
    /* Neon Navbat Box */
    .queue-box {
        border: 2px solid #00e5ff; border-radius: 20px; padding: 25px;
        text-align: center; background: #050505; box-shadow: 0 0 25px #00e5ff;
        margin-bottom: 30px; animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% {box-shadow: 0 0 10px #00e5ff;} 50% {box-shadow: 0 0 30px #00e5ff;} 100% {box-shadow: 0 0 10px #00e5ff;} }
    .neon-text { color: #00e5ff; text-shadow: 0 0 15px #00e5ff; font-weight: bold; font-size: 24px; }

    /* Neon Elementlar */
    div[data-baseweb="select"] > div { background-color: #000 !important; border: 2px solid #00e5ff !important; box-shadow: 0 0 10px #00e5ff; }
    div[data-baseweb="select"] span { color: #00e5ff !important; font-weight: bold; }
    
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000 !important; color: #00e5ff !important; border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff; border-radius: 12px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #00e5ff !important; color: #000 !important; box-shadow: 0 0 35px #00e5ff; }

    [data-testid="stFileUploader"] section { background-color: #000 !important; border: 2px dashed #00e5ff !important; }
    .stProgress > div > div > div { background-color: #00e5ff !important; box-shadow: 0 0 10px #00e5ff; }
</style>
""", unsafe_allow_html=True)

# --- 3. KARAOKE PLAYER KOMPONENTI ---
def render_neon_player(audio_bytes, transcript_data):
    b64 = base64.b64encode(audio_bytes).decode()
    transcript_json = json.dumps(transcript_data)
    
    html = f"""
    <div style="background: #050505; border: 2px solid #00e5ff; border-radius: 20px; padding: 25px; box-shadow: 0 0 30px rgba(0,229,255,0.4);">
        <h3 style="text-align:center; color:#00e5ff; text-shadow: 0 0 10px #00e5ff;">🎵 NEON KARAOKE PLAYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 8px #00e5ff); margin-bottom:20px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:10px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {transcript_json};
        
        // LocalStorage'ga saqlash
        localStorage.setItem('last_karaoke', JSON.stringify(data));

        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #222'; div.style.cursor='pointer';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#444; transition: 0.3s;">${{line.text}}</div>` + 
                            (line.translated ? `<div style="font-size:16px; color:#333; margin-top:5px;">${{line.translated}}</div>` : '');
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
                    el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.borderLeft='5px solid #00e5ff';
                    el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=650)

# --- 4. ASOSIY LOGIKA ---
st.title("🎧 NEON TRANSCRIPT PRO")

# Navbat holati
q_val = global_queue["count"]
if q_val > 0:
    st.markdown(f'<div class="queue-box"><div class="neon-text">NAVIBATDA: {q_val} TA ODAM</div><div class="neon-text" style="font-size:35px;">⏳ ~{q_val} MINUT</div></div>', unsafe_allow_html=True)

up = st.file_uploader("Audio yuklang (MP3/WAV)", type=['mp3', 'wav'])
lang = st.selectbox("Tarjima tili", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 TAHLILNI BOSHLASH"):
    if up:
        global_queue["count"] += 1
        # Ekranni tozalash va progressni ko'rsatish
        status = st.empty()
        bar = st.progress(0)
        
        try:
            with st.session_state.queue_lock:
                status.markdown("⏳ **Navbatingiz keldi! AI yuklanmoqda...**")
                temp_path = f"web_{time.time()}.mp3"
                with open(temp_path, "wb") as f: f.write(up.getbuffer())
                
                status.markdown("⚡ **AI audioni tahlil qilmoqda (Whisper)...**")
                bar.progress(30)
                
                # Whispering...
                result = model.transcribe(temp_path)
                bar.progress(70)
                
                status.markdown("🌐 **Matnlar tarjima qilinmoqda va imzo qo'yilmoqda...**")
                p_data = []
                txt_out = f"📄 TRANSKRIPSIYA: {up.name}\n📅 {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n---\n\n"
                t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)

                for s in result['segments']:
                    text = s['text'].strip()
                    tr = GoogleTranslator(source='auto', target=t_code).translate(text) if t_code else None
                    p_data.append({"start": s['start'], "end": s['end'], "text": text, "translated": tr})
                    
                    st_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                    txt_out += f"[{st_f}] {text}\n" + (f"Tarjima: {tr}\n" if tr else "") + "\n"

                # PECHAT (IMZO)
                txt_out += f"\n---\n👤 Shodlik (Otavaliyev_M) | 🤖 Neon Pro Web | ⏰ {datetime.now(uz_tz).strftime('%H:%M:%S')}"
                
                bar.progress(100)
                status.success("✅ Tahlil tayyor! Karaoke pleyeri yuklandi:")

                # NATIJANI CHIQARISH
                render_neon_player(up.getvalue(), p_data)
                st.download_button("📄 TXT FAYLNI YUKLAB OLISH", txt_out, file_name=f"{up.name}.txt")

        except Exception as e:
            st.error(f"Xatolik: {e}")
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)
            if global_queue["count"] > 0: global_queue["count"] -= 1
            # Navbatni yangilash uchun st.rerun() natija chiqib bo'lgach tavsiya etilmaydi, 
            # chunki u pleyerni o'chirib yuboradi.
    else:
        st.error("Iltimos, fayl yuklang!")

st.caption("© Shodlik (Otavaliyev_M)")
