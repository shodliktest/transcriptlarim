import streamlit as st
import telebot
from telebot import types
import whisper
import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 1. BOT VA FIREBASE SOZLAMALARI ---
# Siz bergan Token
BOT_TOKEN = "8295692699:AAGQh6_Syp5uxo-M62wZkaKxnOm_KEU5ruw"

# Firebase Kalitlari (Avvalgi suhbatdan)
FB_API_KEY = "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw"
PROJECT_ID = "karoke-pro"

# Botni ulash
bot = telebot.TeleBot(BOT_TOKEN)

# --- 2. STREAMLIT INTERFEYSI (Server o'chmasligi uchun) ---
st.set_page_config(page_title="Karaoke Bot Server", layout="centered")
st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: white; text-align: center; }
        .status { padding: 20px; border-radius: 10px; background-color: #00CC00; color: black; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Telegram Bot Serveri")
st.markdown('<div class="status">✅ BOT ISHLAMOQDA!</div>', unsafe_allow_html=True)
st.write(f"Bot ulangan: @{bot.get_me().username}")
st.info("Endi brauzerni yopib, Telegramdan botni ishlatavering.")

# --- 3. FIREBASEGA SAQLASH FUNKSIYASI ---
def save_to_firestore(uid, username, filename, transcript_data):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # To'g'ridan-to'g'ri REST API orqali yozish URL manzili
        url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/transcriptions?key={FB_API_KEY}"
        
        # Ma'lumotlar paketi
        payload = {
            "fields": {
                "uid": {"stringValue": str(uid)},
                "username": {"stringValue": str(username)},
                "filename": {"stringValue": filename},
                "data": {"stringValue": json.dumps(transcript_data)},
                "created_at": {"stringValue": now}
            }
        }
        # So'rov yuborish
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Bazaga saqlandi")
        else:
            print(f"❌ Bazaga yozishda xato: {response.text}")
    except Exception as e:
        print(f"Baza xatosi: {e}")

# --- 4. BOT MANTIQI ---
user_data = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 **Assalomu alaykum!**\n\n"
                 "🎤 Menga **Audio fayl** yoki **Ovozli xabar** yuboring.\n"
                 "📝 Men uni matnga aylantirib, TXT fayl qilib beraman.\n"
                 "💾 Barcha tarixi bazada saqlanadi.")

@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    try:
        chat_id = message.chat.id
        
        # Faylni aniqlash
        if message.content_type == 'audio':
            file_info = bot.get_file(message.audio.file_id)
            file_name = message.audio.file_name or "audio.mp3"
        else: # Ovozli xabar
            file_info = bot.get_file(message.voice.file_id)
            file_name = "voice_message.ogg"

        # Yuklab olish xabari
        bot.send_message(chat_id, "📥 Audio qabul qilindi. Yuklanmoqda...")

        # Faylni serverga yuklash
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Vaqtinchalik nom bilan saqlash
        temp_name = f"user_{chat_id}_{int(datetime.now().timestamp())}.mp3"
        with open(temp_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # User ma'lumotlarini eslab qolish
        user_data[chat_id] = {"file_path": temp_name, "orig_name": file_name}

        # Til tanlash tugmalari
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("🇺🇿 O'zbek", callback_data="uz")
        btn2 = types.InlineKeyboardButton("🇷🇺 Rus", callback_data="ru")
        btn3 = types.InlineKeyboardButton("🇬🇧 Ingliz", callback_data="en")
        btn4 = types.InlineKeyboardButton("📄 Original (Tarjimasiz)", callback_data="original")
        markup.add(btn1, btn2, btn3, btn4)
        
        bot.send_message(chat_id, "Qaysi tilga tarjima qilay?", reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if chat_id not in user_data: 
        bot.answer_callback_query(call.id, "Fayl eskirgan, qaytadan yuboring.")
        return

    # Xabarni o'zgartirish
    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                          text="⏳ **Sun'iy intellekt ishlamoqda...**\n\n(Bu audio hajmiga qarab biroz vaqt olishi mumkin)")
    
    try:
        file_path = user_data[chat_id]["file_path"]
        orig_name = user_data[chat_id]["orig_name"]
        lang = call.data
        
        # --- WHISPER MODELINI ISHLATISH ---
        # Streamlit Cloud resursi yetishi uchun 'base' model ishlatamiz
        model = whisper.load_model("base")
        result = model.transcribe(file_path)
        
        # --- MA'LUMOTLARNI FORMATLASH ---
        txt_content = f"TRANSKRIPSIYA HISOBOTI\nFayl nomi: {orig_name}\n"
        txt_content += f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        firebase_data = [] # Bazaga ketadigan ro'yxat
        
        for s in result['segments']:
            text = s['text'].strip()
            trans = None
            
            # Tarjima jarayoni
            if lang != "original":
                try: 
                    trans = GoogleTranslator(source='auto', target=lang).translate(text)
                except: 
                    pass
            
            # Vaqt formati: [00:12 - 00:15]
            start_m = int(s['start'] // 60)
            start_s = int(s['start'] % 60)
            end_m = int(s['end'] // 60)
            end_s = int(s['end'] % 60)
            timestamp = f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}]"
            
            # TXT faylga yozish
            txt_content += f"{timestamp} {text}\n"
            if trans: 
                txt_content += f"Tarjima: {trans}\n"
            txt_content += "\n" # Bo'sh qator
            
            # Bazaga yig'ish
            firebase_data.append({
                "start": s['start'],
                "end": s['end'],
                "text": text,
                "translated": trans
            })

        # --- IMZO QO'SHISH ---
        txt_content += f"\n---\nYaratuvchi: Shodlik (Otavaliyev_M)\nTelegram: @Otavaliyev_M"

        # --- FIREBASE GA SAQLASH ---
        username = call.from_user.username or call.from_user.first_name or "Foydalanuvchi"
        save_to_firestore(chat_id, username, orig_name, firebase_data)

        # --- TELEGRAMGA YUBORISH ---
        out_filename = f"{orig_name}_natija.txt"
        with open(out_filename, "w", encoding="utf-8") as f:
            f.write(txt_content)
        
        with open(out_filename, "rb") as f:
            bot.send_document(chat_id, f, caption="✅ **Tahlil yakunlandi!**\n\n💾 Nusxasi ma'lumotlar bazasiga saqlandi.")
            
        # --- TOZALASH ---
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(out_filename): os.remove(out_filename)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Xatolik: {e}")
        # Agar fayl qolib ketgan bo'lsa o'chirish
        if os.path.exists(file_path): os.remove(file_path)

# --- BOTNI UZLUKSIZ ISHLATISH LOOP ---
if __name__ == "__main__":
    try:
        bot.infinity_polling()
    except Exception as e:
        st.error(f"Bot to'xtadi: {e}")
