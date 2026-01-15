import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. FIREBASE CONFIG ---
FB_CONFIG = {
    "apiKey": "AIzaSyD41LiWGecnVDmsFU73mj12ruoz2s3jdgw",
    "projectId": "karoke-pro"
}

st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- 2. CSS DIZAYN (OQ YOZUVLAR) ---
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        font-family: 'Inter', sans-serif;
    }
    .glass-card {
        background: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin-bottom: 20px;
        color: white !important;
    }
    /* Inputlar */
    .stTextInput input, .stSelectbox div, div[data-baseweb="select"] {
        color: black !important; background-color: white !important;
    }
    h1, h2, h3, p, label, span, div { color: white !important; }
    
    .stButton > button {
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important;
        color: #000 !important; font-weight: bold !important; border: none; height: 50px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FIREBASE FUNKSIYALARI (DIAGNOSTIKA BILAN) ---
def fb_auth_request(endpoint, payload):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{endpoint}?key={FB_CONFIG['apiKey']}"
    return requests.post(url, json=payload).json()

def save_to_firestore(uid, filename, transcript_data):
    now = datetime.now().isoformat()
    url = f"https://firestore.googleapis.com/v1/projects/{FB_CONFIG['projectId']}/databases/(default)/documents/transcriptions"
    
    payload = {
        "fields": {
            "uid": {"stringValue": uid},
            "filename": {"stringValue": filename},
            "data": {"stringValue": json.dumps(transcript_data)},
            "created_at": {"stringValue": now}
        }
    }
    res = requests.post(url, json=payload)
    
    # DIAGNOSTIKA: Agar xato bo'lsa, konsolga va ekranga chiqaramiz
    if res.status_code != 200:
        return f"XATO: {res.text}"
    return "OK"

def get_history(uid):
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
            },
            "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}]
        }
    }
    res = requests.post(url, json=query)
    if res.status_code == 200:
        return res.json()
    return []

# --- 4. KARAOKE PLEYER ---
def render_karaoke_neon(audio_url, transcript_json):
    html_code = f"""
    <div style="background:#000; padding:20px; border-radius:20px; border:1px solid #444;">
        <audio id="player" controls src="{audio_url}" style="width:100%; filter:invert(1); margin-bottom:15px;"></audio>
        <div id="t-box" style="height:350px; overflow-y:auto; padding:10px; color:#fff;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('t-box');
        const data = {transcript_json};
        
        data.forEach((item, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i;
            div.style.padding = '10px'; div.style.marginBottom = '5px'; div.style.cursor = 'pointer';
            div.innerHTML = `<div style="font-size:18px; font-weight:bold; color:#aaa;">${{item.text}}</div>` + 
                            (item.translated ? `<div style="font-size:14px; color:#666; font-style:italic;">${{item.translated}}</div>` : "");
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(i => audio.currentTime >= i.start && audio.currentTime <= i.end);
            data.forEach((_, i) => {{ document.getElementById('s-'+i).children[0].style.color = '#aaa'; }});
            if(idx !== -1) {{
                const el = document.getElementById('s-'+idx);
                el.children[0].style.color = '#00e5ff'; el.scrollIntoView({{behavior:'smooth', block:'center'}});
            }}
        }};
    </script>
    """
    components.html(html_code, height=520)

# --- 5. LOGIKA ---
qp = st.query_params
if qp.get("uid"):
    st.session_state.user_id = qp.get("uid")
    st.session_state.email = qp.get("email")

if 'user_id' not in st.session_state:
    st.markdown("<h1 style='text-align:center;'>Kirish</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Kirish", "Ro'yxatdan o'tish"])
    
    with tab1:
        le = st.text_input("Email", key="le")
        lp = st.text_input("Parol", type="password", key="lp")
        if st.button("KIRISH"):
            res = fb_auth_request("signInWithPassword", {"email": le, "password": lp, "returnSecureToken": True})
            if 'localId' in res:
                st.query_params["uid"] = res['localId']
                st.query_params["email"] = res['email']
                st.rerun()
            else: st.error("Xatolik!")
            
    with tab2:
        re = st.text_input("Email", key="re")
        rp = st.text_input("Parol", type="password", key="rp")
        if st.button("RO'YXATDAN O'TISH"):
            res = fb_auth_request("signUp", {"email": re, "password": rp, "returnSecureToken": True})
            if 'localId' in res: st.success("Muvaffaqiyatli!")
            else: st.error("Xatolik!")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # Sidebar
    st.sidebar.write(f"👤 {st.session_state.email}")
    if st.sidebar.button("🔴 CHIQISH"):
        st.query_params.clear()
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    st.markdown("<h2 style='text-align:center;'>Audio Karaoke Pro</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Yangi Tahlil", "Saqlanganlar"])

    with t1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        f = st.file_uploader("Audio", type=["mp3", "wav"])
        langs = {"Tanlanmagan": "original", "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"}
        lng = st.selectbox("Tarjima", list(langs.keys()))
        
        if st.button("BOSHLASH"):
            if f:
                with st.spinner("Jarayon ketmoqda..."):
                    with open("t.mp3", "wb") as file: file.write(f.getbuffer())
                    model = whisper.load_model("base")
                    res = model.transcribe("t.mp3")
                    
                    data = []
                    txt_out = f"FAYL: {f.name}\n\n"
                    for s in res['segments']:
                        orig = s['text'].strip()
                        tr = GoogleTranslator(source='auto', target=langs[lng]).translate(orig) if langs[lng] != "original" else None
                        data.append({"start":s['start'], "end":s['end'], "text":orig, "translated":tr})
                        
                        m_s, s_s = divmod(int(s['start']), 60)
                        m_e, s_e = divmod(int(s['end']), 60)
                        txt_out += f"[{m_s:02d}:{s_s:02d} - {m_e:02d}:{s_e:02d}] {orig}\n"
                        if tr: txt_out += f"Tarjima: {tr}\n"
                        txt_out += "\n"
                    
                    txt_out += "\n---\nMuallif: Shodlik (Otavaliyev_M)\nTG: @Otavaliyev_M"
                    
                    # BAZAGA YOZISH VA TEKSHIRISH
                    status = save_to_firestore(st.session_state.user_id, f.name, data)
                    
                    if status == "OK":
                        st.success("✅ Bazaga muvaffaqiyatli saqlandi!")
                    else:
                        st.error(f"❌ Bazaga saqlanmadi! Sababi: {status}")
                        st.info("Iltimos, Firebase Console -> Firestore -> Rules bo'limini 'allow read, write: if true;' qiling.")

                    b64 = base64.b64encode(f.getvalue()).decode()
                    render_karaoke_neon(f"data:audio/mp3;base64,{b64}", json.dumps(data))
                    st.download_button("TXT Yuklash", txt_out, file_name="natija.txt")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        if st.button("🔄 Yangilash"): st.rerun()
        
        hist = get_history(st.session_state.user_id)
        if hist and 'document' in hist[0]:
            for h in hist:
                d = h['document']['fields']
                fn = d['filename']['stringValue']
                content = json.loads(d['data']['stringValue'])
                
                with st.expander(f"🎵 {fn}"):
                    full_txt = ""
                    for c in content:
                        st.markdown(f"**{c['text']}**")
                        full_txt += f"{c['text']}\n"
                        if c['translated']:
                            st.caption(c['translated'])
                            full_txt += f"Tarjima: {c['translated']}\n"
                        st.divider()
                    st.download_button("Yuklash", full_txt, file_name=f"{fn}.txt", key=h['document']['name'])
        else:
            st.info("Hozircha tarix bo'sh.")
        st.markdown('</div>', unsafe_allow_html=True)
