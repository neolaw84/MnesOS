import os
import sys
from dotenv import load_dotenv

# Ensure MnesOS is in the path or run from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from MnesOS.orchestrator import Orchestrator
from langchain_openai import ChatOpenAI

def main():
    load_dotenv()
    
    # Check if OPENAI_API_KEY is present
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set your OPENAI_API_KEY in the .env file.")
        return

    # MnesOS expects langchain chat models for its nodes.
    # The models handle the generation and parsing using tool binding.
    # Pass them cleanly to the Orchestrator.
    llm = ChatOpenAI(model="gpt-4o")
    
    cartridge_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Loading Dark Fantasy Cartridge from {cartridge_dir}...\n")
    try:
        orch = Orchestrator(cartridge_dir, llm_director=llm, llm_narrator=llm, llm_npc=llm)
    except Exception as e:
        print(f"Failed to load cartridge or orchestrator: {e}")
        return
        
    print("Welcome to Yharn, the Cursed Capital.")
    print("Press Ctrl+C to exit.\n")
    
    while True:
        try:
            action = input("> ")
            if not action.strip():
                continue
            if action.lower() in ("quit", "exit"):
                break
                
            print(f"--- PLAYER ACTION ---")
            print(f"> {action}\n")
            
            orch.state["client_messages"].append({"role": "user", "content": action})
            invoke_result = orch._app.invoke(orch.state)
            orch._state = invoke_result
            
            print("---debug starts---")
            print(invoke_result)
            print("---debug-ends---")
            
            response = orch._extract_narrator_response()
            print(f"--- SYSTEM RESPONSE ---")
            print(f"{response}\n")
            
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error processing turn: {e}")
            break

if __name__ == "__main__":
    main()
