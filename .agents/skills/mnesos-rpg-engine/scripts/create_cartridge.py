import os
import sys
import argparse

def create_cartridge(game_name):
    """
    Creates a new MnesOS cartridge with the basic file structure.
    """
    base_path = os.path.join('cartridges', game_name)
    if os.path.exists(base_path):
        print(f"Error: Cartridge '{game_name}' already exists at {base_path}", file=sys.stderr)
        sys.exit(1)

    try:
        os.makedirs(base_path)
        with open(os.path.join(base_path, 'prompt_directives.yaml'), 'w') as f:
            f.write("director: ''\nnarrator: ''\nnpc: ''\n")
        with open(os.path.join(base_path, 'bot_lore.md'), 'w') as f:
            f.write(f"# {game_name.replace('-', ' ').title()}\n\n")
        with open(os.path.join(base_path, 'yare.yaml'), 'w') as f:
            f.write("version: '1.0'\nstate_schema:\n\nevents:\n")
        print(f"Successfully created cartridge '{game_name}' at {base_path}")
    except OSError as e:
        print(f"Error: Could not create cartridge directory or files: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a new MnesOS game cartridge.')
    parser.add_argument('game_name', type=str, help='The name of the game cartridge (e.g., my-awesome-game).')
    args = parser.parse_args()

    create_cartridge(args.game_name)
