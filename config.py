# ============================================================
#  Jarvis Configuration
# ============================================================

# ---------- Paths (update these if your apps are elsewhere) ----------
VSCODE_PATH = r"C:\Users\NAMIT\AppData\Local\Programs\Microsoft VS Code\Code.exe"
SPOTIFY_PATH = r"C:\Users\NAMIT\AppData\Local\Microsoft\WindowsApps\Spotify.exe"

# ---------- Voice ----------
WAKE_WORD = "jarvis"
VOICE_RATE = 175          # words per minute (pyttsx3 fallback)
VOICE_VOLUME = 1.0        # 0.0 – 1.0

# Edge TTS (natural neural voice) — requires internet
EDGE_TTS_VOICE = "en-GB-RyanNeural"   # British accent like the real Jarvis
EDGE_TTS_RATE = "+30%"                 # Speed tweak
EDGE_TTS_PITCH = "+0Hz"               # Pitch tweak

# ---------- Audio Monitor ----------
SAMPLE_RATE = 44100        # audio sample rate
BLOCK_SIZE = 1024          # samples per audio block

# ---------- Spotify API (for "Jarvis play <song>") ----------
# One-time setup (2 minutes, free):
#   1. Go to  https://developer.spotify.com/dashboard
#   2. Click "Create App"  (name: Jarvis, redirect URI: http://localhost)
#   3. Copy Client ID and Client Secret below
SPOTIFY_CLIENT_ID = ""
SPOTIFY_CLIENT_SECRET = ""
