# ============================================================
#  Download all Jarvis voice responses (run once with internet)
#  After this, the app works fully offline.
# ============================================================

import os
import asyncio
import edge_tts
from config import EDGE_TTS_VOICE, EDGE_TTS_RATE, EDGE_TTS_PITCH

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "voice_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ALL_PHRASES = [
    # Greetings
    "At your service, sir.",
    "Hello sir. What can I do for you?",
    "Yes sir?",
    "Online and ready, sir.",
    "I'm here. What do you need?",
    "Sir. Sarcasm module loaded and ready.",
    "What shall we break today, sir?",
    "Awaiting orders, sir.",
    # Home openers
    "On it, sir.",
    "Firing up your workspace.",
    "Setting up, sir.",
    "Loading your setup.",
    "Right away, sir.",
    # Home ready
    "All set, sir.",
    "Done. You're welcome.",
    "Ready when you are.",
    "The stage is yours, sir.",
    "All yours. Do try to keep up.",
    # Error messages
    "Well this is embarrassing. I can't seem to find VS Code, sir.",
    "Well this is embarrassing. I can't seem to find Spotify, sir.",
    # Play prompt
    "What would you like me to play, sir?",
]


async def download_all():
    total = len(ALL_PHRASES)
    downloaded = 0
    skipped = 0

    for i, phrase in enumerate(ALL_PHRASES, 1):
        filename = f"jarvis_{hash(phrase) & 0xFFFFFFFF:08x}.mp3"
        filepath = os.path.join(CACHE_DIR, filename)

        if os.path.exists(filepath):
            skipped += 1
            print(f"  [{i}/{total}] SKIP  (cached) {phrase[:50]}")
            continue

        try:
            communicate = edge_tts.Communicate(
                phrase, voice=EDGE_TTS_VOICE,
                rate=EDGE_TTS_RATE, pitch=EDGE_TTS_PITCH,
            )
            await communicate.save(filepath)
            downloaded += 1
            print(f"  [{i}/{total}] OK    {phrase[:50]}")
        except Exception as e:
            print(f"  [{i}/{total}] FAIL  {phrase[:50]}  -> {e}")

    print(f"\nDone! Downloaded: {downloaded} | Already cached: {skipped}")
    print(f"Voice cache folder: {CACHE_DIR}")


if __name__ == "__main__":
    print("=" * 55)
    print("  J.A.R.V.I.S  Voice Downloader")
    print(f"  Voice : {EDGE_TTS_VOICE}")
    print(f"  Rate  : {EDGE_TTS_RATE}")
    print(f"  Pitch : {EDGE_TTS_PITCH}")
    print("=" * 55)
    print()
    asyncio.run(download_all())
