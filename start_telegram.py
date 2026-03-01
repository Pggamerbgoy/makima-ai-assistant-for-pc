import os
import sys
import logging
import threading
from dotenv import load_dotenv

# Load .env BEFORE imports that might use env vars at module level
load_dotenv()

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.ai_handler import AIHandler
from core.eternal_memory import EternalMemory
from core.command_router import CommandRouter
from remote.telegram_remote import TelegramRemote

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("Makima.TelegramLauncher")

def main():
    load_dotenv()
    
    logger.info("🌸 Starting Makima Telegram Bot...")
    
    # 1. Initialize core components (V4 Manager)
    from core.makima_manager import MakimaManager
    manager = MakimaManager()
    manager.start()
    
    # 2. Initialize and start Telegram Remote
    remote = TelegramRemote(manager)
    
    logger.info("✅ Telegram bot is starting. You can now message your bot.")
    remote.start()

if __name__ == "__main__":
    main()
