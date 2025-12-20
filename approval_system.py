"""
Approval System for EnactusBOT
Handles manager approval workflow and weekly notifications
"""

import logging
import asyncio
import uuid
from datetime import datetime, timedelta, time
from typing import List, Optional, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from data_models import storage, Manager, WorkHour, BotData
from sheets_integration import sheets_manager

logger = logging.getLogger(__name__)


class ApprovalSystem:
    """Manages the approval workflow for work hours"""

    def __init__(self, bot_application: Application):
        self.bot_application = bot_application
        self.approval_sessions: Dict[int, Dict] = {}  # user_id -> session data

    def initialize_default_managers(self):
        """Initialize default managers from BotData configuration"""
        from data_models import BotData

        for telegram_user_id, name, managed_areas in BotData.DEFAULT_MANAGERS:
            manager = Manager(telegram_user_id=telegram_user_id,
                              name=name,
                              managed_areas=managed_areas,
                              is_active=True)
            storage.add_manager(manager)

        logger.info(
            f"Initialized {len(BotData.DEFAULT_MANAGERS)} default managers")

    async def send_weekly_approval_notifications(self):
        """Send weekly notifications to managers about pending approvals"""
        logger.info("Checking for managers with pending approvals...")

        for manager in storage.managers:
            if not manager.is_active:
                continue

            pending_hours = storage.get_pending_work_hours_for_manager(manager)
            if not pending_hours:
                continue

            # Send notification to manager
            await self._send_approval_notification(manager, pending_hours)

    async def _send_approval_notification(self, manager: Manager,
                                          pending_hours: List[WorkHour]):
        """Send approval notification to a specific manager"""
        count = len(pending_hours)
        areas_text = ", ".join(manager.managed_areas)

        text = f"""
🔔 **Notificação de Aprovação - Semanal**

Olá **{manager.name}**!

Você tem **{count} HO{'s' if count != 1 else ''}** pendente{'s' if count != 1 else ''} de aprovação para as áreas/projetos: {areas_text}

Clique no botão abaixo para iniciar o processo de aprovação.
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔍 Revisar HO's Pendentes",
                    callback_data=f"start_approval_{manager.telegram_user_id}")
            ],
            [
                InlineKeyboardButton(
                    "📊 Ver Estatísticas",
                    callback_data=f"approval_stats_{manager.telegram_user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await self.bot_application.bot.send_message(
                chat_id=manager.telegram_user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown')
            logger.info(
                f"Approval notification sent to manager {manager.name} ({manager.telegram_user_id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to send approval notification to {manager.name}: {e}")

    def start_approval_session(self, user_id: int, manager: Manager):
        """Start an approval session for a manager"""
        pending_hours = storage.get_pending_work_hours_for_manager(manager)

        if not pending_hours:
            return None

        self.approval_sessions[user_id] = {
            'manager': manager,
            'pending_hours': pending_hours,
            'current_index': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'started_at': datetime.now()
        }

        return self.approval_sessions[user_id]

    def get_current_approval_item(self, user_id: int) -> Optional[WorkHour]:
        """Get the current work hour being reviewed in approval session"""
        session = self.approval_sessions.get(user_id)
        if not session:
            return None

        pending_hours = session['pending_hours']
        current_index = session['current_index']

        if current_index >= len(pending_hours):
            return None

        return pending_hours[current_index]

    def process_approval_decision(self, user_id: int, ho_id: str,
                                  decision: str, manager_name: str):
        """Process manager's approval decision"""
        session = self.approval_sessions.get(user_id)
        if not session:
            return False

        # Update work hour status
        approval_date = datetime.now()
        status = "Aprovado" if decision == "approve" else "Reprovado"

        storage.update_work_hour_status(ho_id, status, manager_name,
                                        approval_date)

        # Update session counts
        if decision == "approve":
            session['approved_count'] += 1
        else:
            session['rejected_count'] += 1

        # Move to next item
        session['current_index'] += 1

        # Sync with Google Sheets if available
        if sheets_manager.is_available():
            try:
                # Find the work hour and sync the updated status
                for work_hour in storage.work_hours:
                    if work_hour.ho_id == ho_id:
                        sheets_manager.update_work_hour_status(work_hour)
                        break
            except Exception as e:
                logger.error(
                    f"Failed to sync approval status to Google Sheets: {e}")

        return True

    def has_more_items(self, user_id: int) -> bool:
        """Check if there are more items to review in the approval session"""
        session = self.approval_sessions.get(user_id)
        if not session:
            return False

        return session['current_index'] < len(session['pending_hours'])

    def finish_approval_session(self, user_id: int) -> Dict:
        """Finish approval session and return summary"""
        session = self.approval_sessions.get(user_id)
        if not session:
            return {}

        summary = {
            'approved_count': session['approved_count'],
            'rejected_count': session['rejected_count'],
            'total_reviewed':
            session['approved_count'] + session['rejected_count'],
            'manager_name': session['manager'].name,
            'areas': session['manager'].managed_areas
        }

        # Clean up session
        del self.approval_sessions[user_id]

        return summary

    def get_approval_statistics(self, manager: Manager) -> Dict:
        """Get approval statistics for a manager"""
        all_hours = [
            wh for wh in storage.work_hours
            if wh.project_area in manager.managed_areas
        ]

        total = len(all_hours)
        pending = len([wh for wh in all_hours if wh.status == "Pendente"])
        approved = len([wh for wh in all_hours if wh.status == "Aprovada"])
        rejected = len([wh for wh in all_hours if wh.status == "Reprovada"])

        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'areas': manager.managed_areas
        }


# Global approval system instance
approval_system = None


def initialize_approval_system(bot_application: Application):
    """Initialize the global approval system"""
    global approval_system
    approval_system = ApprovalSystem(bot_application)
    return approval_system
