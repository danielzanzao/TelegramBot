#!/usr/bin/env python3
"""
EnactusBOT - Telegram bot for Enactus work hours management
Main entry point for the application
"""

import os
import logging
from dotenv import load_dotenv
from bot import EnactusBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the Enactus Telegram bot"""
    try:
        # Get bot token from environment variables
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            return
        
        # Initialize and start the bot
        enactus_bot = EnactusBot(bot_token)
        logger.info("Starting EnactusBOT...")
        enactus_bot.run()
        
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")

if __name__ == "__main__":
    main()
