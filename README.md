# DJ ALYX — Neural Radio Station

**Listen live:** [https://djalyx.2077911.xyz/](https://djalyx.2077911.xyz/)
**Stream For Mobile:** [https://djalyx.2077911.xyz/mobile](https://djalyx.2077911.xyz/mobile)
**Listeners map:** [https://djalyx.2077911.xyz/listeners/](https://djalyx.2077911.xyz/listeners/)
**Icecast admin:** [https://djalyx.2077911.xyz/icecast/admin/](https://djalyx.2077911.xyz/icecast/admin/)

AI-powered radio station with a neural DJ. Plays music from a local collection, generates live commentary via LLM, and voices it with neural TTS.

<details>
<summary>Нажмите, чтобы развернуть</summary>

- О музыке: локальная коллекция 76 Гб, IDM, DarkSynth, ChipTune.
- Станция в разработке, любые отзывы, предложения по улучшению и даже желаемую музыку в ротацию можно и нужно отправлять на адрес stend003@yandex.ru
- Может прерываться, зависать, внезапно выключаться, сейчас радио не в потребительском состоянии.
- Серверы оплачены на 3 месяца, дальше будет видно.

![Elvis](images/Gemini_Generated_Image_taeymrtaeymrtaey.png)

</details>

---

## Status

Development active. Station is online but not 24/7. Schedule is being formed.

## Features

- **Neural DJ** — Alyx selects tracks (BPM-based, time-of-day aware), writes commentary via LM Studio, voices via F5-TTS
- **News integration** — every 10 tracks reads 3 latest IT/tech news from Xakep.ru, rephrased by LM Studio
- **BPM scheduling** — morning (100-130), day (80-110), evening (70-100), night (60-90)
- **Time-of-day voice style** — DJ prompts change by hour: energetic mornings, calm nights
- **Digits-to-words** — all numbers in speech converted to Russian words for clean TTS
- **Web interface** — xterm.js terminal with live logs, ON AIR badge, volume slider, auto-reconnect
- **Icecast streaming** — MP3 @ 32-128 kbps via remote Icecast + nginx, listeners bypass home connection
- **EZstream push** — auto-reconnect on network drops, watchdog restarts on 3 consecutive failures
- **Fault tolerance** — `_restart_all()` kills all stale processes, `start_all.py` limits restarts 5/hour

## Architecture

```
Local machine                    Remote server (firstbyte)
┌────────────────────┐           ┌───────────────────────────────┐
│ play_music.py      │  push via │ Icecast :8000                 │
│  → PCM pipe        │──ezstream→│ nginx :80/443                 │
│  → ffmpeg encode   │  TCP      │  ├── /stream/ → Icecast    → listeners
│  → ezstream push   │           │  ├── /mobile/  → Django    → mobile UI
│                    │           │  └── /         → Django    → terminal UI
│ LM Studio :1234    │           │ Django (uvicorn) + Redis    │
│ F5-TTS (CPU TTS)   │           │ PostgreSQL (channel layer)  │
│ News DB (SQLite)   │           │ Let's Encrypt (HTTPS)       │
└────────────────────┘           └───────────────────────────────┘
```

## Quick Start

```bash
# Start radio station (supervised, auto-restart on crash)
python3 start_all.py

# With FM transmitter (HackRF on 95 MHz)
python3 start_all.py --fm

# Full stop
bash tools/shutdown_all.sh

# Full restart (kill everything + fresh start)
bash tools/restart_all.sh
```

## Recovery

- **3 consecutive drain failures** → `_restart_all()` → kills ezstream + ffmpeg, play_music exits
- **`start_all.py`** detects exit → restarts play_music (max 5 attempts per hour)
- **EZstream** auto-reconnects on network drops
- **Cron** (optional) checks `/api/status/` and restarts start_all if needed

## Commands

| Action | Command |
|--------|---------|
| Start radio | `python3 start_all.py` |
| Start with FM | `python3 start_all.py --fm` |
| Stop gracefully | `bash tools/shutdown_all.sh` |
| Full restart | `bash tools/restart_all.sh` |
| Collect news | `python3 tools/xakep_xml_parser.py` |
| Listener map (local) | `python3 tools/listener_map.html` |
| Network monitor | `python3 tools/network_monitor.py` |
| Bump version | `sh tools/bump_version.sh` |

## Stack

- Python 3.11+ / asyncio
- F5-TTS (neural voice synthesis, CPU)
- LM Studio (local LLM, Gemma 4)
- EZstream (Icecast push client with auto-reconnect)
- Django 5 + Channels + Uvicorn (web interface)
- Icecast 2.4 + nginx (audio streaming)
- SQLite (music DB, news DB)
- GNU Radio + HackRF (optional FM transmitter)

## Project Structure

```
dj_alyx/
├── play_music.py         # main radio orchestrator
├── start_all.py          # supervisor (restarts on crash, limit 5/h)
├── ai_connector.py       # LLM speech generation
├── voice_engine.py       # TTS voice synthesis via F5-TTS
├── last_fm.py            # artist info (blocked in RU, offline fallback)
├── journal_prompt_generic.py  # LLM prompts
├── fm.py                 # GNU Radio FM transmitter (optional)
├── tools/
│   ├── ezstream.xml.template  # ezstream config template
│   ├── restart_all.sh         # full restart script
│   ├── shutdown_all.sh        # graceful stop script
│   ├── network_monitor.py     # Icecast connectivity diagnostics
│   ├── xakep_xml_parser.py    # news parser
│   └── bump_version.sh        # auto-increment VERSION
├── django-aws-terminal-websocket/  # Django web service
│   ├── vmwebsocket/      # Django project
│   └── terminal/         # WebSocket + xterm.js
├── VERSION               # current version (1.1.9)
├── FEATURES.md           # feature backlog
├── AGENTS.md             # AI agent instructions
└── maxmind/              # GeoIP tools (local only, gitignored)
```

## License

MIT
