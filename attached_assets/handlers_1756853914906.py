"""
Telegram bot handlers for EnactusBOT
"""

import logging
import re
from datetime import datetime, date, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_models import BotData, storage, WorkHour, Reminder, ReminderFrequency
from sheets_integration import sheets_manager

logger = logging.getLogger(__name__)

class BotHandlers:
    """Class containing all bot message and callback handlers"""
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_text = f"""
🌟 Olá {user.first_name}, bem-vindo ao EnactusBOT! 🌟

Sou seu assistente para gerenciamento de horas de trabalho da Enactus.

Use os botões abaixo para navegar:
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("📈 Google Sheets", callback_data="sheets_menu")],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
            [InlineKeyboardButton("❓ Ajuda", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📖 **Ajuda - EnactusBOT**

**Comandos disponíveis:**
• /start - Iniciar o bot e ver menu principal
• /help - Mostrar esta mensagem de ajuda
• /get_my_id - Descobrir seu ID do Telegram (para configurar gerentes)

**Funcionalidades:**
• **Marcar HO**: Registrar suas horas de trabalho
• **Central Enactus**: Acessar drive compartilhado

**Como marcar HO:**
1. Clique em "Marcar HO"
2. Selecione seu nome
3. Escolha se é tarefa de área ou projeto
4. Selecione a área/projeto específico
5. Informe data e horas
6. Escolha modalidade (Presencial/EAD)
7. Confirme os dados

Dúvidas? Entre em contato com a coordenação! 🤝
        """
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def get_my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /get_my_id command - useful for manager configuration"""
        user_id = update.message.from_user.id
        first_name = update.message.from_user.first_name or "Usuário"
        username = update.message.from_user.username
        
        text = f"""
🆔 **Seu ID do Telegram**

**Nome:** {first_name}
**Username:** @{username if username else "não definido"}
**ID:** `{user_id}`

📋 **Como usar:**
Para configurar gerentes, adicione esta linha no arquivo `data_models.py`:
```
({user_id}, "{first_name}", ["área1", "área2"]),
```

**Áreas disponíveis:** DAF, GP, MKT, QLD, PSD
**Projetos disponíveis:** Odoyá, Maná, Gelé
        """
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = storage.get_user_session(user_id)
        
        # Route to appropriate handler based on callback data
        if query.data == "main_menu":
            await self._show_main_menu(query)
        elif query.data == "mark_ho":
            await self._start_ho_flow(query, session)
        elif query.data == "help":
            await self._show_help(query)
        elif query.data == "sheets_menu":
            await self._show_sheets_menu(query, session)
        elif query.data == "sync_all_hours":
            await self._sync_all_hours(query, session)
        elif query.data == "view_sheets":
            await self._view_sheets_url(query, session)
        elif query.data == "reminders":
            await self._show_reminders_menu(query, session)
        elif query.data == "setup_reminder":
            await self._start_reminder_setup(query, session)
        elif query.data == "view_reminder":
            await self._view_current_reminder(query, session)
        elif query.data == "disable_reminder":
            await self._disable_reminder(query, session)
        elif query.data.startswith("reminder_member_"):
            await self._handle_reminder_member_selection(query, session)
        elif query.data.startswith("reminder_frequency_"):
            await self._handle_reminder_frequency_selection(query, session)
        elif query.data.startswith("member_"):
            await self._handle_member_selection(query, session)
        elif query.data.startswith("task_type_"):
            await self._handle_task_type_selection(query, session)
        elif query.data.startswith("project_"):
            await self._handle_project_selection(query, session)
        elif query.data.startswith("area_"):
            await self._handle_area_selection(query, session)
        elif query.data.startswith("modality_"):
            await self._handle_modality_selection(query, session)
        elif query.data == "confirm_ho":
            await self._confirm_ho(query, session)
        elif query.data == "confirm_reminder":
            await self._confirm_reminder_setup(query, session)
        elif query.data == "mark_another_same":
            await self._mark_another_same(query, session)
        elif query.data == "mark_another_different":
            await self._mark_another_different(query, session)
        elif query.data == "finish_and_survey":
            await self._finish_and_survey(query, session)
        elif query.data == "finish_no_survey":
            await self._finish_no_survey(query, session)
        elif query.data == "cancel":
            await self._cancel_process(query, session)
    
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
    
    async def _show_main_menu(self, query):
        """Show main menu"""
        text = """
🌟 **EnactusBOT - Menu Principal**

Escolha uma opção abaixo:
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
            [InlineKeyboardButton("❓ Ajuda", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_main_menu_message(self, update):
        """Show main menu as new message"""
        text = """
🌟 **EnactusBOT - Menu Principal**

Escolha uma opção abaixo:
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Marcar HO", callback_data="mark_ho")],
            [InlineKeyboardButton("📁 Central Enactus", url=BotData.CENTRAL_ENACTUS_LINK)],
            [InlineKeyboardButton("🔔 Lembretes", callback_data="reminders")],
            [InlineKeyboardButton("❓ Ajuda", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_help(self, query):
        """Show help information"""
        help_text = """
📖 **Ajuda - EnactusBOT**

**Funcionalidades:**
• **Marcar HO**: Registrar suas horas de trabalho
• **Central Enactus**: Acessar drive compartilhado

**Como marcar HO:**
1. Clique em "Marcar HO"
2. Selecione seu nome
3. Escolha se é tarefa de área ou projeto
4. Selecione a área/projeto específico
5. Informe data e horas
6. Escolha modalidade (Presencial/EAD)
7. Confirme os dados

Dúvidas? Entre em contato com a coordenação! 🤝
        """
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _start_ho_flow(self, query, session):
        """Start the work hour registration flow"""
        # Clear previous session data
        session.clear()
        session['step'] = 'member_selection'
        
        text = """
👥 **Seleção de Membro**

Selecione seu nome da lista abaixo:
        """
        
        # Create keyboard with members (2 per row)
        keyboard = []
        for i in range(0, len(BotData.MEMBERS), 2):
            row = []
            row.append(InlineKeyboardButton(
                BotData.MEMBERS[i], 
                callback_data=f"member_{i}"
            ))
            if i + 1 < len(BotData.MEMBERS):
                row.append(InlineKeyboardButton(
                    BotData.MEMBERS[i + 1], 
                    callback_data=f"member_{i + 1}"
                ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_member_selection(self, query, session):
        """Handle member selection"""
        member_index = int(query.data.split("_")[1])
        selected_member = BotData.MEMBERS[member_index]
        session['member'] = selected_member
        session['step'] = 'task_type_selection'
        
        text = f"""
✅ **Membro selecionado:** {selected_member}

📋 **Tipo de Tarefa**

A tarefa foi de área ou projeto?
        """
        
        keyboard = [
            [InlineKeyboardButton("🎯 Projeto", callback_data="task_type_project")],
            [InlineKeyboardButton("🏢 Área", callback_data="task_type_area")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_task_type_selection(self, query, session):
        """Handle task type selection (project or area)"""
        task_type = query.data.split("_")[2]  # project or area
        session['task_type'] = task_type
        session['step'] = f'{task_type}_selection'
        
        if task_type == "project":
            text = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** Projeto

🎯 **Selecione o Projeto:**
            """
            
            keyboard = []
            for i, project in enumerate(BotData.PROJECTS):
                keyboard.append([InlineKeyboardButton(
                    project, 
                    callback_data=f"project_{i}"
                )])
        else:  # area
            text = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** Área

🏢 **Selecione a Área:**
            """
            
            keyboard = []
            for i, area in enumerate(BotData.AREAS):
                keyboard.append([InlineKeyboardButton(
                    area, 
                    callback_data=f"area_{i}"
                )])
        
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_project_selection(self, query, session):
        """Handle project selection"""
        project_index = int(query.data.split("_")[1])
        selected_project = BotData.PROJECTS[project_index]
        session['project_area'] = selected_project
        session['step'] = 'description_input'
        
        await self._ask_for_description(query, session)
    
    async def _handle_area_selection(self, query, session):
        """Handle area selection"""
        area_index = int(query.data.split("_")[1])
        selected_area = BotData.AREAS[area_index]
        session['project_area'] = selected_area
        session['step'] = 'description_input'
        
        await self._ask_for_description(query, session)
    
    async def _ask_for_description(self, query, session):
        """Ask user for activity description"""
        session['waiting_for'] = 'description'
        
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        text = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}

📝 **Descrição da Atividade**

Digite uma breve descrição do que foi realizado:
- Exemplo: "Reunião de planejamento do projeto"
- Exemplo: "Desenvolvimento de material de marketing"
- Exemplo: "Treinamento de capacitação"

**Seja específico mas conciso:**
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _ask_for_date(self, query, session):
        """Ask user for date input"""
        session['waiting_for'] = 'date'
        today = date.today().strftime("%d/%m/%Y")
        
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        text = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}

📅 **Data da Atividade**

Digite a data no formato DD/MM/AAAA
Exemplo: {today}

Para hoje, digite apenas: hoje
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_description_input(self, update, session, text):
        """Handle description input from user"""
        # Validate description length
        if len(text.strip()) < 5:
            await update.message.reply_text(
                "❌ **Descrição muito curta!**\n\n"
                "A descrição deve ter pelo menos 5 caracteres. Seja mais específico sobre a atividade realizada.",
                parse_mode='Markdown'
            )
            return
        
        if len(text.strip()) > 200:
            await update.message.reply_text(
                "❌ **Descrição muito longa!**\n\n"
                "A descrição deve ter no máximo 200 caracteres. Seja mais conciso.",
                parse_mode='Markdown'
            )
            return
        
        # Save description and move to next step
        session['description'] = text.strip()
        session['step'] = 'date_input'
        
        await self._ask_for_date_from_message(update, session)
    
    async def _ask_for_date_from_message(self, update, session):
        """Ask user for date input from a text message"""
        session['waiting_for'] = 'date'
        today = date.today().strftime("%d/%m/%Y")
        
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        text = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}

📅 **Data da Atividade**

Digite a data no formato DD/MM/AAAA
Exemplo: {today}

Para hoje, digite apenas: hoje
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_date_input(self, update, session, text):
        """Handle date input from user"""
        try:
            if text.lower() == "hoje":
                session['date'] = date.today().strftime("%d/%m/%Y")
            else:
                # Validate date format
                if not re.match(r'^\d{2}/\d{2}/\d{4}$', text):
                    raise ValueError("Formato inválido")
                
                # Try to parse date
                datetime.strptime(text, "%d/%m/%Y")
                session['date'] = text
            
            session['step'] = 'hours_input'
            session['waiting_for'] = 'hours'
            
            task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
            
            text_response = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}

⏱️ **Quantas Horas?**

Digite o número de horas trabalhadas (use ponto para decimais)
Exemplos: 2, 1.5, 0.5, 3.25
            """
            
            keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Data inválida!**\n\n"
                "Use o formato DD/MM/AAAA (ex: 21/08/2025) ou digite 'hoje' para a data atual.",
                parse_mode='Markdown'
            )
    
    async def _handle_hours_input(self, update, session, text):
        """Handle hours input from user"""
        try:
            # Replace comma with dot for decimal separation
            text = text.replace(',', '.')
            hours = float(text)
            
            if hours <= 0 or hours > 24:
                raise ValueError("Valor inválido")
            
            session['hours'] = hours
            session['step'] = 'modality_selection'
            session['waiting_for'] = None
            
            task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
            
            text_response = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {hours}h

🌐 **Modalidade**

A atividade foi presencial ou EAD?
            """
            
            keyboard = []
            for i, modality in enumerate(BotData.MODALITIES):
                keyboard.append([InlineKeyboardButton(
                    modality, 
                    callback_data=f"modality_{i}"
                )])
            
            keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Número de horas inválido!**\n\n"
                "Digite um número válido entre 0.1 e 24 horas.\n"
                "Exemplos: 2, 1.5, 0.5, 3.25",
                parse_mode='Markdown'
            )
    
    async def _handle_modality_selection(self, query, session):
        """Handle modality selection"""
        modality_index = int(query.data.split("_")[1])
        selected_modality = BotData.MODALITIES[modality_index]
        session['modality'] = selected_modality
        session['step'] = 'confirmation'
        
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        text = f"""
📋 **Confirmação dos Dados**

✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {session['hours']}h
✅ **Modalidade:** {selected_modality}

Confirma o registro desta HO?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_ho"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _confirm_ho(self, query, session):
        """Confirm and save work hour"""
        import uuid
        
        # Create work hour record
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        work_hour = WorkHour(
            member_name=session['member'],
            task_type=f"{task_type_display} - {session['project_area']}",
            project_area=session['project_area'],
            date=session['date'],
            hours=session['hours'],
            modality=session['modality'],
            description=session['description'],
            status="Pendente",
            telegram_user_id=query.from_user.id,
            ho_id=str(uuid.uuid4())
        )
        
        storage.add_work_hour(work_hour)
        
        # Attempt to sync to Google Sheets
        sync_status = ""
        if sheets_manager.is_available():
            user_id = query.from_user.id
            if sheets_manager.sync_work_hour(work_hour, user_id):
                sync_status = "\n📊 **Sincronizado com Google Sheets!**"
            else:
                sync_status = "\n⚠️ **Erro ao sincronizar com Google Sheets**"
        else:
            sync_status = "\n📋 **Google Sheets não configurado**"
        
        text = f"""
🎉 **HO Registrada com Sucesso!**

✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {session['hours']}h
✅ **Modalidade:** {session['modality']}
⏳ **Status:** Pendente de aprovação{sync_status}

O que deseja fazer agora?
        """
        
        keyboard = []
        
        # Same area/project option
        if session['task_type'] == "project":
            same_text = f"📊 Marcar outra HO do projeto {session['project_area']}"
        else:
            same_text = f"📊 Marcar outra HO da área {session['project_area']}"
        
        keyboard.append([InlineKeyboardButton(same_text, callback_data="mark_another_same")])
        keyboard.append([InlineKeyboardButton("🔄 Marcar HO de outra área/projeto", callback_data="mark_another_different")])
        keyboard.append([InlineKeyboardButton("✅ Finalizar (com pesquisa de clima)", callback_data="finish_and_survey")])
        keyboard.append([InlineKeyboardButton("✅ Finalizar (sem pesquisa)", callback_data="finish_no_survey")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _mark_another_same(self, query, session):
        """Mark another HO for the same area/project"""
        # Keep member, task_type, and project_area, but reset the rest
        member = session['member']
        task_type = session['task_type']
        project_area = session['project_area']
        
        session.clear()
        session['member'] = member
        session['task_type'] = task_type
        session['project_area'] = project_area
        session['step'] = 'description_input'
        
        await self._ask_for_description(query, session)
    
    async def _mark_another_different(self, query, session):
        """Mark another HO for different area/project"""
        # Keep only member
        member = session['member']
        session.clear()
        session['member'] = member
        session['step'] = 'task_type_selection'
        
        text = f"""
✅ **Membro selecionado:** {member}

📋 **Tipo de Tarefa**

A tarefa foi de área ou projeto?
        """
        
        keyboard = [
            [InlineKeyboardButton("🎯 Projeto", callback_data="task_type_project")],
            [InlineKeyboardButton("🏢 Área", callback_data="task_type_area")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _finish_and_survey(self, query, session):
        """Finish with climate survey"""
        storage.clear_user_session(query.from_user.id)
        
        text = f"""
🎉 **Processo Finalizado!**

Obrigado por registrar suas horas! 

🌡️ Gostaria de participar da nossa pesquisa de clima organizacional?
        """
        
        keyboard = [
            [InlineKeyboardButton("🌡️ Fazer Pesquisa de Clima", url=BotData.CLIMATE_SURVEY_LINK)],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _finish_no_survey(self, query, session):
        """Finish without survey"""
        storage.clear_user_session(query.from_user.id)
        
        text = f"""
🎉 **Processo Finalizado!**

Obrigado por registrar suas horas! 

Até a próxima! 🤝
        """
        
        keyboard = [
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _cancel_process(self, query, session):
        """Cancel current process"""
        storage.clear_user_session(query.from_user.id)
        
        text = """
❌ **Processo Cancelado**

Operação cancelada. Você pode iniciar novamente quando quiser.
        """
        
        keyboard = [
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # ==================== REMINDER FUNCTIONALITY ====================
    
    async def _show_reminders_menu(self, query, session):
        """Show reminders management menu"""
        user_id = query.from_user.id
        current_reminder = storage.get_user_reminder(user_id)
        
        if current_reminder:
            frequency_text = {
                ReminderFrequency.DAILY: "Diário",
                ReminderFrequency.WEEKLY: "Semanal", 
                ReminderFrequency.MONTHLY: "Mensal"
            }[current_reminder.frequency]
            
            status_text = "🟢 Ativo" if current_reminder.is_active else "🔴 Inativo"
            
            text = f"""
🔔 **Lembretes de HO**

**Status Atual:** {status_text}
**Membro:** {current_reminder.member_name}
**Frequência:** {frequency_text}
**Horário:** {current_reminder.time_of_day.strftime('%H:%M')}

O que deseja fazer?
            """
            
            keyboard = [
                [InlineKeyboardButton("👁️ Ver Detalhes", callback_data="view_reminder")],
                [InlineKeyboardButton("⚙️ Configurar Novo", callback_data="setup_reminder")],
                [InlineKeyboardButton("❌ Desativar", callback_data="disable_reminder")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
            ]
        else:
            text = """
🔔 **Lembretes de HO**

Você ainda não tem lembretes configurados.

Configure um lembrete para não esquecer de marcar suas horas de trabalho!
            """
            
            keyboard = [
                [InlineKeyboardButton("⚙️ Configurar Lembrete", callback_data="setup_reminder")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _start_reminder_setup(self, query, session):
        """Start reminder setup flow"""
        session.clear()
        session['step'] = 'reminder_member_selection'
        
        text = """
⚙️ **Configurar Lembrete**

Primeiro, selecione para qual membro configurar o lembrete:
        """
        
        # Create keyboard with members (2 per row)
        keyboard = []
        for i in range(0, len(BotData.MEMBERS), 2):
            row = []
            row.append(InlineKeyboardButton(
                BotData.MEMBERS[i], 
                callback_data=f"reminder_member_{i}"
            ))
            if i + 1 < len(BotData.MEMBERS):
                row.append(InlineKeyboardButton(
                    BotData.MEMBERS[i + 1], 
                    callback_data=f"reminder_member_{i + 1}"
                ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="reminders")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_reminder_member_selection(self, query, session):
        """Handle reminder member selection"""
        member_index = int(query.data.split("_")[2])
        selected_member = BotData.MEMBERS[member_index]
        session['reminder_member'] = selected_member
        session['step'] = 'reminder_frequency_selection'
        
        text = f"""
✅ **Membro selecionado:** {selected_member}

📅 **Frequência do Lembrete**

Com que frequência deseja receber lembretes?
        """
        
        keyboard = [
            [InlineKeyboardButton("📅 Diário", callback_data="reminder_frequency_daily")],
            [InlineKeyboardButton("📆 Semanal", callback_data="reminder_frequency_weekly")],
            [InlineKeyboardButton("🗓️ Mensal", callback_data="reminder_frequency_monthly")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="reminders")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_reminder_frequency_selection(self, query, session):
        """Handle reminder frequency selection"""
        frequency_str = query.data.split("_")[2]
        frequency_map = {
            "daily": ReminderFrequency.DAILY,
            "weekly": ReminderFrequency.WEEKLY,
            "monthly": ReminderFrequency.MONTHLY
        }
        
        frequency_text_map = {
            "daily": "Diário",
            "weekly": "Semanal",
            "monthly": "Mensal"
        }
        
        session['reminder_frequency'] = frequency_map[frequency_str]
        session['reminder_frequency_text'] = frequency_text_map[frequency_str]
        session['step'] = 'reminder_time_input'
        session['waiting_for'] = 'reminder_time'
        
        text = f"""
✅ **Membro:** {session['reminder_member']}
✅ **Frequência:** {session['reminder_frequency_text']}

🕐 **Horário do Lembrete**

Digite o horário em que deseja receber os lembretes no formato HH:MM (24h)

Exemplos: 09:00, 18:30, 20:00
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="reminders")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_reminder_time_input(self, update, session, text):
        """Handle reminder time input"""
        try:
            # Validate time format HH:MM
            if not re.match(r'^\d{2}:\d{2}$', text):
                raise ValueError("Formato inválido")
            
            hour, minute = map(int, text.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Horário inválido")
            
            session['reminder_time'] = time(hour, minute)
            session['step'] = 'reminder_confirmation'
            session['waiting_for'] = None
            
            text_response = f"""
📋 **Confirmação do Lembrete**

✅ **Membro:** {session['reminder_member']}
✅ **Frequência:** {session['reminder_frequency_text']}
✅ **Horário:** {session['reminder_time'].strftime('%H:%M')}

Confirma a configuração deste lembrete?
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data="confirm_reminder"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="reminders")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Horário inválido!**\n\n"
                "Use o formato HH:MM (24h)\n"
                "Exemplos: 09:00, 18:30, 20:00",
                parse_mode='Markdown'
            )
    
    async def _confirm_reminder_setup(self, query, session):
        """Confirm and save reminder setup"""
        user_id = query.from_user.id
        
        # Create reminder
        reminder = Reminder(
            user_id=user_id,
            member_name=session['reminder_member'],
            frequency=session['reminder_frequency'],
            time_of_day=session['reminder_time'],
            is_active=True,
            created_at=datetime.now()
        )
        
        storage.add_reminder(reminder)
        
        text = f"""
🎉 **Lembrete Configurado com Sucesso!**

✅ **Membro:** {session['reminder_member']}
✅ **Frequência:** {session['reminder_frequency_text']}
✅ **Horário:** {session['reminder_time'].strftime('%H:%M')}

Você receberá lembretes para marcar suas HO de acordo com a configuração escolhida.

Para gerenciar seus lembretes, use o menu "🔔 Lembretes".
        """
        
        keyboard = [
            [InlineKeyboardButton("🔔 Ver Lembretes", callback_data="reminders")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Clear session
        session.clear()
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _view_current_reminder(self, query, session):
        """View current reminder details"""
        user_id = query.from_user.id
        reminder = storage.get_user_reminder(user_id)
        
        if not reminder:
            text = "❌ Nenhum lembrete encontrado."
        else:
            frequency_text = {
                ReminderFrequency.DAILY: "Diário",
                ReminderFrequency.WEEKLY: "Semanal", 
                ReminderFrequency.MONTHLY: "Mensal"
            }[reminder.frequency]
            
            status_text = "🟢 Ativo" if reminder.is_active else "🔴 Inativo"
            last_sent_text = reminder.last_sent.strftime('%d/%m/%Y às %H:%M') if reminder.last_sent else "Nunca enviado"
            
            text = f"""
👁️ **Detalhes do Lembrete**

**Status:** {status_text}
**Membro:** {reminder.member_name}
**Frequência:** {frequency_text}
**Horário:** {reminder.time_of_day.strftime('%H:%M')}
**Criado em:** {reminder.created_at.strftime('%d/%m/%Y às %H:%M')}
**Último envio:** {last_sent_text}
            """
        
        keyboard = [
            [InlineKeyboardButton("🔔 Voltar", callback_data="reminders")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _disable_reminder(self, query, session):
        """Disable user's reminder"""
        user_id = query.from_user.id
        storage.remove_user_reminder(user_id)
        
        text = """
❌ **Lembrete Desativado**

Seu lembrete foi desativado com sucesso. Você não receberá mais notificações automáticas.

Você pode configurar um novo lembrete quando quiser.
        """
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Configurar Novo", callback_data="setup_reminder")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # ==================== GOOGLE SHEETS FUNCTIONALITY ====================
    
    async def _show_sheets_menu(self, query, session):
        """Show Google Sheets integration menu"""
        # Check if sheets integration is available
        if not sheets_manager.is_available():
            text = """
📋 **Google Sheets - Não Configurado**

A integração com Google Sheets não está configurada.

Para habilitar esta funcionalidade, é necessário:
• Credenciais de Service Account do Google
• ID da planilha do Enactus

Entre em contato com o administrador do sistema.
            """
            
            keyboard = [
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
            ]
        else:
            # Get some stats
            total_hours = len(storage.work_hours)
            spreadsheet_url = sheets_manager.get_spreadsheet_url()
            
            text = f"""
📊 **Google Sheets - Integração Ativa**

**Status:** 🟢 Conectado
**Total de HO registradas:** {total_hours}
**Sincronização:** Automática a cada registro

O que deseja fazer?
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 Ver Planilha", callback_data="view_sheets")],
                [InlineKeyboardButton("🔄 Sincronizar Todas HO", callback_data="sync_all_hours")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _view_sheets_url(self, query, session):
        """Show Google Sheets URL"""
        if not sheets_manager.is_available():
            text = "❌ Google Sheets não está configurado."
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="sheets_menu")]]
        else:
            spreadsheet_url = sheets_manager.get_spreadsheet_url()
            text = f"""
📊 **Planilha do Enactus**

Acesse a planilha através do link abaixo:

{spreadsheet_url}

A planilha contém todos os registros de HO sincronizados automaticamente.
            """
            
            keyboard = [
                [InlineKeyboardButton("🔗 Abrir Planilha", url=spreadsheet_url)],
                [InlineKeyboardButton("🔙 Voltar", callback_data="sheets_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _sync_all_hours(self, query, session):
        """Sync all work hours to Google Sheets"""
        if not sheets_manager.is_available():
            text = "❌ Google Sheets não está configurado."
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="sheets_menu")]]
        else:
            user_id = query.from_user.id
            work_hours = storage.work_hours
            
            if not work_hours:
                text = "📋 Nenhuma HO encontrada para sincronizar."
            else:
                # Show progress message
                await query.edit_message_text(
                    f"🔄 Sincronizando {len(work_hours)} registros de HO...",
                    parse_mode='Markdown'
                )
                
                # Perform sync
                synced_count = sheets_manager.sync_multiple_work_hours(work_hours, user_id)
                
                if synced_count > 0:
                    text = f"""
🎉 **Sincronização Concluída!**

✅ **{synced_count} registros** sincronizados com sucesso
📊 **Planilha atualizada** com todos os dados

Todos os registros de HO estão agora disponíveis na planilha.
                    """
                else:
                    text = f"""
❌ **Erro na Sincronização**

Não foi possível sincronizar os registros.
Verifique a conexão e tente novamente.

**Total de registros:** {len(work_hours)}
                    """
            
            keyboard = [
                [InlineKeyboardButton("📊 Ver Planilha", callback_data="view_sheets")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="sheets_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')