# 🌸 Makima AI Assistant

A modular, self-learning, bilingual (English/Hindi) AI assistant with voice I/O, persistent memory, cloud sync, remote control, and a multi-backend AI engine.

---

## ✨ Features

| Module | Description |
|--------|-------------|
| 🧠 **AI Engine** | Auto-switches between Google Gemini (online) and Ollama (offline) |
| 🎙️ **Voice I/O** | Wake word activation ("Hey Makima"), bilingual speech recognition, offline TTS |
| 🧬 **Self-Learning** | Writes, verifies, and hot-loads new Python skills at runtime |
| 🗄️ **Eternal Memory** | TF-IDF semantic search across all past conversations |
| 🎵 **Spotify Control** | Play, pause, skip, search tracks via Spotify Web API |
| 📱 **App Control** | Fuzzy-matched open/close for any installed app |
| 🖥️ **System Commands** | Volume, lock, screenshot, CPU/RAM/battery, window management |
| 📡 **Telegram Remote** | Full command access from anywhere via Telegram bot |
| 🌐 **Web Dashboard** | Browser UI at localhost:8000 for LAN control |
| ☁️ **Cloud Sync** | Auto-syncs memories to Google Drive every 12 hours |
| 🔒 **Security Scanner** | Voice-triggered Windows Defender / ClamAV scans |
| 🎯 **Focus Mode** | Auto-kills distracting apps on a timer |
| ⌨️ **Macros** | Record and replay keyboard/mouse sequences |
| 📅 **Reminders** | Time-based spoken alerts with natural language parsing |
| 🌐 **Web Agent** | DuckDuckGo instant answers + browser fallback |
| 🤖 **Auto Coder** | Generates and runs Python scripts on demand |
| 📋 **Clipboard Monitor** | Detects copied URLs and offers to open them |
| 🔋 **Battery Monitor** | Alerts at < 20% battery |
| 🖼️ **Overlay** | Semi-transparent on-screen display of Makima's responses |
| 👥 **3 Personas** | Makima, Normal, Date mode with auto-language detection |
| 🖥️ **Electron UI** | Rich Desktop HUD and command center interface |
| 🎮 **Proactive Engine** | Makima can initiate actions autonomously |
| 👁️ **Vision & Screen** | Screen reading capabilities and Face/Emotion tracking |
| 🌐 **Web Downloader** | Autonomous web search and Scrapy downloading |
| 📱 **App Learner** | Autonomously learns how to use new applications |
| 🎵 **Media & Music** | Spotify, YouTube playback, and intelligent Music DJ |
| 💬 **Communication** | WhatsApp automation and Email management |
| 📅 **Productivity** | Calendar tracking, File manager, Meeting assistant, Hotkeys |
| ❤️ **Personal Care** | Health data tracker and Mood monitoring |
| 📡 **Remote Control** | Full command access from anywhere via Telegram bot/Web UI |
| ⌨️ **System Mastery** | Macros, fuzzy app matching, Focus Mode blocking, Battery alerts |
| 🔒 **Security / Cloud** | Voice-triggered Defender scans, hourly Google Drive sync |

---

### Advanced Capabilities (Experimental)
*   **Translation Engine**: Real-time multi-language translation.
*   **Self-Updater**: System auto-updates components.
*   **Quantum Simulator**: Experimental module.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourname/makima.git
cd makima
pip install -r requirements.txt
```

> **Note:** `PyAudio` may require system packages:
> - Windows: `pip install pipwin && pipwin install pyaudio`
> - Linux: `sudo apt install portaudio19-dev && pip install pyaudio`

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Minimum required for full functionality:
- `GEMINI_API_KEY` — for online AI (optional if using Ollama)
- `SPOTIPY_*` — for Spotify control
- `TELEGRAM_BOT_TOKEN` — for remote control

### 3. Run

```bash
# Voice mode (microphone required)
python makima_assistant.py

# Text mode (no microphone needed, great for testing)
python makima_assistant.py --text
```

---

## 🗣️ Voice Commands

### Memory
```
Remember that [X]               → saves a note
Do you remember [X]             → recalls from memory
Memory stats                    → shows memory count
```

### AI & Persona
```
Switch to normal mode           → neutral AI persona
Switch to date mode             → friendly/playful persona
Switch to makima mode           → default persona
Clear history                   → resets conversation context
```

### Self-Learning
```
Learn how to [task]             → generates + saves a new skill
List skills                     → shows all learned skills
```

### Apps
```
Open [app name]                 → launches any installed app
Close [app name]                → kills the process
Scan apps                       → rebuilds app index
```

### Spotify
```
Play music                      → resumes Spotify
Pause                           → pauses
Next song                       → skips forward
Previous song                   → goes back
```

### Volume
```
Volume to 60                    → sets to 60%
Volume up / Volume down
Mute / Unmute
```

### System
```
Lock PC
Screenshot
CPU usage
RAM usage
Battery status
Maximize window / Minimize window / Close window
Empty recycle bin
```

### Focus & Productivity
```
Start focus                     → kills distracting apps
Stop focus                      → deactivates
Start recording macro [name]    → records keyboard/mouse
Stop recording                  → saves macro
Run macro [name]                → replays macro
Remind me to [task] at [time]   → sets a spoken reminder
```

### Security
```
Quick scan
Full scan / Deep scan
Scan my downloads
```

### Cloud
```
Sync memory to cloud            → immediate Google Drive backup
Upload [file] to cloud
```

### Web & Code
```
Search for [query]              → DuckDuckGo / browser search
Write code to [task]            → generates Python script
Run code [filename]             → executes a script
```

### Utilities
```
What time is it?
What's today's date?
What day is it?
Good morning / Good evening     → morning briefing
Status                          → AI + memory status
```

---

## 🔍 Code Review Requested!

This is an active project seeking **community code review**.

**Known Issues to Review:**
- Threading safety in `_hud()` method
- Exception handling specificity
- Language detection hardcoding
- Missing shutdown/cleanup
- Microphone calibration blocking

**Please open an issue if you find:**
- 🐛 Bugs
- 🔒 Security vulnerabilities
- 📈 Performance problems
- 🏗️ Architecture improvements
- 📝 Documentation gaps
- ✨ Code quality concerns

**Your feedback helps improve this project!**

---

## 🔍 Code Review Requested!

This is a personal project now open for **community code review**. I am looking for feedback on:

- **Threading safety** in the `_hud()` and voice loops
- **Exception handling** (making it more specific)
- **Architecture patterns** for scaling system plugins
- **Performance** optimizations for low-end hardware

If you find a bug or have a suggestion, please [Open an Issue](https://github.com/Pggamerbgoy/makima/issues/new).

---

## 🏗️ Architecture

```
makima/
├── makima_assistant.py          # Main entry — voice loop, TTS, monitors
├── core/
│   ├── ai_handler.py            # Gemini + Ollama backends, persona, history
│   ├── proactive_engine.py      # Autonomously initiates actions
│   ├── eternal_memory.py        # Persistent memory, TF-IDF search
│   └── command_router.py        # Intent routing for all commands
├── agents/
│   ├── skill_teacher.py         # Self-learning: generate, verify, hot-load skills
│   ├── web_agent.py             # DuckDuckGo search + page fetching
│   ├── app_learner.py           # Learns app UI paths
│   ├── screen_reader.py         # Reads active screen text
│   └── auto_coder.py            # Write and run Python code on demand
├── systems/
│   ├── app_control.py           # Fuzzy app open/close
│   ├── spotify_control.py       # Spotify Web API playback
│   ├── system_commands.py       # Volume, lock, screenshot, CPU/RAM/battery
│   ├── focus_mode.py            # Distraction blocking
│   ├── macros.py                # Keyboard/mouse macro recorder
│   ├── reminder.py              # Time-based spoken reminders
│   ├── security_manager.py      # Antivirus scanning
│   ├── media_observer.py        # Track currently playing media
│   ├── battery_monitor.py       # Low battery alerts
│   ├── clipboard_monitor.py     # URL detection in clipboard
│   ├── overlay.py               # On-screen text display (tkinter)
│   ├── music_dj.py              # DJ module for media
│   ├── whatsapp_manager.py      # WhatsApp automation
│   ├── health_tracker.py        # Health & mood tracking
│   └── ...                      # 15+ other system plugins
├── ui/                          # Rich Electron-based UI components
├── remote/
│   ├── telegram_remote.py       # Telegram bot remote control
│   └── web_dashboard.py         # Local browser UI (port 8000)
├── cloud/
│   └── cloud_manager.py         # Google Drive sync (12h auto)
├── learned_skills/              # Auto-generated skill plugins (hot-loaded)
├── makima_memory/               # Persistent conversation logs + notes
├── screenshots/                 # Saved screenshots
├── generated_code/              # Auto-generated scripts
├── macros/                      # Saved macro recordings
├── requirements.txt
└── .env.example
```

---

## 🧬 Self-Learning System

When you say **"Learn how to [task]"**, Makima:

1. Checks if it's already a built-in command
2. Prompts Gemini/Ollama to write a Python function for the task
3. Verifies the code compiles (syntax check, up to 2 retries with self-correction)
4. Saves the skill to `learned_skills/[name].py`
5. Hot-loads it instantly — no restart needed

Next time you give a matching command, the learned skill runs automatically.

---

## 🔌 Remote Access

### Telegram
Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then the bot auto-starts with Makima. Message your bot to control Makima from anywhere.

### Web Dashboard
Open `http://localhost:8000` in any browser on your LAN. Type commands and get responses in real time.

---

## 🛠️ Adding New Systems

1. Create `systems/my_system.py` with a class
2. Import and instantiate it in `core/command_router.py`
3. Add regex patterns to `CommandRouter.PATTERNS`
4. Add a handler method `_handle_my_command(self, m)`

---

## 📦 Optional Local LLM (Ollama)

```bash
# Install Ollama from https://ollama.ai
ollama pull mistral       # or llama3, phi3, gemma, etc.
# Makima auto-detects it when Gemini is unavailable
```

---

## 🌏 Bilingual Support

Makima auto-detects Hindi (Devanagari or Hinglish) in both voice and text:
- English phrases → responded to in English
- Hindi phrases → responded to in Hindi
- Wake word works in English: "Hey Makima"

---

## 📄 License

MIT License. Built with ❤️ using Python, Gemini, and Ollama.
