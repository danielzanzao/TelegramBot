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
        self.token = token
        self.application = Application.builder().token(token).connection_pool_size(8).pool_timeout(20).read_timeout(20).write_timeout(20).build()
        self.handlers = BotHandlers()
        self.reminder_scheduler = ReminderScheduler(self.application)
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("get_my_id", self.handlers.get_my_id_command))
        
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
            
            # Run the bot with polling
            self.application.run_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
            raise
