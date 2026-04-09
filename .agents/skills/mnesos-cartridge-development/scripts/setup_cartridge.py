import os
import sys
import shutil

def setup_cartridge(game_name):
    """
    Creates a new MnesOS cartridge using the assets provided in the skill directory.
    """
    base_dest = os.path.join('data', 'cartridges', game_name)
    skill_assets = os.path.join('.agents', 'skills', 'mnesos-cartridge-development', 'assets')

    if os.path.exists(base_dest):
        print(f"Error: Cartridge '{game_name}' already exists at {base_dest}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(skill_assets):
        print(f"Error: Could not find assets folder at {skill_assets}. Are you running this from the workspace root?", file=sys.stderr)
        sys.exit(1)

    try:
        os.makedirs(base_dest)
        
        # Copy template files
        shutil.copy(os.path.join(skill_assets, 'bot_lore.md'), os.path.join(base_dest, 'bot_lore.md'))
        shutil.copy(os.path.join(skill_assets, 'prompt_directives.yaml'), os.path.join(base_dest, 'prompt_directives.yaml'))
        shutil.copy(os.path.join(skill_assets, 'yare.yaml'), os.path.join(base_dest, 'yare.yaml'))

        print(f"Successfully created Cartridge '{game_name}' at {base_dest} using the mnesos-cartridge-development templates.")
    except OSError as e:
        print(f"Error: Could not copy template files: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_cartridge.py <cartridge-name>")
        sys.exit(1)
        
    game_name = sys.argv[1]
    setup_cartridge(game_name)
