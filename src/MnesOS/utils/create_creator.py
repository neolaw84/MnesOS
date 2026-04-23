"""
MnesOS utility: create a CREATOR user account.

This script creates a new UserAccount with the CREATOR role in the local SQLite database.
This is necessary before ingesting cartridges, as the database enforces a foreign key
constraint requiring the cartridge creator to exist.

Usage::

    mnesos-create-creator --username local-test-user --id local-test-user

Options:
    --username NAME   The username for the new account (required).
    --id ID           A specific UUID/ID string to use for the user. If omitted, a random UUID is generated.
    --email EMAIL     The email for the new account [default: dummy@example.com].
    --db-path PATH    Path to the SQLite3 database file [default: artifacts/mnesos.db].
"""

import argparse
import logging
import sys

from ..storage import SQLite3PhysicalComponent
from ..storage.models import UserAccount, UserRole

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new CREATOR user account in the MnesOS database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--username",
        required=True,
        metavar="NAME",
        help="The username for the new creator account.",
    )
    parser.add_argument(
        "--id",
        metavar="ID",
        help="A specific ID string to assign to the user. Optional.",
    )
    parser.add_argument(
        "--email",
        default="dummy@example.com",
        metavar="EMAIL",
        help="The email for the account [default: dummy@example.com].",
    )
    parser.add_argument(
        "--db-path",
        default="artifacts/mnesos.db",
        metavar="PATH",
        help="Path to the SQLite3 database file [default: artifacts/mnesos.db].",
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

    # Instantiate storage and ensure schema exists
    storage = SQLite3PhysicalComponent(db_path=args.db_path)
    storage.initialize()

    # Create the UserAccount model
    user = UserAccount(
        username=args.username,
        email=args.email,
        password_hash="dummy_hash",  # Dummy hash since auth is currently bypassed for local testing
        role=UserRole.CREATOR,
    )
    
    # If a specific ID is requested, we apply it. 
    # Note: storage.create_user normally auto-generates this, so we will manually insert if an ID is provided
    # or override the auto-generation after initialization.
    if args.id:
        user.id = args.id
        user.created_at = None  # Will be set by create_user or manually
        
        # We need to manually insert to force the ID, because create_user overwrites user.id
        from datetime import datetime, timezone
        user.created_at = datetime.now(timezone.utc)
        conn = storage._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO user_accounts
                        (id, username, email, password_hash, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.id,
                        user.username,
                        user.email,
                        user.password_hash,
                        user.role.value,
                        user.created_at.isoformat(),
                    ),
                )
            logger.info("Successfully created CREATOR user '%s' with specific ID: %s", user.username, user.id)
        except Exception as e:
            logger.error("Failed to create user. Ensure the ID or username/email isn't already taken. Error: %s", e)
            sys.exit(1)
    else:
        # Standard creation with auto-generated ID
        try:
            created_user = storage.create_user(user)
            logger.info("Successfully created CREATOR user '%s' with auto-generated ID: %s", created_user.username, created_user.id)
        except Exception as e:
            logger.error("Failed to create user. Ensure the username/email isn't already taken. Error: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
