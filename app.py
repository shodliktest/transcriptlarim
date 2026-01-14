def render_modern_ui(audio_url, transcript_json):
    # CSS va JS dagi { } belgilari {{ }} ko'rinishida yozildi
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/lucide@latest"></script>
        <style>
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            @keyframes slideUp {{
                from {{ opacity: 0; transform: translateY(40px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            .animate-fadeIn {{ animation: fadeIn 0.8s ease-out; }}
            .animate-slideUp {{ animation: slideUp 0.6s ease-out; }}
            
            .scrollbar-custom::-webkit-scrollbar {{ width: 8px; }}
            .scrollbar-custom::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.1); border-radius: 10px; }}
            .scrollbar-custom::-webkit-scrollbar-thumb {{ background: linear-gradient(to bottom, #ec4899, #a855f7); border-radius: 10px; }}
        </style>
    </head>
    <body class="bg-gradient-to-br from-indigo-950 via-purple-900 to-pink-900 min-h-screen p-4 md:p-8 text-white">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-12 animate-fadeIn">
                <div class="flex items-center justify-center gap-3 mb-4">
                    <div class="relative">
                        <i data-lucide="mic" class="w-12 h-12 text-pink-400"></i>
                        <div class="absolute inset-0 bg-pink-400/20 blur-xl rounded-full animate-ping"></div>
                    </div>
                    <h1 class="text-5xl md:text-6xl font-black bg-gradient-to-r from-pink-300 via-purple-300 to-indigo-300 bg-clip-text text-transparent">
                        Audio Karaoke
                    </h1>
                </div>
            </div>

            <div class="bg-white/10 backdrop-blur-xl rounded-3xl p-8 border border-white/20 shadow-2xl animate-slideUp">
                <audio id="audio-player" src="{audio_url}"></audio>
                
                <div class="mb-8 min-h-[120px] flex items-center justify-center text-center">
                    <p id="active-text" class="text-3xl md:text-5xl font-bold text-white leading-relaxed px-4">
                        Tayyor bo'lsangiz Play tugmasini bosing...
                    </p>
                </div>

                <div class="relative h-3 bg-white/10 rounded-full mb-6 cursor-pointer group overflow-hidden">
                    <div id="progress-bar" class="absolute h-full bg-gradient-to-r from-pink-500 to-purple-600 rounded-full" style="width: 0%"></div>
                </div>

                <div class="flex items-center justify-between mb-8">
                    <span id="time-current" class="text-purple-200 font-mono">0:00</span>
                    <button id="play-btn" class="bg-gradient-to-r from-pink-500 to-purple-600 text-white p-6 rounded-full">
                        <i data-lucide="play" id="play-icon" class="w-8 h-8"></i>
                    </button>
                    <span id="time-duration" class="text-purple-200 font-mono">0:00</span>
                </div>

                <div id="transcript-list" class="bg-black/20 rounded-2xl p-6 max-h-64 overflow-y-auto scrollbar-custom space-y-2">
                </div>
            </div>
        </div>

        <script>
            const audio = document.getElementById('audio-player');
            const playBtn = document.getElementById('play-btn');
            const progressBar = document.getElementById('progress-bar');
            const activeText = document.getElementById('active-text');
            const transcriptList = document.getElementById('transcript-list');
            const timeCurrent = document.getElementById('time-current');
            const timeDuration = document.getElementById('time-duration');
            
            // Python'dan kelgan ma'lumot (bitta qavsda qoladi)
            const data = {transcript_json};

            lucide.createIcons();

            data.forEach((seg, idx) => {{
                const div = document.createElement('div');
                div.id = 'seg-' + idx;
                div.className = "p-4 rounded-xl cursor-pointer transition-all bg-white/5";
                div.innerHTML = `
                    <div class="flex items-start gap-3">
                        <span class="text-purple-300 text-sm font-mono mt-1">${{formatTime(seg.start)}}</span>
                        <div>
                            <p class="text-white">${{seg.text}}</p>
                            ${{seg.translated ? `<p class="text-pink-400/60 text-sm italic mt-1">${{seg.translated}}</p>` : ''}}
                        </div>
                    </div>
                `;
                div.onclick = () => {{ audio.currentTime = seg.start; audio.play(); }};
                transcriptList.appendChild(div);
            }});

            function formatTime(s) {{
                const mins = Math.floor(s / 60);
                const secs = Math.floor(s % 60);
                return mins + ":" + (secs < 10 ? '0' : '') + secs;
            }}

            playBtn.onclick = () => {{
                if (audio.paused) {{
                    audio.play();
                    playBtn.innerHTML = '<i data-lucide="pause" class="w-8 h-8"></i>';
                }} else {{
                    audio.pause();
                    playBtn.innerHTML = '<i data-lucide="play" class="w-8 h-8"></i>';
                }}
                lucide.createIcons();
            }};

            audio.ontimeupdate = () => {{
                const cur = audio.currentTime;
                const dur = audio.duration;
                progressBar.style.width = (cur / dur * 100) + "%";
                timeCurrent.innerText = formatTime(cur);
                timeDuration.innerText = formatTime(dur);

                let activeIdx = data.findIndex(i => cur >= i.start && cur <= i.end);
                data.forEach((_, i) => {{
                    const el = document.getElementById('seg-' + i);
                    if(i === activeIdx) {{
                        el.className = "p-4 rounded-xl cursor-pointer bg-gradient-to-r from-pink-500/30 to-purple-600/30 border border-pink-400/50 scale-105";
                        activeText.innerText = data[i].text;
                    }} else {{
                        el.className = "p-4 rounded-xl cursor-pointer bg-white/5";
                    }}
                }});
            }};
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=850, scrolling=True)
