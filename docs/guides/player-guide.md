# Play-Testing MnesOS — Step-by-Step Guide

This guide walks you through setting up and running a local play-test of the MnesOS agentic RPG engine from scratch. It is written for people who are comfortable using a terminal (Bash, Zsh, PowerShell, or Command Prompt), but who are **not** software engineers.

---

## Overview & Quick Reference

MnesOS has two parts that must run at the same time:

| Part | What it is | Where you run it |
|---|---|---|
| **Backend (API server)** | Python application that runs the game engine | Terminal 1 |
| **Web UI (front-end)** | Browser app you use to actually play | Terminal 2 |

You will need **two terminal windows** open side by side.

### Quick Reference Commands

**First-time setup only:**
```bash
# In the MnesOS project root (with venv activated):
pip install -e ".[dev,api]"
mnesos-ingest-cartridges

# In web-client/ (one-time install):
npm install
```

**Starting up (every session):**
```bash
# Terminal 1 — Backend API server
cd /path/to/MnesOS
# Activate venv (Unix: `source venv/bin/activate`, Windows: `.\venv\Scripts\activate`)
uvicorn MnesOS.api.app:app --reload

# Terminal 2 — Web UI
cd /path/to/MnesOS/web-client
npm run dev
```

---

## Prerequisites

### 1. Install Python 3.12+

MnesOS requires Python 3.12 or newer. Check your version:
```bash
python3 --version  # or python --version on Windows
```

**If you need to install Python:**
- **Ubuntu / Debian**: `sudo apt install -y python3.12 python3.12-venv python3.12-dev`
- **macOS** (Homebrew): `brew install python@3.12`
- **Windows**: Download the installer from Python.org. **IMPORTANT:** Check the box that says **"Add Python to PATH"** during installation.

### 2. Install Node.js via nvm / nvm-windows

The web UI requires Node.js. 

**macOS / Linux:**
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# Restart terminal, then:
nvm install --lts
nvm use --lts
```

**Windows:**
1. Download the latest `nvm-setup.exe` from the nvm-windows releases page.
2. Run the installer.
3. Open a **new** PowerShell window and run:
```powershell
nvm install lts
nvm use lts
```

---

## Part 1 — Setting Up the Backend (API Server)

Open **Terminal 1** and navigate to the MnesOS project root (e.g. `cd ~/projects/MnesOS` or `cd C:\path\to\MnesOS`).

### 1.1 — Create a Virtual Environment
```bash
# macOS/Linux:
python3.12 -m venv venv

# Windows:
python -m venv venv
```

### 1.2 — Activate the Virtual Environment
```bash
# macOS/Linux:
source venv/bin/activate

# Windows (PowerShell):
.\venv\Scripts\activate
# Note: On Windows, you may need to run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` as Administrator if scripts are disabled.
```

Your terminal prompt should now show `(venv)` at the beginning.

### 1.3 — Install Python Dependencies
```bash
pip install -e ".[dev,api]"
```

### 1.4 — Ingest Game Cartridges
```bash
mnesos-ingest-cartridges
```

### 1.5 — Start the API Server
```bash
uvicorn MnesOS.api.app:app --reload
```
Leave this terminal running. The API server is now running at **http://localhost:8000**.

---

## Part 2 — Setting Up the Web UI (Front-End)

Open **Terminal 2**, and navigate to the web client directory:
```bash
# macOS/Linux:
cd /path/to/MnesOS/web-client

# Windows:
cd C:\path\to\MnesOS\web-client
```

### 2.1 — Install JavaScript Dependencies
```bash
npm install
```

### 2.2 — Start the Web UI Dev Server
```bash
npm run dev
```

Leave this terminal running. The Web UI is now at **http://localhost:5173**. Open this in your browser.

---

## Part 3 — Using the Web UI

The interface is divided into several sections, all accessible from the header bar:
- **🕹 Play**: The main game view
- **📚 Library**: Browse and manage game cartridges
- **🎭 Personas**: Create and manage your player characters
- **📂 Active Games**: See and resume all your in-progress games
- **🚀 Start New Game**: Launch a new game session
- **⚙️ Settings**: Configure your API key and user identity

### Step 3.1 — Configure Settings First (Required!)
You must set a User ID in Settings before using Personas or Active Games.
1. Click **⚙️ Settings**.
2. Enter your **OpenRouter API Key (BYOK)**.
3. Enter a **User ID** (e.g., `tester-01`).
4. Click **Save**.

### Step 3.2 — Browse the Cartridge Library
Click **📚 Library** to see available games. You can click a cartridge to open its Detail View and upload new versions via ZIP or individual files (`yare.yaml`, `bot_lore.md`, etc.).

### Step 3.3 — Create a Persona
Click **🎭 Personas**, then **+ New Persona**. Fill in your character's name, pronouns, appearance, and background. This helps the narrator describe your character accurately.

### Step 3.4 — Start a New Game
Click **🚀 Start New Game**, select your cartridge, version, and persona, then click **Start Game**.

### Step 3.5 — Playing the Game
Interact with the narrator in the **🕹 Play** view. Type your action and press Enter. You can save your state using the Save Bar above the chat box to branch your timeline.

### Step 3.6 — The State Debugger
On the right edge of the Play view, click the **◀ Debug** tab to see live game stats (HP, Gold, items) and a full JSON dump of the engine's tracking state. This is highly useful for verifying deterministic cartridge rules.

---

## Part 4 — Stopping the Servers

When you are done play-testing:
1. In **Terminal 2** (web UI), press `Ctrl+C`.
2. In **Terminal 1** (API server), press `Ctrl+C`.
3. Deactivate the Python virtual environment:
   ```bash
   deactivate
   ```

---

## Troubleshooting

- **The web UI shows error banners immediately on load:** Your User ID is not set. Go to ⚙️ Settings and save a User ID.
- **"Failed to load cartridges" or API errors:** The backend API server is probably not running. Check Terminal 1.
- **"No Cartridges Available" in Start New Game:** Run `mnesos-ingest-cartridges` in Terminal 1 with your `venv` active.
- **"No Versions Available" when starting a game:** The cartridge has no version files. Open it in the Library and upload a version using the files from `cartridges/<game-name>/`.
- **Narrator response is very slow:** Check your OpenRouter API key and credit balance.
- **The `(venv)` prefix disappears (macOS/Linux) or script errors out (Windows):** The virtual environment must be activated again in each new terminal session. On Windows, ensure you've set the ExecutionPolicy if scripts fail to run.
