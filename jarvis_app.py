# ============================================================
#  J.A.R.V.I.S  –  GUI Application
#  Iron Man–style interface with system tray & auto-start
# ============================================================

import os
import sys
import time
import subprocess
import threading
import queue
import math
import random
import json
import base64
import webbrowser
from datetime import datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import asyncio

import customtkinter as ctk
import edge_tts
import pygame
import speech_recognition as sr
import numpy as np
import sounddevice as sd
from PIL import Image, ImageDraw, ImageFont

from config import (
    VSCODE_PATH,
    SPOTIFY_PATH,
    WAKE_WORD,
    VOICE_RATE,
    VOICE_VOLUME,
    SAMPLE_RATE,
    BLOCK_SIZE,
    EDGE_TTS_VOICE,
    EDGE_TTS_RATE,
    EDGE_TTS_PITCH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
)

# ── Paths ───────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "assets", "jarvis_icon.ico")

# ── Thread-safe log queue ───────────────────────────────────
log_queue: queue.Queue = queue.Queue()

# ── Colour palette (Iron Man vibes) ────────────────────────
BG_DARK      = "#0a0a0f"
BG_PANEL     = "#111118"
ACCENT_CYAN  = "#00d4ff"
ACCENT_GOLD  = "#f0c040"
TEXT_DIM     = "#5a5a6e"
TEXT_LIGHT   = "#c8c8d8"
RED_ALERT    = "#ff3040"
GREEN_OK     = "#30ff90"


# ====================================================================
#  JARVIS CORE  (engine that both GUI and headless mode share)
# ====================================================================
class JarvisCore:
    """Voice + clap engine running on background threads."""

    def __init__(self, on_log=None, on_status=None, on_amplitude=None, on_wake=None):
        self._on_log = on_log or (lambda *a: None)
        self._on_status = on_status or (lambda *a: None)
        self._on_amplitude = on_amplitude or (lambda *a: None)
        self._on_wake = on_wake or (lambda: None)

        self.running = False
        self._tts_queue: queue.Queue = queue.Queue()
        self._tts_lock = threading.Lock()

        # Pygame mixer for audio playback
        pygame.mixer.init()

        # Permanent voice cache (pre-downloaded, never re-fetched)
        self._tts_cache_dir = os.path.join(APP_DIR, "voice_cache")
        os.makedirs(self._tts_cache_dir, exist_ok=True)

        # Speech recogniser
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = 300
        self._recognizer.dynamic_energy_threshold = True

        # Spotify API token cache
        self._spotify_token = None
        self._spotify_token_expiry = 0.0

    # ── TTS via Edge Neural Voice ───────────────────────────
    def _tts_worker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.running:
            try:
                text = self._tts_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._on_log("jarvis", text)
            try:
                loop.run_until_complete(self._edge_speak(text))
            except Exception as e:
                self._on_log("error", f"TTS error: {e}")
        loop.close()

    async def _edge_speak(self, text: str):
        """Generate speech with Edge TTS and play it."""
        # Create a unique temp file for this utterance
        audio_file = os.path.join(
            self._tts_cache_dir,
            f"jarvis_{hash(text) & 0xFFFFFFFF:08x}.mp3"
        )
        # Generate audio if not cached
        if not os.path.exists(audio_file):
            communicate = edge_tts.Communicate(
                text,
                voice=EDGE_TTS_VOICE,
                rate=EDGE_TTS_RATE,
                pitch=EDGE_TTS_PITCH,
            )
            await communicate.save(audio_file)
        # Play audio
        with self._tts_lock:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)

    def speak(self, text: str):
        self._tts_queue.put(text)

    # ── Witty responses (like the real Jarvis) ────────────
    GREETINGS = [
        "At your service, sir.",
        "Hello sir. What can I do for you?",
        "Yes sir?",
        "Online and ready, sir.",
        "I'm here. What do you need?",
        "Sir. Sarcasm module loaded and ready.",
        "What shall we break today, sir?",
        "Awaiting orders, sir.",
    ]

    HOME_OPENERS = [
        "On it, sir.",
        "Firing up your workspace.",
        "Setting up, sir.",
        "Loading your setup.",
        "Right away, sir.",
    ]

    HOME_READY = [
        "All set, sir.",
        "Done. You're welcome.",
        "Ready when you are.",
        "The stage is yours, sir.",
        "All yours. Do try to keep up.",
    ]
    PLAY_RESPONSES = [
        "Playing {song} for you, sir.",
        "Queuing up {song}. Enjoy, sir.",
        "One {song} coming right up.",
        "{song}. Excellent choice, sir.",
        "On it. Playing {song}.",
    ]
    # ── App launcher ────────────────────────────────────
    def open_home(self):
        self.speak(random.choice(self.HOME_OPENERS))
        for name, path in [("VS Code", VSCODE_PATH), ("Spotify", SPOTIFY_PATH)]:
            try:
                if os.path.exists(path):
                    subprocess.Popen([path], shell=False)
                else:
                    os.startfile(path)
                self._on_log("system", f"Launched {name}")
            except Exception:
                self.speak(f"Well this is embarrassing. I can't seem to find {name}, sir.")
        self.speak(random.choice(self.HOME_READY))

    # ── Spotify play ────────────────────────────────────
    def _get_spotify_token(self):
        """Get a Spotify API access token (client-credentials flow)."""
        now = time.time()
        if self._spotify_token and now < self._spotify_token_expiry:
            return self._spotify_token
        auth = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        data = urlencode({"grant_type": "client_credentials"}).encode()
        req = Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={"Authorization": f"Basic {auth}"},
        )
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        self._spotify_token = result["access_token"]
        self._spotify_token_expiry = now + result.get("expires_in", 3600) - 60
        return self._spotify_token

    def _spotify_search_track(self, query: str):
        """Search Spotify for a track. Returns (uri, name, artist) or Nones."""
        token = self._get_spotify_token()
        params = urlencode({"q": query, "type": "track", "limit": 1})
        req = Request(
            f"https://api.spotify.com/v1/search?{params}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        tracks = data.get("tracks", {}).get("items", [])
        if tracks:
            t = tracks[0]
            return t["uri"], t["name"], t["artists"][0]["name"]
        return None, None, None

    def play_song(self, song_name: str):
        """Search Spotify for a song and play it."""
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            self.speak("I need Spotify API credentials to play music, sir. Check config.")
            self._on_log("error", "Set SPOTIFY_CLIENT_ID & SECRET in config.py")
            return
        try:
            uri, track_name, artist = self._spotify_search_track(song_name)
            if uri:
                self.speak(random.choice(self.PLAY_RESPONSES).format(
                    song=f"{track_name} by {artist}"
                ))
                os.startfile(uri)  # opens spotify:track:XXX → auto-plays
                self._on_log("system", f"Playing: {track_name} by {artist}")
            else:
                self.speak(f"I couldn't find {song_name} on Spotify, sir.")
        except Exception as e:
            self._on_log("error", f"Spotify API error: {e}")
            # Fallback: open search in Spotify
            try:
                os.startfile(f"spotify:search:{quote(song_name)}")
            except Exception:
                webbrowser.open(f"https://open.spotify.com/search/{quote(song_name)}")

    # ── Voice loop ──────────────────────────────────────────
    def _voice_loop(self):
        self._on_log("system", "Voice listener active")
        self._on_status("voice", True)
        while self.running:
            try:
                with sr.Microphone() as source:
                    try:
                        audio = self._recognizer.listen(
                            source, timeout=2, phrase_time_limit=5
                        )
                    except sr.WaitTimeoutError:
                        continue

                # Try to recognise — do NOT touch clap state here
                try:
                    text = self._recognizer.recognize_google(audio).lower()
                except (sr.UnknownValueError, sr.RequestError):
                    continue

                if not text:
                    continue

                self._on_log("user", text)

                if WAKE_WORD in text and "open" in text and "home" in text:
                    self._on_wake()
                    self.open_home()
                elif WAKE_WORD in text and "play" in text:
                    # Extract song name after "play"
                    parts = text.split("play", 1)
                    song = parts[1].strip() if len(parts) > 1 else ""
                    if song:
                        self._on_wake()
                        self.play_song(song)
                    else:
                        self._on_wake()
                        self.speak("What would you like me to play, sir?")
                elif WAKE_WORD in text:
                    self._on_wake()
                    self.speak(random.choice(self.GREETINGS))
            except Exception as e:
                self._on_log("error", f"Voice error: {e}")
                time.sleep(2)

    # ── Audio monitor (feeds UI waveform & reactor) ───────
    def _audio_callback(self, indata, frames, time_info, status):
        amplitude = float(np.abs(indata).max())
        self._on_amplitude(amplitude)

    def _audio_monitor_loop(self):
        self._on_log("system", "Audio monitor active")
        self._on_status("audio", True)
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                channels=1,
                callback=self._audio_callback,
            ):
                while self.running:
                    time.sleep(0.1)
        except Exception as e:
            self._on_log("error", f"Audio monitor error: {e}")
            self._on_status("audio", False)

    # ── Start / Stop ────────────────────────────────────────
    def start(self):
        self.running = True
        threading.Thread(target=self._tts_worker, daemon=True).start()
        threading.Thread(target=self._voice_loop, daemon=True).start()
        threading.Thread(target=self._audio_monitor_loop, daemon=True).start()
        threading.Thread(target=self._precache_responses, daemon=True).start()
        self._on_log("system", "Jarvis online. Listening silently…")

    def _precache_responses(self):
        """Check if all responses are cached, download any missing ones."""
        all_phrases = self.GREETINGS + self.HOME_OPENERS + self.HOME_READY + [
            "Well this is embarrassing. I can't seem to find VS Code, sir.",
            "Well this is embarrassing. I can't seem to find Spotify, sir.",
            "What would you like me to play, sir?",
        ]
        missing = []
        for phrase in all_phrases:
            audio_file = os.path.join(
                self._tts_cache_dir,
                f"jarvis_{hash(phrase) & 0xFFFFFFFF:08x}.mp3"
            )
            if not os.path.exists(audio_file):
                missing.append((phrase, audio_file))

        if not missing:
            self._on_log("system", "Voice cache loaded. All responses ready.")
            return

        self._on_log("system", f"Downloading {len(missing)} missing voice files…")
        loop = asyncio.new_event_loop()
        for phrase, audio_file in missing:
            try:
                communicate = edge_tts.Communicate(
                    phrase, voice=EDGE_TTS_VOICE,
                    rate=EDGE_TTS_RATE, pitch=EDGE_TTS_PITCH,
                )
                loop.run_until_complete(communicate.save(audio_file))
            except Exception:
                pass
        loop.close()
        self._on_log("system", "Voice cache ready.")

    def stop(self):
        self.running = False


# ====================================================================
#  SYSTEM TRAY  (pystray – so Jarvis lives in the taskbar)
# ====================================================================
def create_tray_icon(show_cb, quit_cb):
    """Create a system-tray icon. Returns the Icon object."""
    import pystray
    from pystray import MenuItem, Menu

    # Generate a simple icon programmatically
    img = Image.new("RGBA", (64, 64), (10, 10, 15, 255))
    draw = ImageDraw.Draw(img)
    # Cyan arc
    draw.ellipse([8, 8, 56, 56], outline=(0, 212, 255, 255), width=3)
    # "J" letter
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 12), "J", fill=(0, 212, 255, 255), font=font)

    icon = pystray.Icon(
        "Jarvis",
        img,
        "J.A.R.V.I.S",
        menu=Menu(
            MenuItem("Show Jarvis", show_cb, default=True),
            MenuItem("Quit", quit_cb),
        ),
    )
    return icon


# ====================================================================
#  ANIMATED ARC REACTOR CANVAS  (pure tkinter drawing)
# ====================================================================
class ArcReactorCanvas(ctk.CTkCanvas):
    """Full-size animated HUD with arc reactor, scanning rings, and waveform."""

    def __init__(self, master, size=280, **kw):
        super().__init__(master, width=size, height=size,
                         bg=BG_DARK, highlightthickness=0, **kw)
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.angle = 0
        self.angle2 = 0
        self.amplitude = 0.0
        self.pulse = 0
        self.wave_data = [0.0] * 40
        self._animate()

    def set_amplitude(self, amp: float):
        self.amplitude = min(amp, 1.0)
        self.wave_data.pop(0)
        self.wave_data.append(amp)

    def _animate(self):
        self.delete("all")
        s = self.size
        cx, cy = self.cx, self.cy
        self.pulse = (self.pulse + 1) % 100
        pulse_val = abs(math.sin(self.pulse * 0.06))

        # ── Outer faint rings (HUD radar style) ──
        for i in range(5):
            r = s // 2 - 6 - i * 4
            alpha_hex = max(15, 40 - i * 8)
            col = f"#00{alpha_hex + 30:02x}{alpha_hex + 50:02x}"
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=col, width=1)

        # ── Outer spinning ring 1 (clockwise) ──
        r1 = s // 2 - 20
        for i in range(4):
            start = self.angle + i * 90
            self.create_arc(cx - r1, cy - r1, cx + r1, cy + r1,
                            start=start, extent=50,
                            outline="#00a0d0", width=2, style="arc")

        # ── Outer spinning ring 2 (counter-clockwise) ──
        r1b = s // 2 - 30
        for i in range(6):
            start = -self.angle2 + i * 60
            self.create_arc(cx - r1b, cy - r1b, cx + r1b, cy + r1b,
                            start=start, extent=25,
                            outline="#006090", width=1, style="arc")

        # ── Main reactor ring ──
        r2 = s // 2 - 45
        glow = int(140 + self.amplitude * 115)
        ring_col = f"#00{min(glow, 255):02x}ff"
        self.create_oval(cx - r2, cy - r2, cx + r2, cy + r2,
                         outline=ring_col, width=3)

        # ── Tick marks around the ring ──
        r_tick_out = r2 + 2
        r_tick_in = r2 - 6
        for i in range(36):
            a = math.radians(i * 10)
            x1 = cx + r_tick_out * math.cos(a)
            y1 = cy + r_tick_out * math.sin(a)
            x2 = cx + r_tick_in * math.cos(a)
            y2 = cy + r_tick_in * math.sin(a)
            tick_col = "#00607a" if i % 3 != 0 else "#00b8e0"
            self.create_line(x1, y1, x2, y2, fill=tick_col, width=1)

        # ── Inner spinning triangular segments ──
        r3 = s // 2 - 70
        for i in range(3):
            ang = math.radians(self.angle * 1.5 + i * 120)
            px = cx + r3 * math.cos(ang)
            py = cy + r3 * math.sin(ang)
            tri_size = 8
            points = [
                px + tri_size * math.cos(ang),
                py + tri_size * math.sin(ang),
                px + tri_size * math.cos(ang + 2.3),
                py + tri_size * math.sin(ang + 2.3),
                px + tri_size * math.cos(ang - 2.3),
                py + tri_size * math.sin(ang - 2.3),
            ]
            self.create_polygon(points, fill="#00c8ff", outline="")

        # ── Audio waveform ring ──
        r_wave = s // 2 - 58
        points_wave = []
        for idx, val in enumerate(self.wave_data):
            a = math.radians(idx * (360 / len(self.wave_data)))
            wave_r = r_wave + val * 18
            x = cx + wave_r * math.cos(a)
            y = cy + wave_r * math.sin(a)
            points_wave.extend([x, y])
        if len(points_wave) >= 6:
            self.create_line(*points_wave, fill="#00e8ff", width=1, smooth=True)

        # ── Inner glow disc ──
        r4 = 35
        brightness = int(40 + self.amplitude * 160 + pulse_val * 30)
        inner_col = f"#00{min(brightness, 255):02x}{min(brightness + 30, 255):02x}"
        self.create_oval(cx - r4, cy - r4, cx + r4, cy + r4,
                         fill=inner_col, outline="#00a0c0", width=1)

        # ── Inner ring ──
        r5 = 25
        self.create_oval(cx - r5, cy - r5, cx + r5, cy + r5,
                         outline="#00e0ff", width=2)

        # ── Pulsing core ──
        r6 = int(10 + pulse_val * 4)
        self.create_oval(cx - r6, cy - r6, cx + r6, cy + r6,
                         fill="#60f0ff", outline="")

        # ── White hot centre ──
        r7 = 4
        self.create_oval(cx - r7, cy - r7, cx + r7, cy + r7,
                         fill="#ffffff", outline="")

        # ── Decorative corner brackets (HUD feel) ──
        bk = 20
        bk_col = "#004060"
        # top-left
        self.create_line(4, 4, 4, 4 + bk, fill=bk_col, width=1)
        self.create_line(4, 4, 4 + bk, 4, fill=bk_col, width=1)
        # top-right
        self.create_line(s - 4, 4, s - 4, 4 + bk, fill=bk_col, width=1)
        self.create_line(s - 4, 4, s - 4 - bk, 4, fill=bk_col, width=1)
        # bottom-left
        self.create_line(4, s - 4, 4, s - 4 - bk, fill=bk_col, width=1)
        self.create_line(4, s - 4, 4 + bk, s - 4, fill=bk_col, width=1)
        # bottom-right
        self.create_line(s - 4, s - 4, s - 4, s - 4 - bk, fill=bk_col, width=1)
        self.create_line(s - 4, s - 4, s - 4 - bk, s - 4, fill=bk_col, width=1)

        self.angle = (self.angle + 1.2) % 360
        self.angle2 = (self.angle2 + 0.7) % 360
        self.after(33, self._animate)


# ====================================================================
#  AUDIO WAVEFORM BAR
# ====================================================================
class WaveformBar(ctk.CTkCanvas):
    """Horizontal audio waveform visualiser."""

    def __init__(self, master, width=420, height=40, **kw):
        super().__init__(master, width=width, height=height,
                         bg=BG_DARK, highlightthickness=0, **kw)
        self.w = width
        self.h = height
        self.bars = [0.0] * 50
        self._draw()

    def push(self, amp: float):
        self.bars.pop(0)
        self.bars.append(min(amp, 1.0))

    def _draw(self):
        self.delete("all")
        bar_w = self.w / len(self.bars)
        mid = self.h // 2
        for i, val in enumerate(self.bars):
            x = i * bar_w
            h = max(1, val * mid * 0.9)
            brightness = int(80 + val * 175)
            col = f"#00{min(brightness, 255):02x}{min(brightness + 30, 255):02x}"
            self.create_rectangle(x + 1, mid - h, x + bar_w - 1, mid + h,
                                  fill=col, outline="")
        # Centre line
        self.create_line(0, mid, self.w, mid, fill="#002535", width=1)
        self.after(60, self._draw)


# ====================================================================
#  MAIN GUI WINDOW
# ====================================================================
class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Window setup ────────────────────────────────────
        self.title("J.A.R.V.I.S")
        self.geometry("560x820")
        self.minsize(500, 750)
        self.configure(fg_color=BG_DARK)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Set icon if available
        if os.path.exists(ICON_PATH):
            self.iconbitmap(ICON_PATH)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── State ───────────────────────────────────────────
        self.core: JarvisCore | None = None
        self.tray_icon = None
        self._voice_ok = False
        self._audio_ok = False

        self._build_ui()

    # ── Build UI ────────────────────────────────────────────
    def _build_ui(self):
        # ─── TOP HEADER BAR ─────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="#06060c", corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        left_line = ctk.CTkFrame(header, fg_color=ACCENT_CYAN, width=3, height=30,
                                  corner_radius=2)
        left_line.pack(side="left", padx=(16, 8), pady=11)

        ctk.CTkLabel(
            header, text="J . A . R . V . I . S",
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=ACCENT_CYAN,
        ).pack(side="left")

        self.clock_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM,
        )
        self.clock_label.pack(side="right", padx=16)
        self._tick_clock()

        # Thin cyan line under header
        ctk.CTkFrame(self, fg_color="#003545", height=1, corner_radius=0).pack(fill="x")

        # ─── ARC REACTOR ─────────────────────────────────────
        reactor_frame = ctk.CTkFrame(self, fg_color=BG_DARK)
        reactor_frame.pack(pady=(10, 0))
        self.reactor = ArcReactorCanvas(reactor_frame, size=280)
        self.reactor.pack()

        # ─── STATUS ROW ──────────────────────────────────────
        status_row = ctk.CTkFrame(self, fg_color=BG_DARK)
        status_row.pack(pady=(6, 2))

        # Status badge
        self.status_badge = ctk.CTkFrame(status_row, fg_color="#1a0a0a",
                                          corner_radius=12, height=28)
        self.status_badge.pack(side="left", padx=8)
        self.status_label = ctk.CTkLabel(
            self.status_badge, text="  ● OFFLINE  ",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=RED_ALERT,
        )
        self.status_label.pack(padx=8, pady=2)

        # Voice indicator
        self.voice_dot = ctk.CTkLabel(
            status_row, text="◈ VOICE",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=TEXT_DIM,
        )
        self.voice_dot.pack(side="left", padx=14)

        # Audio indicator
        self.audio_dot = ctk.CTkLabel(
            status_row, text="◈ AUDIO",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=TEXT_DIM,
        )
        self.audio_dot.pack(side="left", padx=14)

        # ─── WAVEFORM ────────────────────────────────────────
        wave_frame = ctk.CTkFrame(self, fg_color=BG_DARK)
        wave_frame.pack(pady=(8, 2), padx=30, fill="x")
        ctk.CTkLabel(
            wave_frame, text="AUDIO INPUT",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color="#003545",
        ).pack(anchor="w", padx=4)
        self.waveform = WaveformBar(wave_frame, width=480, height=36)
        self.waveform.pack(fill="x", padx=2)

        # ─── LOG AREA ────────────────────────────────────────
        log_frame = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=12,
                                  border_width=1, border_color="#0d2a38")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(10, 8))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent", height=28)
        log_header.pack(fill="x", padx=12, pady=(8, 0))
        log_header.pack_propagate(False)
        ctk.CTkLabel(
            log_header, text="◆ ACTIVITY LOG",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#006080",
        ).pack(side="left")

        self.log_box = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0a12", text_color=TEXT_LIGHT,
            corner_radius=8, border_width=0,
            wrap="word", state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # ─── BUTTONS ─────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color=BG_DARK)
        btn_frame.pack(pady=(0, 6))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶  ENGAGE", width=140, height=42,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            fg_color="#0a2a3d", hover_color="#0d3a55",
            text_color=ACCENT_CYAN, corner_radius=10,
            border_width=1, border_color="#00506a",
            command=self._toggle_engine,
        )
        self.start_btn.pack(side="left", padx=6)

        self.home_btn = ctk.CTkButton(
            btn_frame, text="⚡ OPEN HOME", width=155, height=42,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            fg_color="#2a1a05", hover_color="#3d2808",
            text_color=ACCENT_GOLD, corner_radius=10,
            border_width=1, border_color="#604010",
            command=self._manual_open_home,
        )
        self.home_btn.pack(side="left", padx=6)

        self.minimize_btn = ctk.CTkButton(
            btn_frame, text="▼ TRAY", width=90, height=42,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            fg_color="#0e0e16", hover_color="#1a1a28",
            text_color=TEXT_DIM, corner_radius=10,
            border_width=1, border_color="#1a1a2a",
            command=self._minimize_to_tray,
        )
        self.minimize_btn.pack(side="left", padx=6)

        # ─── BOTTOM BAR ──────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="#06060c", corner_radius=0, height=30)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        ctk.CTkFrame(self, fg_color="#003545", height=1, corner_radius=0).pack(
            fill="x", side="bottom")
        ctk.CTkLabel(
            bottom,
            text="  ◆ Namit-07/Jarvis  │  Say 'Jarvis' or 'Jarvis play <song>'  │  v3.0",
            font=ctk.CTkFont(family="Consolas", size=9), text_color="#2a2a3a",
        ).pack(side="left", padx=8)

        # Poll log queue
        self._poll_logs()

    # ── Clock ───────────────────────────────────────────────
    def _tick_clock(self):
        now = datetime.now().strftime("%H:%M:%S  •  %d %b %Y")
        self.clock_label.configure(text=now)
        self.after(1000, self._tick_clock)

    # ── Logging ─────────────────────────────────────────────
    def _log(self, tag: str, msg: str):
        log_queue.put((tag, msg))

    def _poll_logs(self):
        while not log_queue.empty():
            tag, msg = log_queue.get_nowait()
            self._append_log(tag, msg)
        self.after(150, self._poll_logs)

    def _append_log(self, tag: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix_map = {
            "jarvis": ("JARVIS", ACCENT_CYAN),
            "user":   ("  YOU ", ACCENT_GOLD),
            "system": (" SYS  ", TEXT_DIM),
            "error":  ("ERROR ", RED_ALERT),
        }
        prefix, color = prefix_map.get(tag, ("INFO", TEXT_LIGHT))

        self.log_box.configure(state="normal")
        line = f"[{ts}] [{prefix}]  {msg}\n"
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ── Status updates (called from core threads) ───────────
    def _on_status(self, subsystem: str, ok: bool):
        if subsystem == "voice":
            self._voice_ok = ok
        elif subsystem == "audio":
            self._audio_ok = ok
        # Schedule UI update on main thread
        self.after(0, self._refresh_indicators)

    def _refresh_indicators(self):
        self.voice_dot.configure(text_color=GREEN_OK if self._voice_ok else TEXT_DIM)
        self.audio_dot.configure(text_color=GREEN_OK if self._audio_ok else TEXT_DIM)
        if self._voice_ok or self._audio_ok:
            self.status_label.configure(text="  ● ONLINE  ", text_color=GREEN_OK)
            self.status_badge.configure(fg_color="#0a1a0a")

    def _on_amplitude(self, amp: float):
        self.reactor.set_amplitude(amp)
        self.waveform.push(amp)

    # ── Engine toggle ───────────────────────────────────────
    def _toggle_engine(self):
        if self.core and self.core.running:
            self.core.stop()
            self.core = None
            self.start_btn.configure(text="▶  ENGAGE", fg_color="#0a2a3d",
                                     text_color=ACCENT_CYAN)
            self.status_label.configure(text="  ● OFFLINE  ", text_color=RED_ALERT)
            self.status_badge.configure(fg_color="#1a0a0a")
            self._voice_ok = self._audio_ok = False
            self._refresh_indicators()
            self._log("system", "Jarvis stopped.")
        else:
            self.core = JarvisCore(
                on_log=self._log,
                on_status=self._on_status,
                on_amplitude=self._on_amplitude,
                on_wake=self._on_wake_word,
            )
            self.core.start()
            self.start_btn.configure(text="■  DISENGAGE", fg_color="#3d0d0d",
                                     text_color=RED_ALERT)
            self._log("system", "Jarvis starting up…")

    def _manual_open_home(self):
        if self.core and self.core.running:
            threading.Thread(target=self.core.open_home, daemon=True).start()
        else:
            self._log("system", "Start Jarvis first.")

    # ── System Tray ─────────────────────────────────────────
    def _minimize_to_tray(self):
        self.withdraw()  # hide window
        if not self.tray_icon:
            self.tray_icon = create_tray_icon(
                show_cb=lambda icon, item: self._show_from_tray(),
                quit_cb=lambda icon, item: self._quit_from_tray(),
            )
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self._log("system", "Minimised to system tray.")

    def _show_from_tray(self):
        self.after(0, self._bring_to_front)

    def _on_wake_word(self):
        """Called when the wake word is detected — pop up the GUI."""
        self.after(0, self._bring_to_front)

    def _bring_to_front(self):
        """Show window and bring it to the foreground."""
        self.deiconify()
        self.lift()
        self.attributes('-topmost', True)
        self.after(800, lambda: self.attributes('-topmost', False))
        self.focus_force()

    def _quit_from_tray(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self._force_quit)

    # ── Close / quit ────────────────────────────────────────
    def _on_close(self):
        """Minimize to tray instead of quitting."""
        self._minimize_to_tray()

    def _force_quit(self):
        if self.core:
            self.core.stop()
        self.destroy()
        sys.exit(0)


# ====================================================================
#  AUTO-START HELPER  (adds / removes a Windows Startup shortcut)
# ====================================================================
def _get_startup_shortcut_path() -> str:
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    return os.path.join(startup_dir, "Jarvis.lnk")


def enable_autostart():
    """Create a Windows shortcut in the Startup folder."""
    try:
        import winreg
        # Use a registry Run key (simpler, no COM dependency)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        python = sys.executable
        script = os.path.join(APP_DIR, "jarvis_app.py")
        cmd = f'"{python}" "{script}" --background'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "Jarvis", 0, winreg.REG_SZ, cmd)
        print("[Jarvis] Auto-start enabled via Registry.")
        return True
    except Exception as e:
        print(f"[Jarvis] Could not enable auto-start: {e}")
        return False


def disable_autostart():
    """Remove the Startup registry entry."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "Jarvis")
        print("[Jarvis] Auto-start disabled.")
        return True
    except Exception as e:
        print(f"[Jarvis] Could not disable auto-start: {e}")
        return False


# ====================================================================
#  ENTRY POINT
# ====================================================================
def main():
    # Handle --autostart / --no-autostart flags
    if "--enable-autostart" in sys.argv:
        enable_autostart()
        return
    if "--disable-autostart" in sys.argv:
        disable_autostart()
        return

    app = JarvisApp()

    # Always auto-start the engine so Jarvis begins listening immediately
    app.after(500, app._toggle_engine)

    # If launched from Windows startup, also minimize to tray
    if "--background" in sys.argv:
        app.after(800, app._minimize_to_tray)

    app.mainloop()


if __name__ == "__main__":
    main()
