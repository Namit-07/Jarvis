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
# Popular voices:
#   en-US-GuyNeural       → Deep, confident male (perfect for Jarvis)
#   en-US-ChristopherNeural → Warm male
#   en-US-EricNeural      → Authoritative male
#   en-GB-RyanNeural      → British male (like the real Jarvis!)
#   en-US-JennyNeural     → Female alternative
EDGE_TTS_VOICE = "en-GB-RyanNeural"   # British accent like the real Jarvis
EDGE_TTS_RATE = "+18%"                 # Speed tweak: "+10%", "-5%", etc.
EDGE_TTS_PITCH = "+0Hz"               # Pitch tweak: "+5Hz", "-2Hz", etc.

# ---------- Clap Detection ----------
CLAP_THRESHOLD = 0.85     # amplitude spike to count as a clap (0‑1) — raise if false triggers
CLAP_COOLDOWN = 0.5       # seconds to ignore after a clap (avoid double-fire)
DOUBLE_CLAP_WINDOW = 0.8  # max gap between two claps to register as "double clap"
SAMPLE_RATE = 44100        # audio sample rate
BLOCK_SIZE = 1024          # samples per audio block
