import streamlit as st
import whisper
import datetime
import os
import tempfile

st.title("🎧 Audio Transkripsiya")

# Modelni yuklash
@st.cache_resource
def load_model():
    return whisper.load_model("base") # Siz ishlatgan 'base' modeli

model = load_model()

# Fayl yuklash
uploaded_file = st.file_uploader("MP3 faylni tanlang", type=["mp3"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    if st.button("Matnga aylantirish"):
        with st.spinner("Tahlil qilinmoqda..."):
            result = model.transcribe(tmp_path)
            segments = result.get('segments', []) # Segmentlarni olish
            
            txt_output = ""
            for segment in segments:
                # Vaqt formatini hisoblash
                start = str(datetime.timedelta(seconds=int(segment['start'])))
                end = str(datetime.timedelta(seconds=int(segment['end'])))
                line = f"[{start} -> {end}] {segment['text']}\n"
                txt_output += line
                st.text(line)

            st.download_button("Natijani yuklab olish (.txt)", txt_output, file_name="subtitr.txt")
            os.remove(tmp_path)
