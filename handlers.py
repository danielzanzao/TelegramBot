# handlers.py
"""
Telegram bot handlers for EnactusBOT
"""

import logging
import re
import uuid
from datetime import datetime, date, time
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from data_models import BotData, storage, WorkHour, Reminder, ReminderFrequency
from sheets_integration import sheets_manager
# Sistema de aprovação (instância global é inicializada no boot do bot)
#from approval_system import approval_system

logger = logging.getLogger(__name__)


class BotHandlers:
    """Class containing all bot message and callback handlers"""

    # ==================== COMANDOS BÁSICOS ====================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        is_manager = storage.get_manager_by_user_id(user.id) is not None

        welcome_text = (
            f"🌟 Olá {user.first_name}, bem-vindo ao EnactusBOT! 🌟\n\n"
            "Sou seu assistente para gerenciamento de horas de trabalho da Enactus.\n\n"
            "Use os botões abaixo para navegar:"
        )

        keyboard = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("📈 Google Sheets", callback_data="sheets_menu")],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
        ]
        if is_manager:
            keyboard.insert(1, [InlineKeyboardButton("🛡️ Aprovar HOs", callback_data="manager_approval_menu")])
        keyboard.append([InlineKeyboardButton("❓ Ajuda", callback_data="help")])

        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "📖 **Ajuda - EnactusBOT**\n\n"
            "**Comandos disponíveis:**\n"
            "• /start - Iniciar o bot e ver menu principal\n"
            "• /help - Mostrar esta mensagem de ajuda\n"
            "• /get_my_id - Descobrir seu ID do Telegram (para configurar gerentes)\n\n"
            "**Funcionalidades:**\n"
            "• **Marcar HO**: Registrar suas horas de trabalho\n"
            "• **Central Enactus**: Acessar drive compartilhado\n\n"
            "**Como marcar HO:**\n"
            "1. Clique em \"Marcar HO\"\n"
            "2. Selecione seu nome\n"
            "3. Escolha se é tarefa de área ou projeto\n"
            "4. Selecione a área/projeto específico\n"
            "5. Informe data e horas\n"
            "6. Escolha modalidade (Presencial/EAD)\n"
            "7. Confirme os dados\n\n"
            "Dúvidas? Entre em contato com a coordenação! 🤝"
        )

        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def get_my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /get_my_id command - useful for manager configuration"""
        user_id = update.message.from_user.id
        first_name = update.message.from_user.first_name or "Usuário"
        username = update.message.from_user.username

        text = (
            "🆔 **Seu ID do Telegram**\n\n"
            f"**Nome:** {first_name}\n"
            f"**Username:** @{username if username else 'não definido'}\n"
            f"**ID:** `{user_id}`\n\n"
            "📋 **Como usar:**\n"
            "Para configurar gerentes, adicione esta linha no arquivo `data_models.py`:\n"
            f"```\n({user_id}, \"{first_name}\", [\"área1\", \"área2\"]),\n```\n\n"
            "**Áreas disponíveis:** DAF, GP, MKT, QLD, PSD\n"
            "**Projetos disponíveis:** Odoyá, Maná, Gelé"
        )

        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ==================== ROUTER DE CALLBACKS ====================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        logger.info("approval in bot_data? %s", 'approval' in query._bot.application.bot_data)
        user_id = update.effective_user.id
        session = storage.get_user_session(user_id)
        data = query.data

        # Menu principal e seções existentes
        if data == "main_menu":
            await self._show_main_menu(query)
        elif data == "mark_ho":
            await self._start_ho_flow(query, session)
        elif data == "help":
            await self._show_help(query)
        elif data == "sheets_menu":
            await self._show_sheets_menu(query, session)
        elif data == "sync_all_hours":
            await self._sync_all_hours(query, session)
        elif data == "view_sheets":
            await self._view_sheets_url(query, session)
        elif data == "reminders":
            await self._show_reminders_menu(query, session)
        elif data == "setup_reminder":
            await self._start_reminder_setup(query, session)
        elif data == "view_reminder":
            await self._view_current_reminder(query, session)
        elif data == "disable_reminder":
            await self._disable_reminder(query, session)

        # Fluxo de marcação HO
        elif data.startswith("reminder_member_"):
            await self._handle_reminder_member_selection(query, session)
        elif data.startswith("reminder_frequency_"):
            await self._handle_reminder_frequency_selection(query, session)
        elif data.startswith("member_"):
            await self._handle_member_selection(query, session)
        elif data.startswith("task_type_"):
            await self._handle_task_type_selection(query, session)
        elif data.startswith("project_"):
            await self._handle_project_selection(query, session)
        elif data.startswith("area_"):
            await self._handle_area_selection(query, session)
        elif data.startswith("modality_"):
            await self._handle_modality_selection(query, session)
        elif data == "confirm_ho":
            await self._confirm_ho(query, session)
        elif data == "confirm_reminder":
            await self._confirm_reminder_setup(query, session)
        elif data == "mark_another_same":
            await self._mark_another_same(query, session)
        elif data == "mark_another_different":
            await self._mark_another_different(query, session)
        elif data == "finish_and_survey":
            await self._finish_and_survey(query, session)
        elif data == "finish_no_survey":
            await self._finish_no_survey(query, session)
        elif data == "cancel":
            await self._cancel_process(query, session)

        # ==================== APROVAÇÃO (GERENTES) ====================
        elif data == "manager_approval_menu":
            await self._show_manager_approval_menu(query)
        elif data.startswith("start_approval_"):
            await self._start_approval_flow(query)
        elif data.startswith("approve_"):
            await self._handle_approval_decision(query, decision="approve")
        elif data.startswith("reject_"):
            await self._handle_approval_decision(query, decision="reject")
        elif data == "next_approval":
            await self._show_next_approval_item(query)
        elif data == "finish_approval":
            await self._finish_approval_flow(query)
        elif data.startswith("approval_stats_"):
            await self._show_approval_stats(query)

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input from users"""
        user_id = update.effective_user.id
        session = storage.get_user_session(user_id)
        text = update.message.text.strip()

        if 'waiting_for' not in session:
            # No active session, show main menu
            await self._show_main_menu_message(update)
            return

        waiting_for = session['waiting_for']

        if waiting_for == 'description':
            await self._handle_description_input(update, session, text)
        elif waiting_for == 'date':
            await self._handle_date_input(update, session, text)
        elif waiting_for == 'hours':
            await self._handle_hours_input(update, session, text)
        elif waiting_for == 'reminder_time':
            await self._handle_reminder_time_input(update, session, text)

    # ==================== MENUS PRINCIPAIS ====================

    async def _show_main_menu(self, query):
        user_id = query.from_user.id
        is_manager = storage.get_manager_by_user_id(user_id) is not None
        texto = "🌟 **EnactusBOT - Menu Principal**\n\nEscolha uma opção abaixo:"
        teclado = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("📈 Google Sheets", callback_data="sheets_menu")],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
        ]
        if is_manager:
            teclado.insert(1, [InlineKeyboardButton("🛡️ Aprovar HOs", callback_data="manager_approval_menu")])
        teclado.append([InlineKeyboardButton("❓ Ajuda", callback_data="help")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")

    async def _show_main_menu_message(self, update):
        user = update.effective_user
        is_manager = storage.get_manager_by_user_id(user.id) is not None
        texto = "🌟 **EnactusBOT - Menu Principal**\n\nEscolha uma opção abaixo:"
        teclado = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("📈 Google Sheets", callback_data="sheets_menu")],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
        ]
        if is_manager:
            teclado.insert(1, [InlineKeyboardButton("🛡️ Aprovar HOs", callback_data="manager_approval_menu")])
        teclado.append([InlineKeyboardButton("❓ Ajuda", callback_data="help")])
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")

    async def _show_help(self, query):
        """Show help information"""
        help_text = (
            "📖 **Ajuda - EnactusBOT**\n\n"
            "**Funcionalidades:**\n"
            "• **Marcar HO**: Registrar suas horas de trabalho\n"
            "• **Central Enactus**: Acessar drive compartilhado\n\n"
            "**Como marcar HO:**\n"
            "1. Clique em \"Marcar HO\"\n"
            "2. Selecione seu nome\n"
            "3. Escolha se é tarefa de área ou projeto\n"
            "4. Selecione a área/projeto específico\n"
            "5. Informe data e horas\n"
            "6. Escolha modalidade (Presencial/EAD)\n"
            "7. Confirme os dados\n\n"
            "Dúvidas? Entre em contato com a coordenação! 🤝"
        )

        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ==================== MARCAR HO (fluxo) ====================

    async def _start_ho_flow(self, query, session):
        """Start the work hour registration flow"""
        session.clear()
        session['step'] = 'member_selection'

        text = "👤 **Selecione seu nome:**"
        keyboard = []
        for i in range(0, len(BotData.MEMBERS), 2):
            row = []
            row.append(InlineKeyboardButton(BotData.MEMBERS[i], callback_data=f"member_{i}"))
            if i + 1 < len(BotData.MEMBERS):
                row.append(InlineKeyboardButton(BotData.MEMBERS[i + 1], callback_data=f"member_{i+1}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_member_selection(self, query, session):
        index = int(query.data.split("_")[1])
        session['member'] = BotData.MEMBERS[index]
        session['step'] = 'task_type'
        text = (
            f"✅ **Membro:** {session['member']}\n\n"
            "Escolha o tipo de atividade:\n"
        )
        keyboard = [
            [
                InlineKeyboardButton("📁 Projeto", callback_data="task_type_project"),
                InlineKeyboardButton("🏢 Área", callback_data="task_type_area"),
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_task_type_selection(self, query, session):
        task_type = query.data.split("_")[2]  # project or area
        session['task_type'] = task_type
        session['step'] = f'{task_type}_selection'

        if task_type == "project":
            text = (
                f"✅ **Membro:** {session['member']}\n"
                "✅ **Tipo:** Projeto\n\n"
                "🎯 **Selecione o Projeto:**"
            )
            keyboard = [[InlineKeyboardButton(project, callback_data=f"project_{i}")]
                        for i, project in enumerate(BotData.PROJECTS)]
        else:
            text = (
                f"✅ **Membro:** {session['member']}\n"
                "✅ **Tipo:** Área\n\n"
                "🏢 **Selecione a Área:**"
            )
            keyboard = [[InlineKeyboardButton(area, callback_data=f"area_{i}")]
                        for i, area in enumerate(BotData.AREAS)]

        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_project_selection(self, query, session):
        project_index = int(query.data.split("_")[1])
        selected_project = BotData.PROJECTS[project_index]
        session['project_area'] = selected_project
        session['step'] = 'description_input'
        await self._ask_for_description(query, session)

    async def _handle_area_selection(self, query, session):
        area_index = int(query.data.split("_")[1])
        selected_area = BotData.AREAS[area_index]
        session['project_area'] = selected_area
        session['step'] = 'description_input'
        await self._ask_for_description(query, session)

    async def _ask_for_description(self, query, session):
        session['waiting_for'] = 'description'
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"

        text = (
            f"✅ **Membro:** {session['member']}\n"
            f"✅ **Tipo:** {task_type_display}\n"
            f"✅ **{task_type_display}:** {session['project_area']}\n\n"
            "📝 **Descrição da Atividade**\n\n"
            "Digite uma breve descrição do que foi realizado:\n"
            "- Ex.: \"Reunião de planejamento do projeto\"\n"
            "- Ex.: \"Desenvolvimento de material de marketing\""
        )
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_description_input(self, update: Update, session, text: str):
        session['description'] = text[:300]
        session['waiting_for'] = None
        await self._ask_for_date(update.message, session)

    async def _ask_for_date(self, target, session):
        session['waiting_for'] = 'date'
        today = date.today().strftime('%d/%m/%Y')
        text = (
            f"✅ **Membro:** {session['member']}\n"
            f"✅ **{('Projeto' if session['task_type']=='project' else 'Área')}:** {session['project_area']}\n"
            f"✅ **Descrição:** {session['description']}\n\n"
            f"📅 **Informe a data (DD/MM/AAAA)** — ex.: {today}"
        )
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        # target pode ser Message (texto) ou CallbackQuery.message
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_date_input(self, update: Update, session, text: str):
        # aceita 1/9/2025, 01/09/2025, etc.
        m = re.match(r'^\s*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\s*$', text)
        if not m:
            await update.message.reply_text("❗ Formato inválido. Use **DD/MM/AAAA**.", parse_mode='Markdown')
            return
        d, mth, y = map(int, m.groups())
        try:
            _ = date(y, mth, d)  # valida
        except ValueError:
            await update.message.reply_text("❗ Data inválida. Tente novamente no formato **DD/MM/AAAA**.", parse_mode='Markdown')
            return

        session['date'] = f"{d:02d}/{mth:02d}/{y:04d}"
        session['waiting_for'] = None
        await self._ask_for_hours(update.message, session)

    async def _ask_for_hours(self, message, session):
        session['waiting_for'] = 'hours'
        await message.reply_text(
            "⏱️ **Quantas horas?** (aceita decimal, ex.: 1.5)\n\n"
            "_Envie apenas o número._",
            parse_mode='Markdown'
        )

    async def _handle_hours_input(self, update: Update, session, text: str):
        text = text.replace(",", ".")
        try:
            hours = float(text)
            if hours <= 0 or hours > 24:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("❗ Informe um número de horas válido (ex.: 0.5, 1, 2.5).")
            return

        session['hours'] = hours
        session['waiting_for'] = None
        await self._ask_for_modality(update.message, session)

    async def _ask_for_modality(self, message, session):
        text = (
            f"✅ **Data:** {session['date']}\n"
            f"✅ **Horas:** {session['hours']}\n\n"
            "🎓 **Modalidade:**"
        )
        keyboard = [[InlineKeyboardButton(mod, callback_data=f"modality_{i}")]
                    for i, mod in enumerate(BotData.MODALITIES)]
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_modality_selection(self, query, session):
        mod_index = int(query.data.split("_")[1])
        session['modality'] = BotData.MODALITIES[mod_index]
        # tela de confirmação
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        text = (
            "✅ **Confirme os dados:**\n\n"
            f"- Membro: **{session['member']}**\n"
            f"- Tipo: **{task_type_display}**\n"
            f"- {task_type_display}: **{session['project_area']}**\n"
            f"- Data: **{session['date']}**\n"
            f"- Horas: **{session['hours']}**\n"
            f"- Modalidade: **{session['modality']}**\n"
            f"- Descrição: _{session['description']}_\n"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Confirmar", callback_data="confirm_ho")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _confirm_ho(self, query, session):
        user_id = query.from_user.id
        # cria WorkHour e gera HO ID
        ho_id = str(uuid.uuid4())[:8]
        work = WorkHour(
            member_name=session['member'],
            task_type="Projeto" if session['task_type'] == "project" else "Área",
            project_area=session['project_area'],
            date=session['date'],
            hours=float(session['hours']),
            modality=session['modality'],
            description=session['description'],
            status="Pendente",
            telegram_user_id=user_id,
            ho_id=ho_id,
        )
        storage.add_work_hour(work)

        # Sync imediato (se disponível)
        try:
            sheets_manager.sync_work_hour(work, user_id)
        except Exception as e:
            logger.warning(f"Falha ao sincronizar com Sheets: {e}")

        text = (
            "✅ **HO registrada!**\n\n"
            f"ID: `{ho_id}`\n"
            f"Membro: **{work.member_name}**\n"
            f"Tipo: **{work.task_type}** | {work.project_area}\n"
            f"Data: **{work.date}** | Horas: **{work.hours}** | Modalidade: **{work.modality}**\n\n"
            "Deseja marcar outra?"
        )
        keyboard = [
            [
                InlineKeyboardButton("➕ Mesmos dados (mudar só data/horas)", callback_data="mark_another_same")
            ],
            [InlineKeyboardButton("✨ Diferente", callback_data="mark_another_different")],
            [
                InlineKeyboardButton("📋 Pesquisa de clima", callback_data="finish_and_survey"),
                InlineKeyboardButton("🏁 Finalizar", callback_data="finish_no_survey"),
            ],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _mark_another_same(self, query, session):
        # mantém member/task_type/project_area/modality/description
        keep = {k: session[k] for k in ['member', 'task_type', 'project_area', 'modality', 'description']}
        session.clear()
        session.update(keep)
        await self._ask_for_date(query, session)

    async def _mark_another_different(self, query, session):
        await self._start_ho_flow(query, session)

    async def _finish_and_survey(self, query, session):
        keyboard = [
            [InlineKeyboardButton("📝 Abrir Pesquisa", url=BotData.CLIMATE_SURVEY_LINK)],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
        ]
        await query.edit_message_text("Obrigado! Você pode responder nossa pesquisa de clima:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _finish_no_survey(self, query, session):
        await self._show_main_menu(query)

    async def _cancel_process(self, query, session):
        session.clear()
        await query.edit_message_text("❌ Processo cancelado.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]))

    # ==================== GOOGLE SHEETS ====================

    async def _show_sheets_menu(self, query, session):
        text = "📈 **Google Sheets**\n\nO que deseja fazer?"
        keyboard = [
            [InlineKeyboardButton("🔗 Abrir Planilha", callback_data="view_sheets")],
            [InlineKeyboardButton("🔄 Sincronizar tudo", callback_data="sync_all_hours")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _view_sheets_url(self, query, session):
        url = sheets_manager.get_spreadsheet_url()
        if url:
            keyboard = [[InlineKeyboardButton("🔗 Abrir Planilha", url=url)],
                        [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
            await query.edit_message_text("Aqui está a planilha atual:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("⚠️ A integração com o Google Sheets não está configurada.")

    async def _sync_all_hours(self, query, session):
        count = 0
        try:
            count = sheets_manager.sync_multiple_work_hours(storage.work_hours, query.from_user.id)
        except Exception as e:
            logger.warning(f"Falha ao sincronizar em lote: {e}")
        await query.edit_message_text(f"✅ Sincronização concluída. Linhas enviadas: **{count}**.", parse_mode='Markdown')

    # ==================== LEMBRETES ====================

    async def _show_reminders_menu(self, query, session):
        user_id = query.from_user.id
        current = storage.get_user_reminder(user_id)
        if current:
            freq_text = {
                ReminderFrequency.DAILY: "Diário",
                ReminderFrequency.WEEKLY: "Semanal",
                ReminderFrequency.MONTHLY: "Mensal",
            }[current.frequency]
            status = "🟢 Ativo" if current.is_active else "🔴 Inativo"
            text = (
                "🔔 **Lembretes de HO**\n\n"
                f"**Status Atual:** {status}\n"
                f"**Membro:** {current.member_name}\n"
                f"**Frequência:** {freq_text}\n"
                f"**Horário:** {current.time_of_day.strftime('%H:%M')}\n\n"
                "O que deseja fazer?"
            )
            keyboard = [
                [InlineKeyboardButton("👁️ Ver Detalhes", callback_data="view_reminder")],
                [InlineKeyboardButton("⚙️ Configurar Novo", callback_data="setup_reminder")],
                [InlineKeyboardButton("❌ Desativar", callback_data="disable_reminder")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
            ]
        else:
            text = (
                "🔔 **Lembretes de HO**\n\n"
                "Você ainda não tem lembretes configurados.\n\n"
                "Configure um lembrete para não esquecer de marcar suas horas!"
            )
            keyboard = [
                [InlineKeyboardButton("⚙️ Configurar Lembrete", callback_data="setup_reminder")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
            ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _start_reminder_setup(self, query, session):
        session.clear()
        session['step'] = 'reminder_member_selection'
        text = "⚙️ **Configurar Lembrete**\n\nPrimeiro, selecione para qual membro:"
        keyboard = []
        for i in range(0, len(BotData.MEMBERS), 2):
            row = [InlineKeyboardButton(BotData.MEMBERS[i], callback_data=f"reminder_member_{i}")]
            if i + 1 < len(BotData.MEMBERS):
                row.append(InlineKeyboardButton(BotData.MEMBERS[i + 1], callback_data=f"reminder_member_{i+1}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("❌ Voltar", callback_data="reminders")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_reminder_member_selection(self, query, session):
        member_index = int(query.data.split("_")[2])
        session['reminder_member'] = BotData.MEMBERS[member_index]
        session['step'] = 'reminder_frequency'
        text = f"✅ Membro: **{session['reminder_member']}**\n\nEscolha a frequência:"
        keyboard = [
            [InlineKeyboardButton("Diário", callback_data="reminder_frequency_daily")],
            [InlineKeyboardButton("Semanal", callback_data="reminder_frequency_weekly")],
            [InlineKeyboardButton("Mensal", callback_data="reminder_frequency_monthly")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="reminders")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_reminder_frequency_selection(self, query, session):
        freq_key = query.data.split("_")[2]
        freq = {
            "daily": ReminderFrequency.DAILY,
            "weekly": ReminderFrequency.WEEKLY,
            "monthly": ReminderFrequency.MONTHLY,
        }[freq_key]
        session['reminder_frequency'] = freq
        session['waiting_for'] = 'reminder_time'
        await query.edit_message_text("🕒 Informe o horário (HH:MM), ex.: 18:00")

    async def _handle_reminder_time_input(self, update: Update, session, text: str):
        m = re.match(r'^\s*(\d{1,2}):(\d{2})\s*$', text)
        if not m:
            await update.message.reply_text("❗ Informe o horário no formato HH:MM (ex.: 18:00).")
            return
        hh, mm = map(int, m.groups())
        try:
            t = time(hour=hh, minute=mm)
        except ValueError:
            await update.message.reply_text("❗ Horário inválido. Tente novamente (HH:MM).")
            return

        session['reminder_time'] = t
        session['waiting_for'] = None

        member = session['reminder_member']
        freq = session['reminder_frequency']
        text = (
            "✅ **Confirme o lembrete:**\n\n"
            f"- Membro: **{member}**\n"
            f"- Frequência: **{('Diário' if freq==ReminderFrequency.DAILY else 'Semanal' if freq==ReminderFrequency.WEEKLY else 'Mensal')}**\n"
            f"- Horário: **{t.strftime('%H:%M')}**"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Salvar", callback_data="confirm_reminder")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="reminders")],
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _confirm_reminder_setup(self, query, session):
        user_id = query.from_user.id
        reminder = Reminder(
            user_id=user_id,
            member_name=session['reminder_member'],
            frequency=session['reminder_frequency'],
            time_of_day=session['reminder_time'],
            is_active=True,
            created_at=datetime.now(),
        )
        storage.add_reminder(reminder)
        await query.edit_message_text("✅ Lembrete salvo!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]))

    async def _view_current_reminder(self, query, session):
        user_id = query.from_user.id
        r = storage.get_user_reminder(user_id)
        if not r:
            await query.edit_message_text("Você não tem lembrete configurado.")
            return
        freq_text = {
            ReminderFrequency.DAILY: "Diário",
            ReminderFrequency.WEEKLY: "Semanal",
            ReminderFrequency.MONTHLY: "Mensal",
        }[r.frequency]
        text = (
            "🔔 **Seu lembrete**\n\n"
            f"• Membro: **{r.member_name}**\n"
            f"• Frequência: **{freq_text}**\n"
            f"• Horário: **{r.time_of_day.strftime('%H:%M')}**\n"
            f"• Ativo: **{'Sim' if r.is_active else 'Não'}**"
        )
        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _disable_reminder(self, query, session):
        user_id = query.from_user.id
        r = storage.get_user_reminder(user_id)
        if not r:
            await query.edit_message_text("Você não tem lembrete ativo.")
            return
        r.is_active = False
        await query.edit_message_text("🔕 Lembrete desativado.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]))

    # ==================== APROVAÇÃO - GERENTES ====================

    async def _show_manager_approval_menu(self, query):
        user_id = query.from_user.id
        manager = storage.get_manager_by_user_id(user_id)
        if not manager:
            await query.edit_message_text("🚫 Esta área é exclusiva para gerentes.")
            return

        # --- NOVO: resumo a partir da planilha ---
        try:
            summary_by_area = sheets_manager.get_pending_summary_by_area(manager.managed_areas)
            total_ho, total_pend = sheets_manager.get_totals()
        except Exception as e:
            logger.warning(f"Resumo via Sheets falhou, usando fallback em memória: {e}")
            # fallback se falhar
            from collections import Counter
            pending = [wh for wh in storage.work_hours if wh.status == "Pendente" and wh.project_area in manager.managed_areas]
            summary_by_area = Counter([wh.project_area for wh in pending])
            total_ho = len(storage.work_hours)
            total_pend = len(pending)

        if isinstance(summary_by_area, dict):
            lines = [f"• **{area}**: {count} pendente(s)" for area, count in summary_by_area.items()]
        else:
            # Counter → items()
            lines = [f"• **{area}**: {count} pendente(s)" for area, count in summary_by_area.items()]
        stats = "\n".join(lines) if lines else "Sem pendências nas suas áreas."

        text = (
            "🛡️ **Aprovação de HOs**\n\n"
            f"Áreas/Projetos: {', '.join(manager.managed_areas)}\n"
            f"{stats}\n\n"
            f"**Totais (planilha):** {total_ho} HOs | **Pendentes:** {total_pend}\n\n"
            "Escolha uma opção:"
        )
        keyboard = [
            [InlineKeyboardButton("🔍 Revisar HO's Pendentes", callback_data=f"start_approval_{user_id}")],
            [InlineKeyboardButton("📊 Ver Estatísticas", callback_data=f"approval_stats_{user_id}")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _start_approval_flow(self, query):
        user_id = query.from_user.id
        manager = storage.get_manager_by_user_id(user_id)
        if not manager:
            await query.edit_message_text("🚫 Acesso negado (somente gerentes).")
            return

        # Pega a instância correta do ApprovalSystem do bot_data
        approval = query._bot.application.bot_data.get('approval')
        if not approval:
            await query.edit_message_text("⚠️ Sistema de aprovação não inicializado. Verifique o bot.")
            return

        session = approval.start_approval_session(user_id, manager)
        if not session:
            await query.edit_message_text("✅ Não há HO pendente nas suas áreas. 🎉")
            return

        work = approval.get_current_approval_item(user_id)
        await self._render_approval_item(query, work)

    async def _render_approval_item(self, query, work: Optional[WorkHour]):
        if not work:
            # acabou a fila
            await self._finish_approval_flow(query)
            return

        text = (
            "🗂️ **Revisão de HO**\n\n"
            f"ID: `{work.ho_id}`\n"
            f"Membro: **{work.member_name}**\n"
            f"Tipo: **{work.task_type}** | {work.project_area}\n"
            f"Data: **{work.date}** | Horas: **{work.hours}** | Modalidade: **{work.modality}**\n"
            f"Descrição: _{work.description}_\n"
            f"Status atual: **{work.status}**"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Aprovar", callback_data=f"approve_{work.ho_id}"),
                InlineKeyboardButton("❌ Reprovar", callback_data=f"reject_{work.ho_id}"),
            ],
            [
                InlineKeyboardButton("⏭️ Próximo", callback_data="next_approval"),
                InlineKeyboardButton("🏁 Finalizar", callback_data="finish_approval"),
            ],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _handle_approval_decision(self, query, decision: str):
        user_id = query.from_user.id
        manager = storage.get_manager_by_user_id(user_id)
        if not manager:
            await query.edit_message_text("🚫 Acesso negado (somente gerentes).")
            return

        approval = query._bot.application.bot_data.get('approval')
        if not approval:
            await query.edit_message_text("⚠️ Sistema de aprovação não inicializado. Verifique o bot.")
            return

        ho_id = query.data.split("_", 1)[1]
        ok = approval.process_approval_decision(user_id, ho_id, decision, manager.name)
        if not ok:
            await query.edit_message_text("⚠️ Sessão de aprovação não encontrada. Volte ao menu e recomece.")
            return

        if approval.has_more_items(user_id):
            work = approval.get_current_approval_item(user_id)
            await self._render_approval_item(query, work)
        else:
            await self._finish_approval_flow(query)

    async def _show_next_approval_item(self, query):
        user_id = query.from_user.id
        approval = query._bot.application.bot_data.get('approval')
        if not approval:
            await query.edit_message_text("⚠️ Sistema de aprovação não inicializado. Verifique o bot.")
            return
        work = approval.get_current_approval_item(user_id)
        await self._render_approval_item(query, work)

    async def _finish_approval_flow(self, query):
        user_id = query.from_user.id
        approval = query._bot.application.bot_data.get('approval')
        if not approval:
            await query.edit_message_text("✅ Revisão encerrada.")
            return
        summary = approval.finish_approval_session(user_id)
        if not summary:
            await query.edit_message_text("✅ Revisão encerrada.")
            return

        text = (
            "✅ **Sessão encerrada**\n\n"
            f"Aprovados: **{summary['approved_count']}**\n"
            f"Reprovados: **{summary['rejected_count']}**\n"
            f"Total revisado: **{summary['total_reviewed']}**\n"
            f"Áreas/Projetos: {', '.join(summary['areas'])}"
        )
        kb = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    async def _show_approval_stats(self, query):
        user_id = query.from_user.id
        manager = storage.get_manager_by_user_id(user_id)
        if not manager:
            await query.edit_message_text("🚫 Acesso negado (somente gerentes).")
            return

        approval = query._bot.application.bot_data.get('approval')
        if not approval:
            await query.edit_message_text("⚠️ Sistema de aprovação não inicializado. Verifique o bot.")
            return

        stats = approval.get_approval_statistics(manager)
        text = (
            "📊 **Estatísticas de Aprovação**\n\n"
            f"Áreas/Projetos: {', '.join(stats['areas'])}\n"
            f"Total: **{stats['total']}** | Pendente: **{stats['pending']}** | "
            f"Aprovado: **{stats['approved']}** | Reprovado: **{stats['rejected']}**"
        )
        kb = [
            [InlineKeyboardButton("🔍 Revisar Pendentes", callback_data=f"start_approval_{user_id}")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')