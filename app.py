def render_karaoke_neon(audio_url, transcript_json):
    html_code = f"""
    <style>
        .karaoke-black-box {{ 
            background-color: #000000; 
            font-family: 'Segoe UI', Tahoma, sans-serif; 
            padding: 35px; 
            border-radius: 25px;
            border: 2px solid #1f1f1f;
            margin-top: 30px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.8);
        }}
        audio {{ 
            width: 100%; 
            filter: invert(100%) hue-rotate(180deg) brightness(1.6); 
            margin-bottom: 30px;
        }}
        #transcript-box {{ 
            height: 450px; 
            overflow-y: auto; 
            padding: 10px 25px; 
            scroll-behavior: smooth; 
        }}
        
        /* Har bir gap bloki */
        .word-segment {{ 
            display: flex;
            flex-direction: column; /* Matnlarni ustma-ust taxlaydi */
            margin-bottom: 25px; /* Gaplar orasidagi masofa */
            padding: 12px;
            border-radius: 12px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            border-left: 4px solid transparent;
        }}

        /* ASOSIY MATN: Oddiy holatda */
        .original-txt {{
            font-size: 24px;
            color: #4b5563; /* To'q kulrang */
            line-height: 1.4;
            transition: all 0.3s ease;
        }}

        /* TARJIMA MATNI: Har doim tiniq va pastroqda */
        .translated-sub {{ 
            font-size: 16px; 
            color: #6b7280; /* Muted kulrang */
            margin-top: 8px; /* Asosiy matndan masofa */
            font-style: italic;
            font-weight: 400;
            line-height: 1.2;
        }}

        /* --- AKTIV (YONUVCHI) HOLAT --- */
        .word-segment.active {{ 
            background: rgba(0, 229, 255, 0.05); /* Juda yengil fon */
            border-left: 4px solid #00e5ff;
            transform: translateX(10px);
        }}

        .word-segment.active .original-txt {{ 
            color: #00e5ff !important; 
            /* Faqat asosiy matn yonadi */
            text-shadow: 0 0 12px rgba(0, 229, 255, 0.7); 
            font-weight: 700;
        }}

        .word-segment.active .translated-sub {{ 
            color: #94a3b8; /* Tarjima yorishadi, lekin neon bo'lmaydi */
            font-weight: 500;
        }}

        #transcript-box::-webkit-scrollbar {{ width: 6px; }}
        #transcript-box::-webkit-scrollbar-thumb {{ background: #333; border-radius: 10px; }}
    </style>

    <div class="karaoke-black-box">
        <audio id="audio-player" controls src="{audio_url}"></audio>
        <div id="transcript-box"></div>
    </div>

    <script>
        const audio = document.getElementById('audio-player');
        const box = document.getElementById('transcript-box');
        const data = {transcript_json};

        data.forEach((item, index) => {{
            const div = document.createElement('div');
            div.className = 'word-segment'; div.id = 'seg-' + index;
            
            // Matnlarni alohida classlar bilan yaratamiz
            let html = '<span class="original-txt">' + item.text + '</span>';
            if(item.translated) {{
                html += '<span class="translated-sub">' + item.translated + '</span>';
            }}
            
            div.innerHTML = html;
            div.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
            box.appendChild(div);
        }});

        let lastIdx = -1;
        audio.ontimeupdate = () => {{
            const cur = audio.currentTime;
            let idx = data.findIndex(i => cur >= i.start && cur <= i.end);
            if (idx !== -1 && idx !== lastIdx) {{
                if (lastIdx !== -1) document.getElementById('seg-'+lastIdx).classList.remove('active');
                const el = document.getElementById('seg-'+idx);
                if (el) {{
                    el.classList.add('active');
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
                lastIdx = idx;
            }}
        }};
    </script>
    """
    components.html(html_code, height=650)
