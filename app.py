import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
import requests
from deep_translator import GoogleTranslator

# --- 1. FIREBASE SOZLAMALARI ---
FB_CONFIG = {
    "apiKey": "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw",
    "authDomain": "karoke-pro.firebaseapp.com",
    "projectId": "karoke-pro"
}

# --- 2. SAHIFA DIZAYNI VA BRENDINGNI YASHIRISH ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

st.markdown("""
<style>
    /* Streamlit menyularini butunlay yashirish */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    div.stDecoration {display:none;}

    .stApp {
        background: linear-gradient(135deg, #2e1065 0%, #4c1d95 50%, #701a75 100%);
        font-family: 'Inter', sans-serif;
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(16px);
        border-radius: 30px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        color: white;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        font-weight: 800 !important;
        border: none !important;
        padding: 10px !important;
    }
    div[data-baseweb="select"] { background-color: white !important; border-radius: 10px !important; }
    div[data-baseweb="select"] * { color: black !important; }
    label p { color: white !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. FIREBASE AUTH FUNKSIYASI ---
def firebase_auth(email, password, mode="signInWithPassword"):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{mode}?key={FB_CONFIG['apiKey']}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    res = requests.post(url, json=payload)
    return res.json()

# --- 4. KARAOKE PLEYER RENDER ---
def render_karaoke(audio_url, transcript_json):
    html_code = f"""
    <div style="background:#000; padding:20px; border-radius:20px; border:1px solid #333; margin-top:20px;">
        <audio id="aud" controls src="{audio_url}" style="width:100%; filter:invert(1);"></audio>
        <div id="t-box" style="height:350px; overflow-y:auto; color:#444; font-size:22px; padding:10px; line-height:1.6;"></div>
    </div>
    <script>
        const audio = document.getElementById('aud');
        const box = document.getElementById('t-box');
        const data = {transcript_json};
        data.forEach((item, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; div.style.marginBottom='15px'; div.style.cursor='pointer';
            div.innerHTML = `<b>${{item.text}}</b>${{item.translated ? '<br><small style="font-size:14px; color:#666;">'+item.translated+'</small>' : ''}}`;
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});
        audio.ontimeupdate = () => {{
            let idx = data.findIndex(i => audio.currentTime >= i.start && audio.currentTime <= i.end);
            data.forEach((_, i) => document.getElementById('s-'+i).style.color = '#444');
            if(idx !== -1) {{
                const el = document.getElementById('s-'+idx);
                el.style.color = '#00e5ff'; el.style.textShadow = '0 0 10px #00e5ff';
                el.scrollIntoView({{behavior:'smooth', block:'center'}});
            }}
        }};
    </script>
    """
    components.html(html_code, height=500)

# --- 5. DASTUR MANTIQI ---
if 'user' not in st.session_state:
    st.markdown("<h1 style='color:white; text-align:center;'>Audio Karaoke</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    auth_mode = st.radio("Tanlang", ["Kirish", "Ro'yxatdan o'tish"])
    email = st.text_input("Email")
    password = st.text_input("Parol", type="password")
    
    if st.button("Davom etish"):
        mode = "signInWithPassword" if auth_mode == "Kirish" else "signUp"
        res = firebase_auth(email, password, mode)
        if 'localId' in res:
            st.session_state.user = res
            st.rerun()
        else:
            st.error("Xatolik: Ma'lumotlarni tekshiring (Parol kamida 6 belgidan iborat bo'lishi kerak)")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # ASOSIY DASTUR
    st.sidebar.markdown(f"👤 **{st.session_state.user['email']}**")
    if st.sidebar.button("Chiqish"):
        del st.session_state.user
        st.rerun()

    st.markdown("<h2 style='color:white; text-align:center;'>Musiqiy Tahlil</h2>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    up_file = st.file_uploader("Audio yuklang", type=["mp3", "wav"])
    lang = st.selectbox("Tarjima tili", ["O'zbek", "Rus", "Ingliz"])
    lang_code = {"O'zbek":"uz", "Rus":"ru", "Ingliz":"en"}[lang]

    if st.button("✨ Tahlil qilish"):
        if up_file:
            with st.spinner("AI matnlarni ajratmoqda..."):
                with open("t.mp3", "wb") as f: f.write(up_file.getbuffer())
                model = whisper.load_model("base")
                result = model.transcribe("t.mp3")
                
                t_data = []
                for s in result['segments']:
                    txt = s['text'].strip()
                    tr = GoogleTranslator(source='auto', target=lang_code).translate(txt)
                    t_data.append({"start":s['start'], "end":s['end'], "text":txt, "translated":tr})
                
                audio_b64 = f"data:audio/mp3;base64,{base64.b64encode(up_file.getvalue()).decode()}"
                render_karaoke(audio_b64, json.dumps(t_data))
        else:
            st.warning("Fayl yuklanmagan!")
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("<div style='color:white; text-align:center; margin-top:20px; opacity:0.6;'>Shodlik (Otavaliyev_M) | 2026</div>", unsafe_allow_html=True)
    
