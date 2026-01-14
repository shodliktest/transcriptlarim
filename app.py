import React, { useState, useRef, useEffect } from 'react';
import { Upload, Play, Pause, Download, Languages, Sparkles, Mic, FileText, Volume2 } from 'lucide-react';

const ModernKaraokeApp = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [targetLang, setTargetLang] = useState('original');
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcriptData, setTranscriptData] = useState([]);
  const [activeSegment, setActiveSegment] = useState(null);
  
  const audioRef = useRef(null);
  const fileInputRef = useRef(null);

  const mockTranscriptData = [
    { start: 0, end: 3.5, text: "Salom, bu test transkripsiyasi" },
    { start: 3.5, end: 7.2, text: "Audio faylni yuklang va natijani ko'ring" },
    { start: 7.2, end: 11.8, text: "Karaoke rejimida matn sinxronlashadi" },
  ];

  const languages = [
    { code: 'original', name: "Asl til (tarjima yo'q)" },
    { code: 'uz', name: "O'zbek" },
    { code: 'ru', name: "Русский" },
    { code: 'en', name: "English" },
  ];

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.addEventListener('timeupdate', handleTimeUpdate);
      audioRef.current.addEventListener('loadedmetadata', handleLoadedMetadata);
    }
    return () => {
      if (audioRef.current) {
        audioRef.current.removeEventListener('timeupdate', handleTimeUpdate);
        audioRef.current.removeEventListener('loadedmetadata', handleLoadedMetadata);
      }
    };
  }, []);

  useEffect(() => {
    const current = transcriptData.find(
      seg => currentTime >= seg.start && currentTime <= seg.end
    );
    setActiveSegment(current);
  }, [currentTime, transcriptData]);

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setAudioFile(file);
      const url = URL.createObjectURL(file);
      setAudioUrl(url);
      setTranscriptData([]);
      setActiveSegment(null);
    }
  };

  const handleProcess = () => {
    setIsProcessing(true);
    setTimeout(() => {
      setTranscriptData(mockTranscriptData);
      setIsProcessing(false);
    }, 2000);
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newTime = percentage * duration;
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  };

  const formatTime = (time) => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleDownload = () => {
    const text = transcriptData.map(seg => 
      `[${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s] ${seg.text}`
    ).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transkripsiya.txt';
    a.click();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-purple-900 to-pink-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12 animate-fadeIn">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="relative">
              <Mic className="w-12 h-12 text-pink-400 animate-pulse" />
              <div className="absolute inset-0 bg-pink-400/20 blur-xl rounded-full animate-ping" />
            </div>
            <h1 className="text-5xl md:text-6xl font-black bg-gradient-to-r from-pink-300 via-purple-300 to-indigo-300 bg-clip-text text-transparent">
              Audio Karaoke
            </h1>
          </div>
          <p className="text-purple-200 text-lg md:text-xl font-light">
            Audio transkriptsiya va sinxronlashgan karaoke tajribasi
          </p>
        </div>

        {/* Upload Section */}
        <div className="bg-white/10 backdrop-blur-xl rounded-3xl p-8 mb-8 border border-white/20 shadow-2xl animate-slideUp">
          <div className="grid md:grid-cols-2 gap-6">
            {/* File Upload */}
            <div>
              <label className="block text-purple-200 font-semibold mb-3 flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Audio fayl yuklash
              </label>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className="relative group cursor-pointer"
              >
                <div className="border-2 border-dashed border-purple-400/50 rounded-2xl p-8 text-center hover:border-pink-400 hover:bg-white/5 transition-all duration-300">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="audio/*"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <Volume2 className="w-16 h-16 mx-auto mb-4 text-purple-300 group-hover:text-pink-300 transition-colors" />
                  <p className="text-purple-200 font-medium">
                    {audioFile ? audioFile.name : "Audio fayl tanlang"}
                  </p>
                  <p className="text-purple-300 text-sm mt-2">
                    MP3, WAV, M4A, FLAC
                  </p>
                </div>
              </div>
            </div>

            {/* Language Selection */}
            <div>
              <label className="block text-purple-200 font-semibold mb-3 flex items-center gap-2">
                <Languages className="w-5 h-5" />
                Tarjima tili
              </label>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                className="w-full bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl px-6 py-4 text-white font-medium focus:outline-none focus:ring-2 focus:ring-pink-400 transition-all"
              >
                {languages.map(lang => (
                  <option key={lang.code} value={lang.code} className="bg-purple-900">
                    {lang.name}
                  </option>
                ))}
              </select>

              <button
                onClick={handleProcess}
                disabled={!audioFile || isProcessing}
                className="w-full mt-6 bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 disabled:from-gray-500 disabled:to-gray-600 text-white font-bold py-4 px-8 rounded-2xl transition-all duration-300 transform hover:scale-105 disabled:scale-100 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-lg"
              >
                {isProcessing ? (
                  <>
                    <div className="w-5 h-5 border-3 border-white/30 border-t-white rounded-full animate-spin" />
                    Qayta ishlanmoqda...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Boshlash
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Karaoke Player */}
        {transcriptData.length > 0 && (
          <div className="bg-white/10 backdrop-blur-xl rounded-3xl p-8 border border-white/20 shadow-2xl animate-slideUp">
            <audio ref={audioRef} src={audioUrl} />
            
            {/* Current Lyric Display */}
            <div className="mb-8 min-h-[120px] flex items-center justify-center">
              <div className="text-center">
                {activeSegment ? (
                  <p className="text-3xl md:text-5xl font-bold text-white animate-pulse leading-relaxed px-4">
                    {activeSegment.text}
                  </p>
                ) : (
                  <p className="text-2xl text-purple-300/50 font-light italic">
                    Audio ijro etilmoqda...
                  </p>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div 
              onClick={handleSeek}
              className="relative h-3 bg-white/10 rounded-full mb-6 cursor-pointer group overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-pink-500/20 to-purple-500/20" />
              <div 
                className="absolute h-full bg-gradient-to-r from-pink-500 to-purple-600 rounded-full transition-all duration-100 shadow-lg shadow-pink-500/50"
                style={{ width: `${(currentTime / duration) * 100}%` }}
              />
              <div 
                className="absolute top-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ left: `${(currentTime / duration) * 100}%`, marginLeft: '-12px' }}
              />
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between mb-6">
              <span className="text-purple-200 font-mono">{formatTime(currentTime)}</span>
              <button
                onClick={togglePlay}
                className="bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white p-6 rounded-full transition-all duration-300 transform hover:scale-110 shadow-xl"
              >
                {isPlaying ? <Pause className="w-8 h-8" /> : <Play className="w-8 h-8 ml-1" />}
              </button>
              <span className="text-purple-200 font-mono">{formatTime(duration)}</span>
            </div>

            {/* Transcript List */}
            <div className="bg-black/20 rounded-2xl p-6 max-h-64 overflow-y-auto scrollbar-custom">
              {transcriptData.map((seg, idx) => (
                <div
                  key={idx}
                  onClick={() => audioRef.current && (audioRef.current.currentTime = seg.start)}
                  className={`p-4 rounded-xl mb-2 cursor-pointer transition-all duration-300 ${
                    activeSegment === seg
                      ? 'bg-gradient-to-r from-pink-500/30 to-purple-600/30 border border-pink-400/50 transform scale-105'
                      : 'bg-white/5 hover:bg-white/10 border border-transparent'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-purple-300 text-sm font-mono mt-1">
                      {formatTime(seg.start)}
                    </span>
                    <p className="text-white flex-1">{seg.text}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Download Button */}
            <button
              onClick={handleDownload}
              className="w-full mt-6 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold py-4 px-8 rounded-2xl transition-all duration-300 flex items-center justify-center gap-3"
            >
              <Download className="w-5 h-5" />
              Matnni yuklab olish (.txt)
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(40px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .animate-fadeIn {
          animation: fadeIn 0.8s ease-out;
        }
        
        .animate-slideUp {
          animation: slideUp 0.6s ease-out;
        }
        
        .scrollbar-custom::-webkit-scrollbar {
          width: 8px;
        }
        
        .scrollbar-custom::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 10px;
        }
        
        .scrollbar-custom::-webkit-scrollbar-thumb {
          background: linear-gradient(to bottom, #ec4899, #a855f7);
          border-radius: 10px;
        }
        
        .scrollbar-custom::-webkit-scrollbar-thumb:hover {
          background: linear-gradient(to bottom, #db2777, #9333ea);
        }
      `}</style>
    </div>
  );
};

export default ModernKaraokeApp;
