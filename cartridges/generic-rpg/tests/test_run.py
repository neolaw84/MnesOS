import os
import sys

# Configure path to import MnesOS
current_dir = os.path.dirname(os.path.abspath(__file__))
generic_rpg_dir = os.path.dirname(current_dir)
mnesos_src_dir = os.path.abspath(os.path.join(generic_rpg_dir, '..', '..', 'src'))
sys.path.insert(0, mnesos_src_dir)

from MnesOS import Orchestrator

def main():
    print(f"Loading generic-rpg cartridge from {generic_rpg_dir}")
    
    # We omit LLMs to run in dry-run mode
    # Or, we could mock LLMs if we wanted but dry-run mode should work to verify loading and state.
    orch = Orchestrator(cartridge_dir=generic_rpg_dir)
    
    print("Initial State Variables:")
    print("Player:", orch.state["bot_memory"].get("player"))
    print("NPC:", orch.state["bot_memory"].get("npc"))
    print("Location:", orch.state["bot_memory"].get("current_location"))
    print("Inventory:", orch.state["bot_memory"].get("inventory"))

    print("\nSimulating a sequence of events manually to ensure YARE execution...")
    # Because LLM is none, we must manually trigger events via state manipulations
    # Just checking that Orchestrator compiles and runs dry turns without errors.
    
    response = orch.process_turn("I swing my sword at the goblin!")
    
    print("\nTurn Processed (dry run mode):")
    print("Narrator response (should be empty in dry-run):", repr(response))
    print("Agent messages (tools called):", orch.state["agent_messages"])
    print("System Notes:", orch.state["system_notes"])

if __name__ == '__main__':
    main()
