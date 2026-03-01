import os
import sys
from dotenv import load_dotenv

# Load env before imports
load_dotenv()

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.makima_manager import MakimaManager

def test():
    print("🚀 Initializing Makima Manager for testing...")
    manager = MakimaManager(text_mode=True)
    manager.start()

    test_commands = [
        "what's going on?",             # Persona check
        "good morning",               # P5 check (Briefing)
        "play chill music",            # P6 check (detect_mood)
        "play bad blood on youtube",   # P3 check (YouTube pattern)
        "what is the time?",           # P7 check (Stateful - no cache)
        "screenshot",                 # P9 check (System control)
        "help me with research",       # V4 Swarm check
    ]

    for cmd in test_commands:
        print(f"\n--- Testing Command: '{cmd}' ---")
        response = manager.handle(cmd)
        print(f"Response: {response}")

if __name__ == "__main__":
    test()
