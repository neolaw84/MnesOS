"""
MnesOS utility: bulk cartridge ingestion.

Iterates subdirectories of a given root directory, validates each as a
cartridge using CartridgeLoader, and creates/upserts Cartridge +
CartridgeVersion records via the AbstractStorageComponent interface.

Usage::

    mnesos-ingest-cartridges --cartridge-dir cartridges/ \\
        --creator-id <user-uuid> [--upsert] [--db-path artifacts/mnesos.db]

    mnesos-ingest-cartridges --cartridge-dir cartridges/generic-rpg \\
        --creator-id <user-uuid> --version-tag 1.0.0

Options:
    --cartridge-dir PATH  Root directory to scan (required).
    --creator-id ID       User UUID to use as the creator for new records (required).
    --db-path PATH        Path to the SQLite3 database file [default: artifacts/mnesos.db].
    --version-tag TAG     Override the version tag for all ingested versions [default: 1.0.0].
    --upsert              If a cartridge with the same title already exists, add a new
                          version to it instead of creating a duplicate cartridge record.
    --visibility V        PUBLIC or PRIVATE [default: PUBLIC].
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from ..cartridge import CartridgeLoader
from ..storage import AbstractStorageComponent, SQLite3PhysicalComponent
from ..storage.models import Cartridge, CartridgeVersion, Visibility

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_checksum(*paths: Path) -> str:
    """Return SHA-256 over the concatenation of all files at the given paths."""
    h = hashlib.sha256()
    for p in paths:
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def _find_existing_cartridge(
    storage: AbstractStorageComponent,
    title: str,
) -> Cartridge | None:
    """Return the first cartridge with the given title, or None."""
    for c in storage.list_cartridges():
        if c.title == title:
            return c
    return None


def _ingest_directory(
    cartridge_dir: Path,
    storage: AbstractStorageComponent,
    creator_id: str,
    version_tag: str,
    upsert: bool,
    visibility: Visibility,
) -> None:
    """Validate and ingest a single cartridge directory."""
    title = cartridge_dir.name
    logger.info("Processing %r …", str(cartridge_dir))

    # ── Validate ──────────────────────────────────────────────────────────
    try:
        loaded = CartridgeLoader().load(str(cartridge_dir))
    except (ValueError, FileNotFoundError) as exc:
        logger.error("  Validation failed for %r: %s", title, exc)
        return

    logger.info("  ✓ Validated (yare keys: %s)", list(loaded.yare_config.keys()))

    # ── Resolve parent Cartridge ──────────────────────────────────────────
    cartridge: Cartridge | None = None
    if upsert:
        cartridge = _find_existing_cartridge(storage, title)
        if cartridge:
            logger.info("  ↩ Upsert: found existing cartridge %r (%s)", title, cartridge.id)

    if cartridge is None:
        cartridge = storage.create_cartridge(
            Cartridge(
                creator_id=creator_id,
                title=title,
                description="",
                genre="",
                visibility=visibility,
            )
        )
        logger.info("  + Created cartridge %r (%s)", title, cartridge.id)

    # ── Compute checksum ──────────────────────────────────────────────────
    yare_path = cartridge_dir / "yare.yaml"
    lore_path = cartridge_dir / "bot_lore.md"
    directives_path = cartridge_dir / "prompt_directives.yaml"
    checksum = _compute_checksum(yare_path, lore_path, directives_path)

    # ── Create CartridgeVersion ───────────────────────────────────────────
    version = storage.create_cartridge_version(
        CartridgeVersion(
            cartridge_id=cartridge.id,
            version_tag=version_tag,
            yare_spec=loaded.yare_config,
            prompt_directives=loaded.prompt_directives,
            bot_lore=loaded.lore_content,
            first_message=loaded.first_message,
            checksum=checksum,
        )
    )
    logger.info(
        "  + Created version %r (%s) checksum=%s",
        version_tag,
        version.id,
        checksum[:12],
    )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-ingest local cartridge directories into the MnesOS database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--cartridge-dir",
        required=True,
        metavar="PATH",
        help="Root directory to scan for cartridge subdirectories, "
             "or a direct cartridge directory containing yare.yaml.",
    )
    parser.add_argument(
        "--creator-id",
        required=True,
        metavar="ID",
        help="UUID of the UserAccount to record as the creator.",
    )
    parser.add_argument(
        "--db-path",
        default="artifacts/mnesos.db",
        metavar="PATH",
        help="Path to the SQLite3 database file [default: artifacts/mnesos.db].",
    )
    parser.add_argument(
        "--version-tag",
        default="1.0.0",
        metavar="TAG",
        help="Version tag applied to all ingested CartridgeVersion records [default: 1.0.0].",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Add new versions to existing cartridges (matched by directory name) "
             "instead of creating duplicate parent Cartridge records.",
    )
    parser.add_argument(
        "--visibility",
        default="PUBLIC",
        choices=["PUBLIC", "PRIVATE"],
        help="Visibility for newly created cartridges [default: PUBLIC].",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity [default: INFO].",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(message)s",
    )

    root = Path(args.cartridge_dir).resolve()
    if not root.exists():
        logger.error("cartridge-dir %r does not exist.", str(root))
        sys.exit(1)

    visibility = Visibility(args.visibility)

    # Instantiate storage strictly typed as AbstractStorageComponent.
    physical = SQLite3PhysicalComponent(db_path=args.db_path)
    physical.initialize()
    storage: AbstractStorageComponent = physical

    # Determine directories to process.
    if (root / "yare.yaml").exists():
        # Direct cartridge directory
        dirs = [root]
    else:
        # Scan subdirectories
        dirs = sorted(
            [d for d in root.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
        if not dirs:
            logger.warning("No subdirectories found in %r.", str(root))
            sys.exit(0)

    logger.info(
        "Found %d director%s to process.",
        len(dirs),
        "y" if len(dirs) == 1 else "ies",
    )

    success = 0
    failure = 0
    for d in dirs:
        # Skip hidden directories
        if d.name.startswith("."):
            continue
        # A cartridge directory must at least have yare.yaml
        if not (d / "yare.yaml").exists():
            logger.debug("  Skipping %r — no yare.yaml found.", d.name)
            continue
        try:
            _ingest_directory(
                cartridge_dir=d,
                storage=storage,
                creator_id=args.creator_id,
                version_tag=args.version_tag,
                upsert=args.upsert,
                visibility=visibility,
            )
            success += 1
        except (ValueError, OSError) as exc:
            logger.error("Error processing %r: %s", d.name, exc)
            failure += 1
        except Exception:
            logger.exception("Unexpected error processing %r", d.name)
            failure += 1

    logger.info("Done. %d succeeded, %d failed.", success, failure)
    if failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
