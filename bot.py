"""
EnactusBOT - Main bot class and configuration
"""

import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers import BotHandlers
from reminder_system import ReminderScheduler
from approval_system import ApprovalSystem  # <<< NOVO

logger = logging.getLogger(__name__)

class EnactusBot:
    """Main bot class for EnactusBOT"""
    
    def __init__(self, token):
        """Initialize the bot with the given token"""
        self.token = token
        self.application = Application.builder().token(token).build()
        self.handlers = BotHandlers()
        self.reminder_scheduler = ReminderScheduler(self.application)

        # --- Aprovação: instancia e expõe no bot_data ---
        self.approval = ApprovalSystem(self.application)
        self.approval.initialize_default_managers()
        self.application.bot_data['approval'] = self.approval

        self._setup_handlers()
        self._setup_jobs()   # agenda notificação semanal
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("get_my_id", self.handlers.get_my_id_command))
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_text_input))
        logger.info("Bot handlers configured successfully")

    # === Notificação semanal para gerentes ===
    def _setup_jobs(self):
        from datetime import time as dtime
        jq = self.application.job_queue

        async def weekly_approval_job(context):
            await self.approval.send_weekly_approval_notifications()

        # Segunda-feira 09:00 (horário do servidor)
        jq.run_daily(weekly_approval_job, time=dtime(hour=9, minute=0), days=(0,))
        logger.info("Weekly approval notification job scheduled: Monday 09:00")
    
    def run(self):
        """Start the bot"""
        try:
            logger.info("EnactusBOT is starting...")
            self.application.run_polling()
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
            raise
