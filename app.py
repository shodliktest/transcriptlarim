import streamlit as st
import whisper
import os, json, base64, pytz, threading, time
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. SOZLAMALAR VA MODELLAR ---
uz_tz = pytz.timezone('Asia/Tashkent')

@st.cache_resource
def load_model():
    return whisper.load_model("tiny")

model = load_model()

# Navbat tizimi uchun lock
if 'queue_lock' not in st.session_state:
    st.session_state.queue_lock = threading.Lock()

@st.cache_resource
def get_queue_manager():
    return {"count": 0}

queue_manager = get_queue_manager()

st.set_page_config(page_title="Neon Karaoke Player Pro", layout="centered")

# --- 2. DIZAYN (SIZGA YOQQAN NEON + STREAMLIT YASHIRILGAN) ---
st.markdown("""
<style>
    /* Streamlit elementlarini butunlay yashirish */
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stViewerBadge"] {display: none;}

    /* Asosiy Qora Fon */
    .stApp { background-color: #000000 !important; color: white !important; }
    h1, h2, h3 { text-align: center; color: #fff; text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; font-weight: bold; }

    /* Neon Navbat Box (Taymer bilan) */
    .queue-box {
        border: 2px solid #00e5ff;
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        background: #050505;
        box-shadow: 0 0 20px #00e5ff;
        margin-bottom: 30px;
        animation: neonPulse 2s infinite;
    }
    @keyframes neonPulse {
        0% { box-shadow: 0 0 10px #00e5ff; }
        50% { box-shadow: 0 0 30px #00e5ff; }
        100% { box-shadow: 0 0 10px #00e5ff; }
    }
    .neon-text { color: #00e5ff; text-shadow: 0 0 15px #00e5ff; font-weight: bold; font-size: 24px; }

    /* Neon Selectbox (Til tanlash) */
    div[data-baseweb="select"] > div {
        background-color: #000000 !important;
        border: 2px solid #00e5ff !important;
        box-shadow: 0 0 15px #00e5ff;
        border-radius: 10px;
        color: white !important;
    }
    div[data-baseweb="select"] span { color: #00e5ff !important; text-shadow: 0 0 10px #00e5ff; font-weight: bold; }
    div[role="listbox"] { background-color: #000 !important; border: 1px solid #00e5ff !important; }
    
    /* Neon Tugmalar (Boshlash va Yuklab olish) */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #000 !important;
        color: #00e5ff !important;
        border: 2px solid #00e5ff !important;
        border-radius: 12px;
        padding: 12px;
        font-size: 18px !important;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 0 15px #00e5ff;
        transition: 0.3s;
        text-transform: uppercase;
    }
    div.stButton > button:hover { background-color: #00e5ff !important; color: #000 !important; box-shadow: 0 0 35px #00e5ff; }

    /* Fayl yuklash oynasi */
    [data-testid="stFileUploader"] section { 
        background-color: #000 !important; 
        border: 2px dashed #00e5ff !important; 
        border-radius: 15px;
        padding: 20px;
    }
    [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] small {
        color: #00e5ff !important; text-shadow: 0 0 5px #00e5ff;
    }

    /* Neon Player Box */
    .neon-box { background: #050505; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0,229,255,0.4); border-radius: 20px; padding: 25px; margin-top: 25px; }
</style>
""", unsafe_allow_html=True)

# --- 3. NEON PLAYER VA LOCALSTORAGE (TIME LIPS-SIZ) ---
def render_neon_player(audio_bytes, transcript_data, save_now=False):
    b64 = base64.b64encode(audio_bytes).decode()
    transcript_json = json.dumps(transcript_data)
    
    save_script = f"<script>if({str(save_now).lower()}){{localStorage.setItem('last_neon_karaoke', `{transcript_json}`);}}</script>"

    html = f"""
    {save_script}
    <div class="neon-box">
        <h3 style="text-align:center; color:#00e5ff; margin-bottom:15px;">🎵 NEON KARAOKE PLAYER 🎵</h3>
        <audio id="player" controls style="width:100%; filter:invert(1) drop-shadow(0 0 8px #00e5ff); margin-bottom:15px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <div id="lyrics" style="height:450px; overflow-y:auto; scroll-behavior:smooth; padding:15px; border-top:1px solid #333;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('lyrics');
        const data = {transcript_json};
        
        data.forEach((line, i) => {{
            const div = document.createElement('div');
            div.id = 'L-'+i; div.style.padding='15px'; div.style.borderBottom='1px solid #222'; div.style.cursor='pointer';
            // PLAYERDA TIME LIPS KO'RSATILMAYDI, FAQAT MATN
            div.innerHTML = `<div style="font-size:22px; font-weight:bold; color:#555;">${{line.text}}</div>` + 
                            (line.translated ? `<div style="font-size:17px; color:#444; margin-top:5px;">${{line.translated}}</div>` : '');
            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
            box.appendChild(div);
        }});
        
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
            data.forEach((_, i) => {{ 
                let el = document.getElementById('L-'+i);
                if(el){{ el.children[0].style.color='#555'; el.style.borderLeft='none'; }}
            }});
            if(idx!==-1){{
                let el = document.getElementById('L-'+idx);
                if(el){{ 
                    el.children[0].style.color='#00e5ff'; el.children[0].style.textShadow='0 0 15px #00e5ff';
                    el.style.borderLeft='5px solid #00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}});
                }}
            }}
        }};
    </script>
    """
    st.components.v1.html(html, height=620)

# --- 4. ASOSIY LOGIKA ---
st.title("🎧 NEON TRANSCRIPT WEB")

# Navbat holati (Taymer bilan)
curr_q = queue_manager["count"]
if curr_q > 0:
    st.markdown(f"""
    <div class="queue-box">
        <div class="neon-text">NAVIBATDA: {curr_q} TA FOYDALANUVCHI</div>
        <div class="neon-text" style="font-size:35px; margin-top:10px;">⏳ TAYMER: ~{curr_q * 1} MINUT</div>
        <div style="color:#888; margin-top:10px;">Server band, iltimos navbatingizni kuting...</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center; color:lime; font-weight:bold; margin-bottom:20px;">🟢 Server tayyor. Tahlilni hozir boshlashingiz mumkin!</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faqat MP3 yoki WAV fayl yuklang", type=['mp3', 'wav'])
lang_choice = st.selectbox("Tarjima tilini tanlang:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "📄 Original"], index=3)

if st.button("🚀 TAHLILNI BOSHLASH"):
    if uploaded_file:
        queue_manager["count"] += 1
        try:
            with st.spinner("⏳ Navbatingiz keldi! AI tahlil qilmoqda..."):
                # Navbatni qulflash
                with st.session_state.queue_lock:
                    temp_path = f"web_tmp_{time.time()}.mp3"
                    with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    
                    # Whisper Tahlil
                    result = model.transcribe(temp_path)
                    
                    p_data = []
                    # TXT fayl tarkibi (PECHAT VA TIME LIPS SAQLANGAN)
                    txt_out = f"📄 TRANSKRIPSIYA: {uploaded_file.name}\n"
                    txt_out += f"📅 Sana: {datetime.now(uz_tz).strftime('%Y-%m-%d %H:%M')}\n"
                    txt_out += "------------------------------------------\n\n"
                    
                    t_code = {"🇺🇿 O'zbek": "uz", "🇷🇺 Rus": "ru", "🇬🇧 Ingliz": "en"}.get(lang_choice)

                    for s in result['segments']:
                        text = s['text'].strip()
                        trans = GoogleTranslator(source='auto', target=t_code).translate(text) if t_code else None
                        
                        # Player uchun ma'lumot (Vaqtsiz)
                        p_data.append({"start": s['start'], "end": s['end'], "text": text, "translated": trans})
                        
                        # TXT fayl uchun ma'lumot (Vaqtli [00:00 - 00:05])
                        start_f = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}"
                        end_f = f"{int(s['end']//60):02d}:{int(s['end']%60):02d}"
                        txt_out += f"[{start_f} - {end_f}] {text}\n"
                        if trans: txt_out += f"Tarjima: {trans}\n"
                        txt_out += "\n"

                    # --- IMZO (PECHAT) ---
                    txt_out += "\n=========================================="
                    txt_out += f"\n👤 Yaratuvchi: Shodlik (Otavaliyev_M)"
                    txt_out += f"\n🤖 Platforma: Neon Karaoke Pro Web"
                    txt_out += f"\n⏰ Yakunlangan vaqt: {datetime.now(uz_tz).strftime('%H:%M:%S')} (UZB)"
                    txt_out += "\n=========================================="

                    # Natijalarni chiqarish
                    render_neon_player(uploaded_file.getvalue(), p_data, save_now=True)
                    st.download_button("📄 TXT Faylni Yuklab Olish", txt_out, file_name=f"{uploaded_file.name}.txt")
                    
        except Exception as e:
            st.error(f"Xatolik yuz berdi: {e}")
        finally:
            # O'z-o'zini tozalash va navbatni kamaytirish
            if os.path.exists(temp_path): os.remove(temp_path)
            if queue_manager["count"] > 0: queue_manager["count"] -= 1
            st.rerun() 
    else:
        st.error("Iltimos, fayl yuklang!")

st.markdown("---")
st.caption("© Shodlik (Otavaliyev_M) | Barcha tahlillar xavfsiz va shaxsiydir.")
