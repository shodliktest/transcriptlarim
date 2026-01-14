import streamlit as st
import whisper
import datetime
import os
import tempfile
from deep_translator import GoogleTranslator

# Sahifa sozlamalari
st.set_page_config(page_title="Interactive AI Transcriber", page_icon="📝", layout="wide")

# Custom Dizayn (CSS)
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #f0f2f6;
    }
    .main-text {
        font-size: 1.2rem;
        margin-bottom: 5px;
        padding: 10px;
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

st.title("📝 Interaktiv Transkriptor & Tarjimon")

uploaded_file = st.file_uploader("Audio faylni tanlang", type=["mp3", "wav", "m4a"])

if uploaded_file:
    st.audio(uploaded_file)
    
    # Tarjima tilini tanlash
    target_lang = st.selectbox("Tarjima tilini tanlang:", ["uz", "ru", "en"], index=0)
    
    if st.button("🚀 Transkripsiyani boshlash"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_path = tmp_file.name

        with st.status("AI tahlil qilmoqda...", expanded=True) as status:
            result = model.transcribe(tmp_path)
            status.update(label="Tahlil yakunlandi!", state="complete")

        st.divider()
        
        # Yuklab olish uchun matn (Vaqt belgilari BILAN)
        download_text = ""
        
        # UI uchun matn (Vaqt belgilariSIZ va Interaktiv tarjima bilan)
        st.subheader("📝 Matn (Tarjima uchun gaplar ustiga bosing):")
        
        segments = result.get('segments', [])
        
        for segment in segments:
            # 1. Vaqtni hisoblash (Faqat fayl uchun)
            start = str(datetime.timedelta(seconds=int(segment['start'])))
            end = str(datetime.timedelta(seconds=int(segment['end'])))
            original_text = segment['text'].strip()
            
            # Yuklab olinadigan matnga qo'shish
            download_text += f"[{start} -> {end}] {original_text}\n"
            
            # 2. UI da ko'rsatish (Interaktiv expander bilan)
            # Bu yerda vaqt ko'rinmaydi, faqat matn
            with st.expander(original_text):
                # Bosilganda tarjima qiladi
                try:
                    translation = GoogleTranslator(source='auto', target=target_lang).translate(original_text)
                    st.write(f"**Tarjima:** {translation}")
                except:
                    st.write("Tarjima qilishda xatolik yuz berdi.")

        st.divider()
        
        # Fayl ko'rinishida yuklab olish (Vaqt belgilari bilan)
        st.download_button(
            label="💾 To'liq transkriptni (.txt) yuklab olish",
            data=download_text,
            file_name="transcript_with_timestamps.txt",
            mime="text/plain"
        )
        
        st.balloons()
        os.remove(tmp_path)
