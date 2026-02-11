# ============================================================
#  J.A.R.V.I.S  –  Just A Rather Very Intelligent System
#  -----------------------------------------------------
#  Features
#    • Say "Jarvis"        → Welcome greeting
#    • Say "Jarvis open home" → Opens Spotify + VS Code
#    • Double-clap          → Opens Spotify + VS Code
# ============================================================

import os
import sys
import time
import subprocess
import threading

import pyttsx3
import speech_recognition as sr
import numpy as np
import sounddevice as sd

from config import (
    VSCODE_PATH,
    SPOTIFY_PATH,
    WAKE_WORD,
    VOICE_RATE,
    VOICE_VOLUME,
    CLAP_THRESHOLD,
    CLAP_COOLDOWN,
    DOUBLE_CLAP_WINDOW,
    SAMPLE_RATE,
    BLOCK_SIZE,
)

# ── TTS engine (runs on main thread) ────────────────────────
engine = pyttsx3.init()
engine.setProperty("rate", VOICE_RATE)
engine.setProperty("volume", VOICE_VOLUME)

# Pick a male voice if available
voices = engine.getProperty("voices")
for v in voices:
    if "male" in v.name.lower() or "david" in v.name.lower():
        engine.setProperty("voice", v.id)
        break


def speak(text: str) -> None:
    """Speak the given text aloud."""
    print(f"  [Jarvis] {text}")
    engine.say(text)
    engine.runAndWait()


# ── App Launcher ────────────────────────────────────────────
def open_home() -> None:
    """Open Spotify and VS Code (the 'home' setup)."""
    speak("Opening your home setup, sir.")

    for name, path in [("VS Code", VSCODE_PATH), ("Spotify", SPOTIFY_PATH)]:
        if os.path.exists(path):
            subprocess.Popen([path], shell=False)
            print(f"  [Jarvis] Launched {name}")
        else:
            # Fallback: try launching by name via start command (Windows)
            try:
                os.startfile(path)
                print(f"  [Jarvis] Launched {name} via startfile")
            except Exception:
                speak(f"Sorry sir, I could not find {name} at the configured path.")

    speak("Home is ready. Have a productive session!")


# ── Voice Listener ──────────────────────────────────────────
recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True


def listen_once(timeout: int = 5, phrase_limit: int = 5) -> str:
    """Capture one phrase from the mic and return lowercase text."""
    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            text = recognizer.recognize_google(audio).lower()
            return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"  [Jarvis] Speech API error: {e}")
            return ""


def voice_loop() -> None:
    """Continuously listen for voice commands."""
    print("\n  [Jarvis] Voice listener active. Say 'Jarvis' to begin.\n")
    while True:
        text = listen_once(timeout=None, phrase_limit=8)
        if not text:
            continue

        print(f"  [You] {text}")

        # ── "Jarvis open home" ──
        if WAKE_WORD in text and "open" in text and "home" in text:
            open_home()

        # ── Just "Jarvis" (greeting) ──
        elif WAKE_WORD in text:
            speak("Hello sir! Welcome back. Jarvis at your service. What would you like me to do?")


# ── Clap Detector ──────────────────────────────────────────
class ClapDetector:
    """Detect double-claps using the microphone's raw audio stream."""

    def __init__(self):
        self.last_clap_time: float = 0.0
        self.clap_count: int = 0

    def _audio_callback(self, indata, frames, time_info, status):
        amplitude = np.abs(indata).max()
        now = time.time()

        if amplitude > CLAP_THRESHOLD:
            if now - self.last_clap_time > CLAP_COOLDOWN:
                self.clap_count += 1
                self.last_clap_time = now
                print(f"  [Jarvis] Clap detected! (count={self.clap_count})")

    def run(self) -> None:
        print("  [Jarvis] Clap detector active. Double-clap to open home.\n")
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            callback=self._audio_callback,
        ):
            while True:
                time.sleep(0.1)

                if self.clap_count == 0:
                    continue

                # Wait to see if a second clap arrives within the window
                elapsed = time.time() - self.last_clap_time
                if self.clap_count >= 2:
                    print("  [Jarvis] Double clap recognised!")
                    self.clap_count = 0
                    open_home()
                elif elapsed > DOUBLE_CLAP_WINDOW:
                    # Single clap timed out – reset
                    self.clap_count = 0


# ── Banner ──────────────────────────────────────────────────
BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Just A Rather Very Intelligent System
"""


# ── Main ────────────────────────────────────────────────────
def main() -> None:
    print(BANNER)
    speak("Jarvis initialising. All systems online.")

    # Run voice listener in one thread, clap detector in another
    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    clap_thread = threading.Thread(target=ClapDetector().run, daemon=True)

    voice_thread.start()
    clap_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        speak("Goodbye sir. Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
