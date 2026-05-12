# 📖 MnesOS Player Guide

Welcome to **MnesOS**, a stateless, event-sourced agentic RPG engine. MnesOS operates on a **Bring-Your-Own-Key (BYOK)** model. All gameplay rules, deterministic state progressions, and character logs run directly on your machine, using your private browser session to authenticate securely with OpenRouter.

---

## 🕹️ Part 1 — Player Manual: Pre-Compiled Installation (Recommended)

If you simply want to test cartridges and play games without editing source code, use the pre-compiled Python package. The web client UI is fully bundled inside the backend package, allowing you to run the entire engine from a single terminal command.

### 1.1 — Prerequisites
- **Python 3.12+**: Download from [python.org](https://www.python.org/). 
  > **CRITICAL FOR WINDOWS USERS**: During the installation wizard, you **must** check the box labeled **"Add python.exe to PATH"** before clicking Install.

### 1.2 — Environment Initialization
Open your preferred terminal (**Terminal / iTerm** on macOS/Linux; **PowerShell** or **Command Prompt** on Windows) and create a folder for your local game saves:

```bash
mkdir MnesOS-Games
cd MnesOS-Games
```

Create and activate a clean virtual environment:
- **macOS / Linux**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- **Windows (PowerShell)**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
  *(If script execution is disabled, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first).*
- **Windows (Command Prompt / cmd)**:
  ```cmd
  python -m venv venv
  .\venv\Scripts\activate.bat
  ```

Your terminal prompt will display `(venv)` to confirm isolation.

### 1.3 — Install & Launch
Install the engine and pre-packaged API dependencies directly from PyPI:
```bash
pip install MnesOS[api]
```

Launch the local game server:
```bash
uvicorn MnesOS.api.app:app --host 127.0.0.1 --port 8000
```

> **Database Note**: MnesOS automatically creates its SQLite database file and parent folders on startup. By default, your saves reside at `artifacts/mnesos.db`. To customize this destination folder, prefix your launch command with the environment variable:
> - **Linux/macOS**: `MNESOS_DB_PATH=/path/to/my_saves.db uvicorn MnesOS.api.app:app`
> - **Windows (PowerShell)**: `$env:MNESOS_DB_PATH="C:\my_saves.db"; uvicorn MnesOS.api.app:app`

Leave this terminal running. Open your web browser to **`http://localhost:8000`** to begin playing!

---

## 🔗 Part 2 — Interface Guide & Authentication

The MnesOS top navigation bar contains modules for configuring, loading, and playing adventures:
- **🕹 Play**: The core dialogue and narrative console.
- **📚 Library**: Inspect installed cartridges or upload update bundles (`yare.yaml`, `bot_lore.md`).
- **🎭 Personas**: Define custom player identities and background traits.
- **📂 Active Games**: Inspect, resume, or fork parallel session timelines.
- **🚀 Start New Game**: Spin up a game instance from an ingested cartridge version.
- **⚙️ Settings**: Manage zero-knowledge credentials and active identities.

### Step 2.1 — Configure Settings (Required First Step!)
Because MnesOS operates on a pure stateless architecture, your API keys are never written to disk or logged remotely. You must authorize your browser session locally:

1. Click **⚙️ Settings**.
2. Click the prominent **🔗 Connect OpenRouter** button.
3. Your browser will securely authenticate with OpenRouter via PKCE exchange. Authorize the requested scope.
4. Once redirected back to your dashboard, confirm the panel shows **✅ Connected to OpenRouter**.
5. Specify a custom **User ID** (defaults to `local-user`) to catalog your distinct database save states.
6. Click **Save**.

### Step 2.2 — How to Add & Manage Cartridges
When installing from pre-compiled PyPI packages, your local database initializes completely empty so you can curate your own private gaming library. To load or create an adventure:

1. Navigate to **📚 Library**.
2. Click **+ New Cartridge** to register the parent adventure container (Title, Description, Genre, Visibility) and click **Save**.
3. Click on the newly created cartridge card in your library list to open its **Detail View**.
4. Under the **Versions** section, click **⬆️ Upload Version**.
5. You can submit files in two ways:
   - **Upload a ZIP archive**: Pack your cartridge code folder containing `yare.yaml`, `bot_lore.md`, and optional `prompt_directives.yaml` into a standard `.zip` file and select it.
   - **Upload Individual Files**: Select the explicit rule and markdown assets individually directly from your filesystem.
6. Provide a version tag string (e.g., `1.0.0`) and click **Upload**. The engine validates your schemas on the fly and immediately indexes the playable release.

### Step 2.3 — Create Your Persona
Navigate to **🎭 Personas** -> **+ New Persona**. Define your custom character's identity, pronouns, structural aesthetics, and behavioral history. The engine passes these explicit parameters to the Director agent to contextualize roleplay interactions.

### Step 2.4 — Launch an Adventure
Go to **🚀 Start New Game**, pick an available adventure cartridge and version schema, assign your newly created Persona, and click **Start Game**.

### Step 2.5 — Deterministic Logic Debugging
While testing rules inside the **🕹 Play** console, open the **◀ Debug** panel pinned to the right edge of the window. This exposes real-time numeric properties (HP, Currency, Inventory items) alongside a complete structural JSON snapshot of the local YARE machine state.

---

## 🛑 Part 3 — Graceful Shutdown & Troubleshooting

To conclude your session, switch back to your active terminal(s) and press **`Ctrl + C`** to stop the server processes. Your progression state automatically safely rests inside your SQLite database file.

### Common Solutions
- **Immediate error popups loading the interface**: Your local User ID is empty. Navigate to **⚙️ Settings**, enter an ID, and save.
- **"Failed to fetch" or connection timeouts**: Verify your backend API server is currently running and listening on port 8000.
- **Terminal throws "command not found: pip" or script permissions fail**: Verify your virtual environment `(venv)` is explicitly activated for that terminal pane. On Windows PowerShell, confirm your execution policies permit running local module scripts.

---

## 💻 Part 4 — Install from Source

If you plan to edit React frontend components, alter core YARE interpreter logic, or contribute pull requests, set up the divided workspace. You will need **two separate terminal windows** running simultaneously.

### 4.1 — Prerequisites
Ensure you have **Python 3.12+** and **Node.js (v20+ LTS)** installed.

### 4.2 — Terminal 1: Backend API Server
Navigate to your cloned repository root:
```bash
cd /path/to/MnesOS
```

Create and activate your Python virtual environment:
```bash
python3.12 -m venv venv
# Unix:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate
```

Install the engine in editable mode with development dependencies:
```bash
pip install -e ".[dev,api]"
```

Ingest bundled starting cartridges into your local database:
```bash
mnesos-ingest-cartridges
```

Start the backend server using the unified database rule:
```bash
make run-python
```
*(This launches Uvicorn pointing automatically to `artifacts/mnesos.db` so your manual gameplay state persists identically across testing routines).*

### 4.3 — Terminal 2: Live-Reload Web UI
Open a second terminal window and navigate to the frontend directory:
```bash
cd /path/to/MnesOS/web-client
```

Install Node packages and launch the Vite client server:
```bash
npm install
npm run dev
```

Leave both terminals running. Open your web browser to **`http://localhost:5173`** to access the live-reloading UI.
