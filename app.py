import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import os
import requests
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. KONFIGURATSIYA VA KALITLAR ---
FB_CONFIG = {
    "apiKey": "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw",
    "authDomain": "karoke-pro.firebaseapp.com",
    "projectId": "karoke-pro"
}

st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- 2. LOGOUT VA PERSISTENCE (JavaScript orqali loginni saqlash) ---
def set_local_storage(key, value):
    components.html(f"<script>localStorage.setItem('{key}', '{value}');</script>", height=0)

def get_local_storage_and_sync():
    # Bu qism foydalanuvchi ma'lumotlarini brauzer xotirasidan tekshiradi
    js_code = """
    <script>
        const user = localStorage.getItem('karaoke_user');
        if (user) {
            window.parent.postMessage({type: 'streamlit:set_user', data: JSON.parse(user)}, '*');
        }
    </script>
    """
    components.html(js_code, height=0)

# --- 3. CUSTOM CSS ---
st.markdown("""
<style>
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
        backdrop-filter: blur(20px);
        border-radius: 30px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        margin-bottom: 20px;
        color: white;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        font-weight: 800 !important;
        height: 50px;
        border: none;
    }
    div[data-baseweb="select"] { background-color: white !important; border-radius: 12px !important; }
    div[data-baseweb="select"] * { color: black !important; }
</style>
""", unsafe_allow_html=True)

# --- 4. FIREBASE FUNKSIYALARI ---
def fb_auth(email, password, mode="signInWithPassword"):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{mode}?key={FB_CONFIG['apiKey']}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(url, json=payload).json()

def save_to_firestore(uid, filename, transcript_data):
    url = f"https://firestore.googleapis.com/v1/projects/{FB_CONFIG['projectId']}/databases/(default)/documents/transcriptions"
    payload = {
        "fields": {
            "uid": {"stringValue": uid},
            "filename": {"stringValue": filename},
            "data": {"stringValue": json.dumps(transcript_data)},
            "created_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
        }
    }
    requests.post(url, json=payload)

def get_history(uid):
    url = f"https://firestore.googleapis.com/v1/projects/{FB_CONFIG['projectId']}/databases/(default)/documents:runQuery"
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "transcriptions"}],
            "where": {"fieldFilter": {"field": {"fieldPath": "uid"}, "op": "EQUAL", "value": {"stringValue": uid}}},
            "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}]
        }
    }
    res = requests.post(url, json=query).json()
    return res

# --- 5. KARAOKE PLEYER ---
def render_karaoke_neon(audio_url, transcript_json):
    html_code = f"""
    <div style="background:#000; padding:25px; border-radius:25px; border:2px solid #333; margin-top:20px;">
        <audio id="player" controls src="{audio_url}" style="width:100%; filter:invert(1); margin-bottom:25px;"></audio>
        <div id="t-box" style="height:400px; overflow-y:auto; padding:15px; scroll-behavior: smooth;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('t-box');
        const data = {transcript_json};
        
        data.forEach((item, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i;
            div.style.padding = '15px'; div.style.marginBottom = '10px'; div.style.transition = '0.4s'; div.style.color = '#444'; div.style.cursor = 'pointer';
            div.innerHTML = `<div style="font-size:24px; font-weight:bold;">${{item.text}}</div>` + 
                            (item.translated ? `<div style="font-size:16px; color:#666; font-style:italic;">${{item.translated}}</div>` : "");
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(i => audio.currentTime >= i.start && audio.currentTime <= i.end);
            data.forEach((_, i) => {{ 
                const el = document.getElementById('s-'+i);
                el.style.color = '#333'; el.style.textShadow = 'none'; el.style.transform = 'scale(1)';
            }});
            if(idx !== -1) {{
                const active = document.getElementById('s-'+idx);
                active.style.color = '#00e5ff'; active.style.textShadow = '0 0 15px #00e5ff'; active.style.transform = 'scale(1.05)';
                active.scrollIntoView({{behavior:'smooth', block:'center'}});
            }}
        }};
    </script>
    """
    components.html(html_code, height=600)

# --- 6. DASTUR MANTIQI ---
if 'user' not in st.session_state:
    get_local_storage_and_sync() # Xotirani tekshirish
    st.markdown("<h1 style='color:white; text-align:center;'>Audio Karaoke Pro</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    auth_mode = st.radio("Tanlang", ["Kirish", "Ro'yxatdan o'tish"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Parol", type="password")
    
    if st.button("Davom etish"):
        mode = "signInWithPassword" if auth_mode == "Kirish" else "signUp"
        res = fb_auth(email, password, mode)
        if 'localId' in res:
            st.session_state.user = res
            # Xotiraga saqlash (Log out qilmaguncha qoladi)
            set_local_storage('karaoke_user', json.dumps(res))
            st.rerun()
        else: st.error("Ma'lumotlar xato!")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # --- FOYDALANUVCHI INTERFEYSI ---
    uid = st.session_state.user['localId']
    
    # Logout qismi
    if st.sidebar.button("🔴 Tizimdan chiqish (Log Out)"):
        # Xotirani tozalash
        components.html("<script>localStorage.removeItem('karaoke_user'); location.reload();</script>", height=0)
        del st.session_state.user
        st.rerun()

    st.sidebar.markdown(f"👤 **{st.session_state.user['email']}**")
    
    tab1, tab2 = st.tabs(["✨ Yangi Tahlil", "📂 Arxiv (Tarix)"])

    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        up_file = st.file_uploader("Audio yuklang", type=["mp3", "wav"])
        
        langs = {"Tanlanmagan (Original)": "original", "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"}
        target_lang = st.selectbox("Tarjima tili", list(langs.keys()), index=0)
        
        if st.button("🚀 Tahlilni boshlash"):
            if up_file:
                with st.spinner("AI tahlil qilmoqda..."):
                    with open("temp.mp3", "wb") as f: f.write(up_file.getbuffer())
                    model = whisper.load_model("base")
                    result = model.transcribe("temp.mp3")
                    
                    t_data = []
                    # Time lips va Imzo uchun matn tayyorlash
                    download_txt = f"--- AUDIO TRANSKRIPSIYA HISOBOTI ---\nFayl: {up_file.name}\n\n"
                    
                    for s in result['segments']:
                        orig = s['text'].strip()
                        trans = None
                        if langs[target_lang] != "original":
                            trans = GoogleTranslator(source='auto', target=langs[target_lang]).translate(orig)
                        
                        t_data.append({"start": s['start'], "end": s['end'], "text": orig, "translated": trans})
                        
                        # Vaqtni formatlash (min:sec)
                        start_m = int(s['start'] // 60)
                        start_s = int(s['start'] % 60)
                        end_m = int(s['end'] // 60)
                        end_s = int(s['end'] % 60)
                        
                        timestamp = f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}]"
                        download_txt += f"{timestamp} {orig}\n"
                        if trans: download_txt += f"Tarjima: {trans}\n"
                        download_txt += "-"*20 + "\n"
                    
                    # Imzo qo'shish
                    download_txt += f"\n\nCreated by: Shodlik (Otavaliyev_M)\nTelegram: @Otavaliyev_M\nSana: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    
                    # Firestore'ga saqlash
                    save_to_firestore(uid, up_file.name, t_data)
                    
                    audio_b64 = f"data:audio/mp3;base64,{base64.b64encode(up_file.getvalue()).decode()}"
                    render_karaoke_neon(audio_b64, json.dumps(t_data))
                    
                    st.download_button("📄 Natijani yuklab olish (.txt)", data=download_txt, file_name=f"{up_file.name}_shodlik.txt")
                    st.success("Tahlil tugadi!")
            else: st.warning("Fayl yuklang!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Sizning arxivlashtirilgan tahlillaringiz")
        history = get_history(uid)
        
        if history and len(history) > 0 and 'document' in history[0]:
            for doc in history:
                fields = doc['document']['fields']
                fname = fields['filename']['stringValue']
                t_json = fields['data']['stringValue']
                
                with st.expander(f"🎵 {fname}"):
                    # Arxivda ham karaoke ko'rinishida chiqarish (faqat matn, pleyer uchun audio kerak)
                    st.write("Pleer uchun audioni qayta yuklang, quyida esa saqlangan matnlar:")
                    for item in json.loads(t_json):
                        st.markdown(f"<div style='border-left:3px solid #00e5ff; padding-left:10px; margin-bottom:10px;'><b>{item['text']}</b><br><i style='color:#888;'>{item['translated'] if item['translated'] else ''}</i></div>", unsafe_allow_html=True)
        else:
            st.info("Arxiv bo'sh.")
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("<div style='text-align:center; color:white; opacity:0.5; margin-top:20px;'>Shodlik (Otavaliyev_M) | 2026</div>", unsafe_allow_html=True)
    
