"""
Reminder system for EnactusBOT
Handles scheduling and sending reminder notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import TYPE_CHECKING
from data_models import storage, ReminderFrequency

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)

class ReminderScheduler:
    """Manages reminder scheduling and sending"""
    
    def __init__(self, application: 'Application'):
        self.application = application
        self.is_running = False
        
    async def start_scheduler(self):
        """Start the reminder scheduler"""
        self.is_running = True
        logger.info("Reminder scheduler started")
        
        while self.is_running:
            try:
                await self._check_and_send_reminders()
                # Check every 5 minutes
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def stop_scheduler(self):
        """Stop the reminder scheduler"""
        self.is_running = False
        logger.info("Reminder scheduler stopped")
    
    async def _check_and_send_reminders(self):
        """Check if any reminders need to be sent"""
        now = datetime.now()
        current_time = now.time()
        
        for reminder in storage.get_active_reminders():
            if self._should_send_reminder(reminder, now, current_time):
                await self._send_reminder(reminder, now)
    
    def _should_send_reminder(self, reminder, now: datetime, current_time: time) -> bool:
        """Check if reminder should be sent now"""
        # Check if it's close to the reminder time (within 5 minutes)
        reminder_time = reminder.time_of_day
        time_diff = abs((current_time.hour * 60 + current_time.minute) - 
                       (reminder_time.hour * 60 + reminder_time.minute))
        
        if time_diff > 5:  # More than 5 minutes difference
            return False
        
        # Check frequency
        if reminder.last_sent is None:
            return True
        
        time_since_last = now - reminder.last_sent
        
        if reminder.frequency == ReminderFrequency.DAILY:
            return time_since_last >= timedelta(days=1)
        elif reminder.frequency == ReminderFrequency.WEEKLY:
            return time_since_last >= timedelta(days=7)
        elif reminder.frequency == ReminderFrequency.MONTHLY:
            return time_since_last >= timedelta(days=30)
        
        return False
    
    async def _send_reminder(self, reminder, now: datetime):
        """Send reminder message to user"""
        try:
            message = f"""
🔔 **Lembrete - Marcar HO**

Olá {reminder.member_name}! 👋

É hora de registrar suas horas de trabalho da Enactus.

Não se esqueça de marcar suas HO para manter seus registros em dia! 📊

Use o comando /start para começar.
            """
            
            await self.application.bot.send_message(
                chat_id=reminder.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            # Update last sent time
            storage.update_reminder_last_sent(reminder.user_id, now)
            logger.info(f"Reminder sent to user {reminder.user_id} ({reminder.member_name})")
            
        except Exception as e:
            logger.error(f"Failed to send reminder to user {reminder.user_id}: {e}")