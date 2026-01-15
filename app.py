import streamlit as st
import streamlit.components.v1 as components
import whisper
import base64
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. FIREBASE KONFIGURATSIYASI ---
FB_CONFIG = {
    "apiKey": "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw",
    "projectId": "karoke-pro"
}

# --- 2. SAHIFA SOZLAMALARI ---
st.set_page_config(page_title="Audio Karaoke Pro", layout="centered")

# --- 3. CUSTOM CSS (DIZAYN VA KONTRAST) ---
st.markdown("""
<style>
    /* Streamlit menyularini yashirish */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    div.stDecoration {display:none;}

    /* Fon */
    .stApp {
        background: linear-gradient(135deg, #2e1065 0%, #4c1d95 50%, #701a75 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Glass Card (Shaffof Oyna) - Yozuvlar oq bo'lishi uchun */
    .glass-card {
        background: rgba(0, 0, 0, 0.4); /* Foni qoraytirildi, yozuv ko'rinishi uchun */
        backdrop-filter: blur(20px);
        border-radius: 25px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin-bottom: 20px;
        color: #ffffff !important; /* Hamma yozuv oq */
    }

    /* Input va Selectboxlar */
    .stTextInput input, .stSelectbox div, div[data-baseweb="select"] {
        color: black !important;
        background-color: white !important;
        border-radius: 10px !important;
    }
    
    /* Tugmalar */
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        font-weight: 800 !important;
        height: 50px;
        border: none !important;
        font-size: 18px !important;
    }
    
    /* Matn ranglari */
    h1, h2, h3, p, label, span {
        color: #ffffff !important;
        text-shadow: 0px 0px 5px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

# --- 4. FIREBASE FUNKSIYALARI ---
def fb_auth_request(endpoint, payload):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{endpoint}?key={FB_CONFIG['apiKey']}"
    return requests.post(url, json=payload).json()

def save_to_firestore(uid, filename, transcript_data):
    # Sana va vaqtni olamiz
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
    return res.status_code

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

# --- 5. KARAOKE PLEYER ---
def render_karaoke_neon(audio_url, transcript_json):
    html_code = f"""
    <div style="background:#000; padding:20px; border-radius:20px; border:2px solid #555;">
        <audio id="player" controls src="{audio_url}" style="width:100%; filter:invert(1); margin-bottom:20px;"></audio>
        <div id="t-box" style="height:350px; overflow-y:auto; padding:10px; color:#fff;"></div>
    </div>
    <script>
        const audio = document.getElementById('player');
        const box = document.getElementById('t-box');
        const data = {transcript_json};
        
        data.forEach((item, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i;
            div.style.padding = '10px'; div.style.marginBottom = '10px'; div.style.cursor = 'pointer'; 
            div.style.borderBottom = '1px solid #333';
            div.innerHTML = `<div style="font-size:20px; font-weight:bold; color:#888;">${{item.text}}</div>` + 
                            (item.translated ? `<div style="font-size:16px; color:#666; font-style:italic;">${{item.translated}}</div>` : "");
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        audio.ontimeupdate = () => {{
            let idx = data.findIndex(i => audio.currentTime >= i.start && audio.currentTime <= i.end);
            data.forEach((_, i) => {{ 
                const el = document.getElementById('s-'+i).children[0];
                el.style.color = '#888'; el.style.textShadow = 'none';
            }});
            if(idx !== -1) {{
                const active = document.getElementById('s-'+idx);
                active.scrollIntoView({{behavior:'smooth', block:'center'}});
                const txt = active.children[0];
                txt.style.color = '#00e5ff'; txt.style.textShadow = '0 0 15px #00e5ff';
            }}
        }};
    </script>
    """
    components.html(html_code, height=550)

# --- 6. ASOSIY LOGIKA (SESSION PERSISTENCE BILAN) ---

# 1. URL dan foydalanuvchi ID sini tekshirish (Sahifa yangilansa ham qoladi)
query_params = st.query_params
user_id_from_url = query_params.get("uid", None)

if user_id_from_url:
    st.session_state.user_id = user_id_from_url
    # Agar email kerak bo'lsa, uni ham URL ga qo'shish yoki bazadan olish mumkin. 
    # Hozircha oddiylik uchun "Foydalanuvchi" deb turamiz.
    st.session_state.user_email = query_params.get("email", "Foydalanuvchi")

# --- 7. LOGIN QISMI ---
if 'user_id' not in st.session_state:
    st.markdown("<h1 style='text-align:center;'>Kirish Tizimi</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Kirish", "Ro'yxatdan o'tish"])
    
    with tab1:
        l_email = st.text_input("Email", key="l_e")
        l_pass = st.text_input("Parol", type="password", key="l_p")
        if st.button("Kirish"):
            res = fb_auth_request("signInWithPassword", {"email": l_email, "password": l_pass, "returnSecureToken": True})
            if 'localId' in res:
                # Muvaffaqiyatli kirish -> URL ga yozib qo'yamiz
                st.query_params["uid"] = res['localId']
                st.query_params["email"] = res['email']
                st.rerun()
            else:
                st.error("Email yoki parol xato!")

    with tab2:
        r_email = st.text_input("Email", key="r_e")
        r_pass = st.text_input("Parol (min 6 ta)", type="password", key="r_p")
        if st.button("Ro'yxatdan o'tish"):
            res = fb_auth_request("signUp", {"email": r_email, "password": r_pass, "returnSecureToken": True})
            if 'localId' in res:
                st.success("Muvaffaqiyatli! Endi Kirish qismidan kiring.")
            else:
                st.error("Xatolik! Parol qisqa bo'lishi mumkin.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 8. ASOSIY DASTUR QISMI (Agar kirilgan bo'lsa) ---
else:
    # Sidebar
    st.sidebar.markdown(f"👤 **{st.session_state.user_email}**")
    st.sidebar.markdown("---")
    
    # LOGOUT TUGMASI
    if st.sidebar.button("🔴 CHIQISH (Log Out)"):
        st.query_params.clear() # URL ni tozalash
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

    st.markdown("<h1 style='text-align:center;'>Audio Karaoke Pro</h1>", unsafe_allow_html=True)

    tabs = st.tabs(["✨ Yangi Tahlil", "📂 Saqlanganlar"])

    # --- TAB 1: TAHLIL ---
    with tabs[0]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        up_file = st.file_uploader("Audio fayl yuklang", type=["mp3", "wav"])
        
        langs = {"Tanlanmagan (Original)": "original", "O'zbek": "uz", "Rus": "ru", "Ingliz": "en"}
        target = st.selectbox("Tarjima tili", list(langs.keys()), index=0)
        
        if st.button("🚀 BOSHLASH"):
            if up_file:
                with st.spinner("AI ishlamoqda..."):
                    with open("temp.mp3", "wb") as f: f.write(up_file.getbuffer())
                    model = whisper.load_model("base")
                    result = model.transcribe("temp.mp3")
                    
                    t_data = []
                    # Time lips chiziqlarsiz
                    txt_content = f"TRANSKRIPSIYA: {up_file.name}\n\n"
                    
                    for s in result['segments']:
                        orig = s['text'].strip()
                        trans = None
                        if langs[target] != "original":
                            trans = GoogleTranslator(source='auto', target=langs[target]).translate(orig)
                        
                        t_data.append({"start":s['start'], "end":s['end'], "text":orig, "translated":trans})
                        
                        # Vaqtni formatlash
                        m_s = int(s['start'] // 60); s_s = int(s['start'] % 60)
                        m_e = int(s['end'] // 60); s_e = int(s['end'] % 60)
                        time_str = f"[{m_s:02d}:{s_s:02d} - {m_e:02d}:{s_e:02d}]"
                        
                        # CHIZIQLARSIZ FORMAT
                        txt_content += f"{time_str} {orig}\n"
                        if trans: txt_content += f"Tarjima: {trans}\n"
                        txt_content += "\n" # Shunchaki bo'sh qator
                    
                    # Imzo
                    txt_content += f"\n\n---\nYaratuvchi: Shodlik (Otavaliyev_M)\nTelegram: @Otavaliyev_M\nSana: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    
                    # Bazaga saqlash
                    status = save_to_firestore(st.session_state.user_id, up_file.name, t_data)
                    if status == 200:
                        st.success("Bazaga saqlandi!")
                    else:
                        st.error("Bazaga saqlashda xatolik bo'ldi (Firebase Rules ni tekshiring)")

                    # Karaoke
                    audio_b64 = f"data:audio/mp3;base64,{base64.b64encode(up_file.getvalue()).decode()}"
                    render_karaoke_neon(audio_b64, json.dumps(t_data))
                    
                    st.download_button("📄 TXT Yuklab olish", txt_content, file_name="natija.txt")
            else:
                st.warning("Fayl tanlanmadi!")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: TARIX ---
    with tabs[1]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        if st.button("🔄 Yangilash"):
            st.rerun()
            
        history = get_history(st.session_state.user_id)
        
        if history and len(history) > 0 and 'document' in history[0]:
            for item in history:
                doc = item['document']['fields']
                fname = doc['filename']['stringValue']
                raw_json = doc['data']['stringValue']
                
                with st.expander(f"🎵 {fname}"):
                    data_list = json.loads(raw_json)
                    # Arxivdan ham TXT yuklash imkoniyati
                    arch_txt = f"TRANSKRIPSIYA (Arxiv): {fname}\n\n"
                    
                    for row in data_list:
                        st.markdown(f"**{row['text']}**")
                        arch_txt += f"{row['text']}\n"
                        if row['translated']:
                            st.caption(row['translated'])
                            arch_txt += f"Tarjima: {row['translated']}\n"
                        st.divider()
                        arch_txt += "\n"
                    
                    arch_txt += f"\n\n---\nYaratuvchi: Shodlik (Otavaliyev_M)\nTelegram: @Otavaliyev_M"
                    st.download_button("📄 Ushbu matnni yuklab olish", arch_txt, file_name=f"{fname}.txt", key=fname)
        else:
            st.info("Hozircha saqlangan ma'lumotlar yo'q.")
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("<div style='text-align:center; color:white; opacity:0.6; margin-top:30px;'>SHodlik (Otavaliyev_M) | 2026</div>", unsafe_allow_html=True)
    
