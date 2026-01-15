import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
import requests
from deep_translator import GoogleTranslator

# --- 1. FIREBASE SOZLAMALARI (Siz bergan kalitlar) ---
FB_CONFIG = {
    "apiKey": "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw",
    "authDomain": "karoke-pro.firebaseapp.com",
    "projectId": "karoke-pro",
}

# --- 2. SAHIFA DIZAYNI VA BRENDINGNI YASHIRISH ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

st.markdown("""
<style>
    /* Streamlit elementlarini yashirish */
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
        color: white;
        margin-bottom: 20px;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        font-weight: 800 !important;
        height: 50px;
        border: none !important;
    }
    label p { color: white !important; font-weight: 600 !important; }
    div[data-baseweb="select"] { background-color: white !important; border-radius: 12px !important; }
    div[data-baseweb="select"] * { color: black !important; }
    
    /* Logout tugmasi uchun qizil gradient */
    .logout-btn > button {
        background: linear-gradient(90deg, #ff4b2b 0%, #ff416c 100%) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FIREBASE VA FIRESTORE FUNKSIYALARI ---
def fb_request(endpoint, payload, mode="auth"):
    if mode == "auth":
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:{endpoint}?key={FB_CONFIG['apiKey']}"
    else: # Firestore
        url = f"https://firestore.googleapis.com/v1/projects/{FB_CONFIG['projectId']}/databases/(default)/documents/{endpoint}"
    return requests.post(url, json=payload).json()

def save_to_firestore(uid, filename, transcript_data):
    # Ma'lumotni Firestore bazasiga yozish
    payload = {
        "fields": {
            "uid": {"stringValue": uid},
            "filename": {"stringValue": filename},
            "data": {"stringValue": json.dumps(transcript_data)}
        }
    }
    fb_request("transcriptions", payload, mode="firestore")

def get_history(uid):
    # Firestore'dan foydalanuvchining arxivini olish
    url = f"https://firestore.googleapis.com/v1/projects/{FB_CONFIG['projectId']}/databases/(default)/documents:runQuery"
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "transcriptions"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "uid"},
                    "op": "EQUAL",
                    "value": {"stringValue": uid}
                }
            }
        }
    }
    res = requests.post(url, json=query).json()
    return res

# --- 4. KARAOKE PLEYER ---
def render_karaoke(audio_url, transcript_json):
    html_code = f"""
    <div style="background:#000; padding:20px; border-radius:25px; border:1px solid #333; margin-top:20px;">
        <audio id="aud" controls src="{audio_url}" style="width:100%; filter:invert(1); margin-bottom:20px;"></audio>
        <div id="t-box" style="height:400px; overflow-y:auto; padding:10px; font-family:sans-serif;"></div>
    </div>
    <script>
        const audio = document.getElementById('aud');
        const box = document.getElementById('t-box');
        const data = {transcript_json};
        
        data.forEach((item, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; div.style.padding='15px'; div.style.marginBottom='10px'; div.style.cursor='pointer'; div.style.transition='0.3s'; div.style.color='#444';
            div.innerHTML = `<div style="font-size:22px; font-weight:bold;">${{item.text}}</div>` + 
                            (item.translated ? `<div style="font-size:16px; color:#777; font-style:italic;">${{item.translated}}</div>` : "");
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(i => audio.currentTime >= i.start && audio.currentTime <= i.end);
            data.forEach((_, i) => {{ const el = document.getElementById('s-'+i); el.style.color='#444'; el.style.textShadow='none'; }});
            if(idx !== -1) {{
                const active = document.getElementById('s-'+idx);
                active.style.color='#00e5ff'; active.style.textShadow='0 0 10px #00e5ff';
                active.scrollIntoView({{behavior:'smooth', block:'center'}});
            }}
        }};
    </script>
    """
    components.html(html_code, height=550)

# --- 5. ASOSIY DASTUR MANTIQI ---
if 'user' not in st.session_state:
    # --- LOGIN / SIGNUP OYNASI ---
    st.markdown("<h1 style='color:white; text-align:center;'>Audio Karaoke</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    auth_mode = st.radio("Tanlang", ["Kirish", "Ro'yxatdan o'tish"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Parol (kamida 6 belgi)", type="password")
    
    if st.button("Davom etish"):
        mode = "signInWithPassword" if auth_mode == "Kirish" else "signUp"
        res = fb_request(mode, {"email": email, "password": password, "returnSecureToken": True})
        if 'localId' in res:
            st.session_state.user = res
            st.rerun()
        else:
            st.error("Xatolik: Ma'lumotlarni tekshiring!")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # --- FOYDALANUVCHI KIRGAN HOLAT ---
    uid = st.session_state.user['localId']
    
    # Sidebar: Foydalanuvchi ma'lumoti va Logout
    st.sidebar.markdown(f"👤 **{st.session_state.user['email']}**")
    st.sidebar.markdown("---")
    if st.sidebar.button("🔴 Tizimdan chiqish", key="logout"):
        del st.session_state.user
        st.rerun()

    # Asosiy sahifa: Tablar (Yangi Tahlil va Arxiv)
    tab1, tab2 = st.tabs(["✨ Yangi Tahlil", "📂 Arxiv (Tarix)"])

    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        up_file = st.file_uploader("Audio faylni tanlang", type=["mp3", "wav"])
        
        langs = {"Tanlanmagan (Original)": "original", "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"}
        target_lang = st.selectbox("Tarjima tili", list(langs.keys()), index=0)
        
        if st.button("🚀 Tahlilni boshlash"):
            if up_file:
                with st.spinner("Sun'iy intellekt tahlil qilmoqda..."):
                    with open("temp.mp3", "wb") as f: f.write(up_file.getbuffer())
                    model = whisper.load_model("base")
                    result = model.transcribe("temp.mp3")
                    
                    t_data = []
                    for s in result['segments']:
                        orig = s['text'].strip()
                        trans = None
                        if langs[target_lang] != "original":
                            trans = GoogleTranslator(source='auto', target=langs[target_lang]).translate(orig)
                        t_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
                    
                    # Firestore'ga saqlash
                    save_to_firestore(uid, up_file.name, t_data)
                    
                    # Natijani ko'rsatish
                    audio_b64 = f"data:audio/mp3;base64,{base64.b64encode(up_file.getvalue()).decode()}"
                    render_karaoke(audio_b64, json.dumps(t_data))
                    st.success("Tahlil yakunlandi va Arxivga saqlandi!")
            else: st.warning("Fayl yuklang!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Sizning avvalgi transkripsiyalaringiz")
        
        history = get_history(uid)
        
        if history and len(history) > 0 and 'document' in history[0]:
            for doc in history:
                fields = doc['document']['fields']
                fname = fields['filename']['stringValue']
                t_json = fields['data']['stringValue']
                
                with st.expander(f"🎵 {fname}"):
                    trans_list = json.loads(t_json)
                    txt_for_download = ""
                    for item in trans_list:
                        st.write(f"**{item['text']}**")
                        txt_for_download += f"{item['text']}\n"
                        if item['translated']: 
                            st.write(f"_{item['translated']}_")
                            txt_for_download += f"Tarjima: {item['translated']}\n"
                        st.divider()
                    
                    st.download_button(
                        label="📄 TXT yuklab olish",
                        data=txt_for_download,
                        file_name=f"{fname}_trans.txt",
                        key=f"dl_{fname}"
                    )
        else:
            st.info("Hozircha tahlillar mavjud emas.")
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("<div style='text-align:center; color:white; opacity:0.5; margin-top:20px;'>Shodlik (Otavaliyev_M) | 2026</div>", unsafe_allow_html=True)
    
