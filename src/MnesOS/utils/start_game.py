"""
MnesOS utility: bootstrap a new game instance.

Creates a default Persona and a GameInstance linked to a specific CartridgeVersion.
Outputs the Game Instance ID which can be pasted into the Web Client settings.

Usage::

    mnesos-start-game --user-id 12345 --cartridge-id <cartridge-uuid>

Options:
    --user-id ID          The ID of the user playing the game (required).
    --cartridge-id ID     The Cartridge ID to play (required).
    --instance-id ID      Optional. A specific UUID to use for the game instance.
    --db-path PATH        Path to the SQLite3 database file [default: artifacts/mnesos.db].
"""

import argparse
import logging
import sys

from ..storage import SQLite3PhysicalComponent
from ..storage.models import GameInstance, GameStatus, Persona

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap a new Game Instance for a specific Cartridge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--user-id",
        required=True,
        metavar="ID",
        help="The user ID of the player.",
    )
    parser.add_argument(
        "--cartridge-id",
        required=True,
        metavar="ID",
        help="The Cartridge ID you want to play.",
    )
    parser.add_argument(
        "--instance-id",
        metavar="ID",
        help="A specific ID string to assign to the game instance. Optional.",
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

    storage = SQLite3PhysicalComponent(db_path=args.db_path)
    storage.initialize()

    # Get the latest version of the specified cartridge
    versions = storage.list_cartridge_versions(args.cartridge_id)
    if not versions:
        logger.error(f"No versions found for cartridge {args.cartridge_id}. Cannot start game.")
        sys.exit(1)
        
    latest_version = versions[-1] # Usually versions are returned in order, taking the last one or just versions[0]
    # In MnesOS alpha, let's just grab the first one
    latest_version = versions[0]

    # Create a default Persona for the user
    persona = Persona(
        user_id=args.user_id,
        name="Player",
        pronoun_sub="they",
        pronoun_obj="them",
        pronoun_poss="their",
        pronoun_poss_obj="theirs",
        appearance="A mysterious wanderer.",
        background="You have no memory of your past.",
        personality="Cautious but determined."
    )
    created_persona = storage.create_persona(persona)
    logger.info(f"Created Persona: {created_persona.id}")

    # Create the Game Instance
    instance = GameInstance(
        user_id=args.user_id,
        persona_id=created_persona.id,
        version_id=latest_version.id,
        status=GameStatus.ACTIVE,
    )
    
    created_instance = storage.create_game_instance(instance)
    
    # If the user requested a specific instance ID, we have to override it directly in the DB
    # because the create_game_instance auto-generates it.
    final_instance_id = created_instance.id
    if args.instance_id:
        conn = storage._get_conn()
        try:
            with conn:
                conn.execute(
                    "UPDATE game_instances SET id = ? WHERE id = ?",
                    (args.instance_id, created_instance.id),
                )
            final_instance_id = args.instance_id
            logger.info(f"Overridden Game Instance ID to requested: {final_instance_id}")
        except Exception as e:
            logger.error(f"Failed to override instance ID. Error: {e}")
            sys.exit(1)

    print("\n" + "="*50)
    print(f"SUCCESS! Your game instance is ready.")
    print(f"User ID:            {args.user_id}")
    print(f"Game Instance ID:   {final_instance_id}")
    print("="*50 + "\n")
    print("Copy the 'Game Instance ID' above and paste it into your Web Client settings!")


if __name__ == "__main__":
    main()
