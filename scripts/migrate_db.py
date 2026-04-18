"""
migrate_db.py — Initialize the MnesOS SQLite database.

Creates ``mnesos.db`` (or the path given as a CLI argument) with the correct
tables and indexes.  Safe to run multiple times; uses ``CREATE … IF NOT
EXISTS`` throughout.

Usage
-----
    python scripts/migrate_db.py                  # creates mnesos.db
    python scripts/migrate_db.py /path/to/my.db   # custom path
"""

import sys
from pathlib import Path

# Allow the script to be run from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from MnesOS.storage.sqlite3_store import SQLite3PhysicalComponent  # noqa: E402


def run(db_path: str = "mnesos.db") -> None:
    """Initialize the database at *db_path*."""
    store = SQLite3PhysicalComponent(db_path)
    store.initialize()
    print(f"[migrate_db] Database initialized: {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "mnesos.db"
    run(path)
