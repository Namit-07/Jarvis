# J.A.R.V.I.S 🤖

> *Just A Rather Very Intelligent System* — your personal laptop assistant, inspired by Iron Man.

## Features

| Trigger | Action |
|---|---|
| Say **"Jarvis"** | Welcome greeting via voice |
| Say **"Jarvis open home"** | Opens Spotify + VS Code |
| **Double clap** 👏👏 | Opens Spotify + VS Code |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `PyAudio` may need extra steps on Windows. If `pip install PyAudio` fails, grab the wheel from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio) or run `pip install pipwin && pipwin install pyaudio`.

### 2. Update paths (if needed)

Open `config.py` and verify:

- `VSCODE_PATH` — path to `Code.exe`
- `SPOTIFY_PATH` — path to `Spotify.exe`

### 3. Run Jarvis

```bash
python jarvis.py
```

### 4. Talk to Jarvis

- Say **"Jarvis"** → hear a greeting
- Say **"Jarvis open home"** → Spotify + VS Code launch
- **Double-clap** → same as "open home"

Press `Ctrl + C` to shut down.

## Configuration

All tunables live in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `CLAP_THRESHOLD` | `0.6` | How loud a clap must be (0–1) |
| `DOUBLE_CLAP_WINDOW` | `1.0 s` | Max gap between two claps |
| `VOICE_RATE` | `175` | Speech speed (words/min) |

## Project Structure

```
Jarvis/
├── jarvis.py          # Main entry point
├── config.py          # All settings & paths
├── requirements.txt   # Python dependencies
└── README.md
```

## License

See `LICENSE` file.
