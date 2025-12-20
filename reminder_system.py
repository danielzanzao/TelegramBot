"""
Reminder system for EnactusBOT
Handles scheduling and sending reminder notifications using JobQueue
"""

import logging
import calendar
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from telegram.ext import ContextTypes
from data_models import storage, ReminderFrequency, ReminderType

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)

class ReminderScheduler:
    """Manages reminder scheduling and sending"""
    
    def __init__(self, application: 'Application'):
        self.application = application
        self._setup_schedule()
        
    def _setup_schedule(self):
        """Setup the recurring job"""
        if self.application.job_queue:
            # Run every 60 seconds
            self.application.job_queue.run_repeating(self._check_reminders_job, interval=60, first=10)
            logger.info("Reminder job scheduled via JobQueue")
        else:
            logger.error("JobQueue is not available in Application!")
    
    async def _check_reminders_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job callback to check and send reminders"""
        now = datetime.now()
        active_reminders = storage.get_active_reminders()
        
        # Verbose log only if there are active reminders to avoid spam
        if active_reminders:
            logger.info(f"Checking {len(active_reminders)} active reminders at {now.strftime('%H:%M:%S')}")
        
        for reminder in active_reminders:
            try:
                if self._should_send_reminder(reminder, now):
                    await self._send_reminder(reminder, context)
            except Exception as e:
                logger.error(f"Error processing reminder for user {reminder.user_id}: {e}")

    def _should_send_reminder(self, reminder, now: datetime) -> bool:
        """Check if reminder should be sent now"""
        # 1. Check Day
        if reminder.frequency == ReminderFrequency.WEEKLY:
            if reminder.day_of_week is not None and now.weekday() != reminder.day_of_week:
                return False
        elif reminder.frequency == ReminderFrequency.MONTHLY:
            if reminder.day_of_month is not None:
                _, last_day_of_month = calendar.monthrange(now.year, now.month)
                target_day = min(reminder.day_of_month, last_day_of_month)
                if now.day != target_day:
                    return False
        
        # 2. Check Time (Catch-up logic: if now >= time)
        # We compare time tuples (hour, minute) to ignore seconds precision issues
        now_time = (now.hour, now.minute)
        rem_time = (reminder.time_of_day.hour, reminder.time_of_day.minute)
        
        if now_time < rem_time:
            # Too early
            return False
            
        # 3. Check duplicate (already sent today?)
        if reminder.last_sent:
            time_since = now - reminder.last_sent
            # Avoid double sending within short window (safety)
            if time_since < timedelta(minutes=1):
                return False
            
            # If already sent today
            if reminder.last_sent.date() == now.date():
                return False
        
        logger.info(f"Triggering reminder for {reminder.member_name} (Scheduled: {reminder.time_of_day}, Now: {now.time()})")
        return True

    
    async def _send_reminder(self, reminder, context: ContextTypes.DEFAULT_TYPE):
        """Send specific reminder message"""
        if reminder.type == ReminderType.PCH:
            message = f"""
📅 **Lembrete PCH - Enactus**

Olá {reminder.member_name}!

Lembre-se de atualizar a Planilha de Controle de Horas (PCH).
O prazo é todo domingo às 12:00!

🔗 **Link da PCH:**
https://docs.google.com/spreadsheets/d/1FsWlDPT1rSMHaXdXPycVTL3jyz6n2sLs0qVZF2in0m0/edit?gid=2142965742#gid=2142965742
            """
        else:
            message = f"""
🔔 **Lembrete - Marcar HO**

Olá {reminder.member_name}! 👋

Hora de registrar suas atividades e manter as HOs em dia! 📊

Use o comando /start ou clique no botão abaixo.
            """
            
        await context.bot.send_message(
            chat_id=reminder.user_id,
            text=message,
            parse_mode='Markdown'
        )
        
        # Update last sent
        storage.update_reminder_last_sent(reminder.user_id, reminder.type, datetime.now())
        logger.info(f"Sent {reminder.type.value} reminder to {reminder.member_name}")