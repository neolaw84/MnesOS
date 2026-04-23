"""
delete_db.py — Remove the MnesOS SQLite database file.

Deletes ``mnesos.db`` (or the path given as a CLI argument).  Safe to call
even when the file does not exist.

Usage
-----
    python scripts/delete_db.py                  # deletes mnesos.db
    python scripts/delete_db.py /path/to/my.db   # custom path
"""

import sys
from pathlib import Path


def run(db_path: str = "mnesos.db") -> None:
    """Delete the database file at *db_path* if it exists."""
    p = Path(db_path)
    if p.exists():
        p.unlink()
        print(f"[delete_db] Removed: {db_path}")
    else:
        print(f"[delete_db] Nothing to remove (file not found): {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "mnesos.db"
    run(path)
