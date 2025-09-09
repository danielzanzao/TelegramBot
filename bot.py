# bot.py
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers import BotHandlers
from reminder_system import ReminderScheduler
from approval_system import ApprovalSystem
from telegram.error import TelegramError   # <<< importa para usar no error handler

logger = logging.getLogger(__name__)

class EnactusBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.handlers = BotHandlers()
        self.reminder_scheduler = ReminderScheduler(self.application)

        # --- Aprovação
        self.approval = ApprovalSystem(self.application)
        self.approval.initialize_default_managers()
        self.application.bot_data['approval'] = self.approval

        self._setup_handlers()
        self._setup_jobs()
        self._setup_error_handler()   # <<< adiciona error handler aqui

    def _setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("get_my_id", self.handlers.get_my_id_command))
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_text_input))
        logger.info("Bot handlers configurados")

    def _setup_jobs(self):
        from datetime import time as dtime
        jq = self.application.job_queue

        async def weekly_approval_job(context):
            await self.approval.send_weekly_approval_notifications()

        jq.run_daily(weekly_approval_job, time=dtime(hour=9, minute=0), days=(0,))
        logger.info("Job semanal de aprovação agendado")

    def _setup_error_handler(self):   # <<< novo método
        async def _on_error(update, context):
            logger.exception("Erro durante processamento de update: %s", context.error)
        self.application.add_error_handler(_on_error)

    def run(self):
        logger.info("EnactusBOT iniciando…")
        self.application.run_polling()
