# Discord Music Bot

A minimal Discord music bot using discord.py, yt-dlp, and FFmpeg.

## Quickstart

### 1) Prerequisites
- Python 3.10+ (recommended)
- FFmpeg installed on your system
- A Discord application with a bot token

Install FFmpeg:
- Linux (Ubuntu/Debian):
	```sh
	sudo apt update && sudo apt install -y ffmpeg
	```
- Windows (pick one):
	- Winget: `winget install -e --id Gyan.FFmpeg`
	- Chocolatey: `choco install ffmpeg`
	- Or download from the FFmpeg website and add the bin folder to PATH

### 2) Setup

Create and activate a virtual environment (optional but recommended):

Linux/macOS:
```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
py -3 -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

### 3) Configure your token

Copy the example env file and add your bot token:

Linux/macOS:
```sh
cp .env.example .env
```
Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Then edit `.env` and set:
```
DISCORD_TOKEN=your_token_here
```
Notes:
- Do not include quotes or the "Bot " prefix. Just the raw token string.
- `.env` is ignored by git (see `.gitignore`). Do not commit your real token.

Make sure the bot has the following scopes and permissions when inviting it to your server:
- Scopes: `bot`, `applications.commands`
- Bot Permissions: `Send Messages`, `Connect`, `Speak`, `Use Slash Commands`

Intents:
- This bot does not require the Message Content intent for its slash commands and music features.

### 4) Run

Linux/macOS:
```sh
python bot.py
```

Windows (PowerShell):
```powershell
python bot.py
```

On first run, slash commands will sync; it may take up to a minute to appear globally. To test faster, add the bot with the `applications.commands` scope and try `/play` in your server.

### 5) Commands
- `/play <query or url>`: Queue and play audio from YouTube
- `/pause`, `/resume`, `/skip`, `/stop`, `/queue`

Moderation:
- `/kick <member> [reason]` — Kick a member from the server
- `/ban <member> [reason]` — Ban a member from the server

Required Discord permissions:
- For users: Kick Members to use `/kick`, Ban Members to use `/ban`.
- For the bot: It must have the corresponding server permissions as well, and its highest role must be above the target member’s highest role.

### Troubleshooting
- If you see `ERROR: DISCORD_TOKEN is not set`, create `.env` with your token.
- If audio doesn’t play, ensure FFmpeg is installed and reachable in PATH.
- Some environments require Opus/PyNaCl for voice. This project pins `PyNaCl` in `requirements.txt`.
- If commands don’t show up, wait a minute or re-invite the bot and ensure it has the `applications.commands` scope.
 - Windows: If `ffmpeg` isn’t found, close and reopen PowerShell after installing it, or verify that `ffmpeg.exe` is on PATH.

### Security note
- `.env` is excluded by `.gitignore` so you can safely push your repo without committing secrets.
- Never paste your real token into source files. Use `.env` only.
- If a token was ever committed, rotate it in the Discord Developer Portal immediately.
