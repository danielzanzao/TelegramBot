"""
EnactusBOT - Main bot class and configuration
"""

import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers import BotHandlers
from reminder_system import ReminderScheduler

logger = logging.getLogger(__name__)

class EnactusBot:
    """Main bot class for EnactusBOT"""
    
    def __init__(self, token):
        """Initialize the bot with the given token"""
        # Force re-initialization of sheets manager now that env vars should be fully loaded
        from sheets_integration import sheets_manager
        sheets_manager._initialize_service()
        
        # Initialize Data Persistence (Cloud DB)
        self._initialize_data_persistence()
        
        self.token = token
        self.application = Application.builder().token(token).build()
        self.handlers = BotHandlers()
        self.reminder_scheduler = ReminderScheduler(self.application)
        self._setup_handlers()

    def _initialize_data_persistence(self):
        """Initialize cloud persistence (Google Sheets)"""
        try:
            from sheets_integration import sheets_manager
            from data_models import BotData, storage
            
            # 1. Ensure DB structure exists
            sheets_manager.ensure_db_structure()
            
            # 2. Load Members
            members = sheets_manager.load_members()
            if members:
                BotData.set_members(members)
                logger.info(f"Loaded {len(members)} members from Cloud DB")
            else:
                logger.info("No members found in Cloud DB. Syncing defaults...")
                sheets_manager.save_members(BotData.MEMBERS_DB) # Save current hardcoded list
                # Re-load to ensure consistency? No need, we just saved what we have.
                
            # 3. Load Reminders
            reminders = sheets_manager.load_reminders()
            if reminders:
                storage.reminders = reminders
                logger.info(f"Loaded {len(reminders)} reminders from Cloud DB")
                
            # 4. Set Save Callback
            storage.set_persistence_callback(sheets_manager.save_reminders)
            logger.info("Persistence callback configured")
            
        except Exception as e:
            logger.error(f"Failed to initialize data persistence: {e}")
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("cadastro", self.handlers.cadastro_command))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("get_my_id", self.handlers.get_my_id_command))
        self.application.add_handler(CommandHandler("refresh", self.handlers.refresh_command))
        
        # Callback query handlers for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback))
        
        # Message handlers for text input
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handlers.handle_text_input
        ))
        
        logger.info("Bot handlers configured successfully")
    
    def run(self):
        """Start the bot"""
        try:
            logger.info("EnactusBOT is starting...")
            
            # Run the bot with polling - versão simplificada
            self.application.run_polling()
            
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
            raise
