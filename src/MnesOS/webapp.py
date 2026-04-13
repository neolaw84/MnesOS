"""
MnesOS Web UI — single-user, locally host-able Flask frontend.

Usage::

    python -m MnesOS.webapp cartridges/generic-rpg

    # or, after ``pip install MnesOS[webapp]``:
    mnesos-webapp cartridges/generic-rpg

Optional environment variables (loaded from .env if present):
    OPENAI_API_KEY       — required for live LLM calls
    OPENAI_API_BASE      — override base URL (e.g. for local / proxy models)
    MNESOS_MODEL         — model name (default: gpt-4o-mini)
    MNESOS_TEMPERATURE   — sampling temperature (default: 0.9)
    MNESOS_HOST          — bind host (default: 127.0.0.1)
    MNESOS_PORT          — bind port (default: 5000)
    MNESOS_SAVES_DIR     — directory for save files (default: ./mnesos-saves)
"""

import argparse
import copy
import json
import logging
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Attempt to load optional dependencies with helpful error messages.
# ---------------------------------------------------------------------------
try:
    from flask import Flask, jsonify, render_template, request
except ImportError as exc:
    sys.exit(
        "Flask is required for the MnesOS web UI.\n"
        "Install it with:  pip install 'MnesOS[webapp]'\n"
        f"(Original error: {exc})"
    )

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app(cartridge_dir: str, saves_dir: str) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        cartridge_dir: Path to the cartridge directory.
        saves_dir:     Directory where save-files are written/read.
    """
    template_folder = str(Path(__file__).parent / "templates")
    app = Flask(__name__, template_folder=template_folder)

    # ------------------------------------------------------------------
    # Initialise the Orchestrator (deferred so Flask can start fast).
    # ------------------------------------------------------------------
    saves_path = Path(saves_dir)
    saves_path.mkdir(parents=True, exist_ok=True)

    _orch = _init_orchestrator(cartridge_dir)

    # Seed with first-message.md if available and history is empty.
    _seed_first_message(_orch, cartridge_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_filename(name: str) -> str:
        """Sanitise user-supplied save-file name."""
        name = name.strip()
        name = re.sub(r"[^\w\- ]", "_", name)
        name = name.replace(" ", "-")
        if not name:
            name = "save"
        return name[:64]

    def _save_path(filename: str) -> Path:
        return saves_path / (_safe_filename(filename) + ".json")

    def _serialisable_state(state: dict) -> dict:
        """Return a JSON-serialisable copy of the game state."""
        data: dict = {}
        for key, value in state.items():
            try:
                json.dumps(value)
                data[key] = value
            except (TypeError, ValueError):
                data[key] = str(value)
        return data

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/")
    def index():
        cartridge_name = Path(cartridge_dir).name
        return render_template("game.html", cartridge_name=cartridge_name)

    @app.post("/api/turn")
    def api_turn():
        body = request.get_json(silent=True) or {}
        user_input = (body.get("user_input") or "").strip()
        if not user_input:
            return jsonify({"error": "user_input is required"}), 400
        try:
            response = _orch.process_turn(user_input)
            _middle_out_truncate(_orch)
            return jsonify({"response": response})
        except Exception as exc:  # noqa: BLE001
            logger.exception("process_turn failed")
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/reset")
    def api_reset():
        _orch.reset()
        _seed_first_message(_orch, cartridge_dir)
        return jsonify({"ok": True})

    @app.get("/api/state")
    def api_state():
        return jsonify({
            "client_messages": _orch.state.get("client_messages", [])
        })

    @app.post("/api/save")
    def api_save():
        body = request.get_json(silent=True) or {}
        filename = (body.get("filename") or "save").strip()
        path = _save_path(filename)
        try:
            data = _serialisable_state(dict(_orch.state))
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Game saved to %s", path)
            return jsonify({"ok": True, "path": str(path)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Save failed")
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/load")
    def api_load():
        body = request.get_json(silent=True) or {}
        filename = (body.get("filename") or "save").strip()
        path = _save_path(filename)
        if not path.exists():
            return jsonify({"error": f"Save file not found: {path}"}), 404
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Restore mutable state fields.
            for key in list(_orch.state.keys()):
                if key in data:
                    _orch.state[key] = data[key]
            logger.info("Game loaded from %s", path)
            return jsonify({
                "ok": True,
                "path": str(path),
                "client_messages": _orch.state.get("client_messages", []),
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("Load failed")
            return jsonify({"error": str(exc)}), 500

    return app


# ---------------------------------------------------------------------------
# Orchestrator bootstrap helpers
# ---------------------------------------------------------------------------

MAX_HISTORY = 10
FRONT_KEPT = 2


def _init_orchestrator(cartridge_dir: str):
    """Initialise the Orchestrator, wiring up LLMs from environment."""
    from MnesOS.orchestrator import Orchestrator  # local import avoids circular

    model = os.environ.get("MNESOS_MODEL", "gpt-4o-mini")
    temperature = float(os.environ.get("MNESOS_TEMPERATURE", "0.9"))

    llm = None
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            from langchain_openai import ChatOpenAI
            kwargs: dict = {"model": model, "temperature": temperature}
            base_url = os.environ.get("OPENAI_API_BASE")
            if base_url:
                kwargs["base_url"] = base_url
            llm = ChatOpenAI(**kwargs)
            logger.info("LLM initialised: model=%s temperature=%s", model, temperature)
        except ImportError:
            logger.warning(
                "langchain_openai is not installed — running in dry-run mode (no LLM calls)."
            )
    else:
        logger.warning(
            "OPENAI_API_KEY not set — running in dry-run mode (no LLM calls)."
        )

    return Orchestrator(
        cartridge_dir=cartridge_dir,
        llm_director=llm,
        llm_npc_brain=llm,
        llm_narrator=llm,
    )


def _seed_first_message(orch, cartridge_dir: str) -> None:
    """Prepend the cartridge's first-message.md to client_messages if present."""
    first_msg_path = Path(cartridge_dir) / "first-message.md"
    if first_msg_path.exists() and not orch.state.get("client_messages"):
        content = first_msg_path.read_text(encoding="utf-8").strip()
        if content:
            orch.state["client_messages"].append(
                {"role": "assistant", "content": content}
            )
            logger.info("Loaded first-message.md from %s", first_msg_path)


def _middle_out_truncate(orch) -> None:
    """Apply Middle Out context truncation after each turn."""
    msgs = orch.state.get("client_messages", [])
    if len(msgs) <= MAX_HISTORY:
        return
    back_len = MAX_HISTORY - FRONT_KEPT
    orch.state["client_messages"] = msgs[:FRONT_KEPT] + msgs[-back_len:]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    if load_dotenv is not None:
        load_dotenv()

    parser = argparse.ArgumentParser(
        prog="mnesos-webapp",
        description="Launch the MnesOS single-user web UI.",
    )
    parser.add_argument(
        "cartridge",
        metavar="CARTRIDGE_DIR",
        help="Path to the cartridge directory (e.g. cartridges/generic-rpg).",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MNESOS_HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MNESOS_PORT", "5000")),
        help="Bind port (default: 5000).",
    )
    parser.add_argument(
        "--saves-dir",
        default=os.environ.get("MNESOS_SAVES_DIR", "mnesos-saves"),
        help="Directory for save files (default: mnesos-saves).",
    )
    args = parser.parse_args(argv)

    cartridge_dir = args.cartridge
    if not Path(cartridge_dir).is_dir():
        sys.exit(f"Cartridge directory not found: {cartridge_dir!r}")

    app = create_app(cartridge_dir=cartridge_dir, saves_dir=args.saves_dir)

    print(f"\n  MnesOS Web UI  →  http://{args.host}:{args.port}/\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
