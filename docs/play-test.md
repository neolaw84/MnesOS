# Play-Testing MnesOS — Step-by-Step Guide

This guide walks you through setting up and running a local play-test of the MnesOS agentic RPG engine from scratch. It is written for people who are comfortable using a terminal, but who are **not** software engineers.

---

## What You Will Be Running

MnesOS has two parts that must run at the same time:

| Part | What it is | Where you run it |
|---|---|---|
| **Backend (API server)** | Python application that runs the game engine | Terminal 1 |
| **Web UI (front-end)** | Browser app you use to actually play | Terminal 2 |

You will need **two terminal windows** open side by side.

---

## Prerequisites

### 1. Install Python 3.12+

MnesOS requires Python 3.12 or newer.

**Check your current version first:**

```bash
python3 --version
```

If the output says `Python 3.12.x` or higher, you are good — skip to step 2.

**If you need to install Python:**

On **Ubuntu / Debian**:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

On **macOS** (with Homebrew):

```bash
brew install python@3.12
```

After installing, confirm:

```bash
python3.12 --version
# Expected output: Python 3.12.x
```

---

### 2. Install Node.js via nvm

The web UI requires Node.js. We use **nvm** (Node Version Manager) so you can install and switch Node versions without needing admin rights.

**Install nvm:**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

After the script finishes, **close and reopen your terminal** (or run the command it prints, which looks like `source ~/.bashrc`).

**Verify nvm is installed:**

```bash
nvm --version
# Expected output: 0.39.7 (or similar)
```

**Install the latest LTS version of Node.js:**

```bash
nvm install --lts
nvm use --lts
```

**Verify Node and npm are available:**

```bash
node --version   # e.g. v22.x.x
npm --version    # e.g. 10.x.x
```

---

## Quick Reference

### First-time setup only

```bash
# In the MnesOS project root, with venv activated:
pip install -e ".[dev,api]"
mnesos-ingest-cartridges

# In web-client/ (one-time install):
npm install
```

### Starting up (every session)

```bash
# Terminal 1 — Backend API server
cd /path/to/MnesOS
source venv/bin/activate
uvicorn MnesOS.api.app:app --reload

# Terminal 2 — Web UI
cd /path/to/MnesOS/web-client
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Part 1 — Setting Up the Backend (Python / API Server)

Open **Terminal 1** and navigate to the MnesOS project root:

```bash
cd /path/to/MnesOS
```

> **Tip:** Replace `/path/to/MnesOS` with the actual path on your machine, e.g. `~/projects/MnesOS`.

### Step 1.1 — Create a Virtual Environment

A virtual environment keeps MnesOS's Python dependencies isolated from the rest of your system.

```bash
python3.12 -m venv venv
```

This creates a `venv/` folder in the project directory.

### Step 1.2 — Activate the Virtual Environment

```bash
source venv/bin/activate
```

Your terminal prompt should now show `(venv)` at the beginning, like this:

```
(venv) user@machine:~/projects/MnesOS$
```

> **Note:** You must activate the virtual environment every time you open a new terminal to work on MnesOS. Just run `source venv/bin/activate` again from the project root.

### Step 1.3 — Install Python Dependencies

```bash
pip install -e ".[dev,api]"
```

This installs the MnesOS engine plus all the packages needed for running the API server. It will take a minute or two the first time.

### Step 1.4 — Ingest Game Cartridges

Before starting the server, load the game cartridges into the database. A **cartridge** is a self-contained game containing rules, lore, and story directives.

```bash
mnesos-ingest-cartridges
```

This scans the `cartridges/` directory and registers all games found there. The bundled cartridges are:

- **`dark-fantasy`** — a grim, Soulslike adventure
- **`generic-rpg`** — a general-purpose fantasy RPG

You should see output confirming each cartridge was ingested successfully.

### Step 1.5 — Start the API Server

```bash
uvicorn MnesOS.api.app:app --reload
```

Leave this terminal running. You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process ...
INFO:     Started server process ...
INFO:     Application startup complete.
```

> The `--reload` flag makes the server restart automatically if any source files change. This is useful during play-testing.

The API server is now running at **http://localhost:8000**.

---

## Part 2 — Setting Up the Web UI (Front-End)

Open **Terminal 2** (keep Terminal 1 running), and navigate to the web client directory:

```bash
cd /path/to/MnesOS/web-client
```

### Step 2.1 — Install JavaScript Dependencies

```bash
npm install
```

This downloads the required front-end packages into `node_modules/`. It only needs to be run once.

### Step 2.2 — Start the Web UI Dev Server

```bash
npm run dev
```

You should see:

```
  VITE v8.x.x  ready in 300 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

Leave this terminal running too.

### Step 2.3 — Open the Web UI

Open your web browser and go to:

```
http://localhost:5173
```

You should see the **MnesOS Alpha** interface — a dark-themed app with a header bar at the top.

---

## Part 3 — Using the Web UI

The MnesOS interface is divided into several sections, all accessible from the header bar.

### Overview of the Header

The header contains six controls:

| Button | What it does |
|---|---|
| **🕹 Play** | The main game view — your chat with the narrator |
| **📚 Library** | Browse and manage game cartridges |
| **🎭 Personas** | Create and manage your player characters |
| **📂 Active Games** | See and resume all your in-progress games |
| **🚀 Start New Game** | Launch a new game session |
| **⚙️ Settings** | Configure your API key and user identity |

---

### Step 3.1 — Configure Settings First (Required!)

> **Important:** You must set a User ID in Settings before using Personas or Active Games, otherwise the UI will show an error.

Click **⚙️ Settings** in the header. A modal dialog will appear:

![Settings modal](img/settings_modal.png)

Fill in the fields:

| Field | What to enter |
|---|---|
| **OpenRouter API Key (BYOK)** | Your `sk-or-...` key from OpenRouter |
| **User ID** | Any identifying string, e.g. `alice` or `tester-01` |
| **Game Instance ID** | Leave blank — it is filled in automatically when you start a game |

> **Privacy note:** Your API key is stored only in your browser's local storage and sent directly to OpenRouter. It is never transmitted to the MnesOS backend server.

Click **Save** when done.

---

### Step 3.2 — Browse the Cartridge Library

Click **📚 Library** in the header.

![Cartridge Library](img/library_view.png)

The Library shows all available game cartridges. Each card shows:

- **Title** — the name of the game (e.g. `dark-fantasy`)
- **Visibility** badge — `PUBLIC` (green) or `PRIVATE` (orange)
- **Description** — a short summary if provided

Click any cartridge card to open its **Detail View**, where you can see its uploaded versions, edit metadata, or upload a new version.

#### Uploading a Cartridge Version

In the Cartridge Detail view, click **⬆️ Upload Version**. A modal appears:

| Field | What to enter |
|---|---|
| **Version Tag** | A label like `1.0.0` |
| **Upload Mode** | **ZIP archive** (recommended) or **Individual files** |

- **ZIP mode:** Upload a single `.zip` containing `yare.yaml`, `bot_lore.md`, and optionally `prompt_directives.yaml`.
- **Individual files mode:** Upload each of those three files separately.

The engine validates all files on upload and shows any errors before saving.

> **For play-testing the bundled cartridges:** You can skip this step. The `mnesos-ingest-cartridges` command (Step 1.5) already loaded the bundled cartridges and their files. Uploading is for when you create or modify your own cartridges.

---

### Step 3.3 — Create a Persona

A **persona** is your player character — the identity you bring into any game.

Click **🎭 Personas** in the header, then click **+ New Persona**.

![Create Persona modal](img/new_persona_modal.png)

Fill in the fields:

| Field | Description | Example |
|---|---|---|
| **Name** *(required)* | Your character's name | `Elara` |
| **Pronoun (Sub)** *(required)* | Subject pronoun | `she` |
| **Pronoun (Obj)** *(required)* | Object pronoun | `her` |
| **Pronoun (Poss)** *(required)* | Possessive adjective | `her` |
| **Pronoun (Poss Obj)** *(required)* | Possessive pronoun | `hers` |
| **Appearance** *(optional)* | Physical description | `Tall with silver hair and sharp eyes` |
| **Background** *(optional)* | Backstory | `A former soldier turned wanderer` |
| **Personality** *(optional)* | Traits and demeanor | `Cautious, dry humour, loyal to a fault` |

The appearance, background, and personality are optional but highly recommended — the narrator LLM uses this information to refer to your character correctly in prose.

Click **Save Persona** when done. Your persona appears as a card in the Personas view. You can create multiple personas and choose between them for different games.

---

### Step 3.4 — Start a New Game

Click **🚀 Start New Game** in the header. A modal appears with three dropdowns:

| Field | What to choose |
|---|---|
| **Select Cartridge** | Choose a game, e.g. `dark-fantasy` |
| **Select Version** | Choose a version tag, e.g. `1.0.0` (defaults to the latest) |
| **Select Persona** | Choose the persona you created in Step 3.3 |

Once all three are selected, click **Start Game**.

The modal closes and the view switches to **🕹 Play** automatically, where your adventure begins.

> **If "No Cartridges Available" appears:** The library requires a User ID to be set. Go to ⚙️ Settings, enter a User ID, and save. Then try again.

> **If "No Versions Available" appears:** The cartridge exists but has no uploaded version files. Go to the Library (Step 3.2), open the cartridge, and upload a version using the files from the `cartridges/` folder.

---

### Step 3.5 — Playing the Game

The **🕹 Play** view is where you interact with the engine:

![Play view with debug panel](img/play_view_debug_open.png)

The Play view has three main areas:

#### Chat Pane (top area)

This is where the story unfolds. The narrator LLM responds to your actions in prose. New messages appear here as you play, and the pane scrolls automatically. Before any action is sent, it shows:

> *🌐 No messages yet. Type an action below to begin your adventure!*

#### Save Bar (middle strip)

Between the chat and the input box, a toolbar provides save controls:

| Control | What it does |
|---|---|
| **🔄 Retry** | Re-runs the last narrator response (useful if the response is unsatisfying) |
| **Save label...** input | Optional label for your save |
| **💾 Save** | Saves the current game state as a named checkpoint |
| **📂 Loads (N)** | Expands a list of saved checkpoints; click **Load** on any to restore it |

> **Tip:** Save before risky actions! You can branch the story by saving, trying something dangerous, and loading the save if it goes badly.

#### Input Box (bottom)

Type what your character does and press **Enter** or click **Act**. Examples:

```
I examine the ruined shrine carefully before touching anything.
```

```
I attack the creature with my sword!
```

```
I try to barter with the merchant for a better price.
```

The engine will interpret your input, apply any deterministic game rules (combat rolls, stat changes, etc.), and have the narrator describe the result.

---

### Step 3.6 — The State Debugger

On the right edge of the Play view there is a thin **◀ Debug** tab. Click it to expand the State Debugger panel:

![Play view with State Debugger open](img/play_view_debug_open.png)

The panel shows the live game state — the raw data the engine is tracking for your playthrough:

| Quick stat | What it shows |
|---|---|
| ❤️ HP | Your current health points |
| 💰 Gold | Your current gold |
| ⭐ Level | Your character level (if the cartridge tracks it) |
| 📍 Location | Your current in-world location |
| 🎒 Items | Number of items in your inventory |

Below the quick stats is a **full JSON dump** of every value the engine is tracking. This is especially useful when play-testing a new or modified cartridge to verify that rules (damage, stat mutations, etc.) are being applied correctly.

Click **▶ Hide Debug** to collapse the panel.

---

### Step 3.7 — Managing Active Games

Click **📂 Active Games** to see all your in-progress game instances. Each card shows the game's status, creation time, and when it was last played.

From here you can:

- Click **Resume** to jump back into a previous game (it loads the last turn of that instance)
- Click **Delete** to permanently remove a game instance and all its history

---

## Part 4 — Stopping the Servers

When you are done play-testing:

1. In **Terminal 2** (web UI), press `Ctrl+C`.
2. In **Terminal 1** (API server), press `Ctrl+C`.
3. Optionally deactivate the Python virtual environment:

    ```bash
    deactivate
    ```

---

## Troubleshooting

### The web UI shows error banners immediately on load

This usually means your **User ID is not set**. Go to ⚙️ Settings, enter any string in the User ID field, and click Save. The errors should disappear after navigating away and back.

### "Failed to load cartridges" or other API errors

The backend API server is probably not running. Switch to Terminal 1 and check if you see `Application startup complete`. If it crashed, re-run:

```bash
source venv/bin/activate
uvicorn MnesOS.api.app:app --reload
```

### "No Cartridges Available" in Start New Game

Either the User ID is not set (fix in Settings), or `mnesos-ingest-cartridges` was not run. With the venv active, run:

```bash
mnesos-ingest-cartridges
```

### "No Versions Available" when starting a game

The cartridge was registered but has no version files. In the Library view, open the cartridge, click **⬆️ Upload Version**, and upload the files from `cartridges/<game-name>/`.

### Narrator response is very slow or never arrives

LLM API calls can take time. If a response is taking more than 30 seconds:

- Check your OpenRouter API key is correct (⚙️ Settings).
- Check your OpenRouter credit balance at [https://openrouter.ai](https://openrouter.ai).
- Check Terminal 1 for error tracebacks from the API server.

### The `(venv)` prefix disappears after opening a new terminal

This is normal — the virtual environment must be activated again in each new terminal session:

```bash
cd /path/to/MnesOS
source venv/bin/activate
```

