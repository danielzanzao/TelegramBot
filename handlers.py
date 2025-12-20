"""
Telegram bot handlers for EnactusBOT
"""

import logging
import re
from datetime import datetime, date, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from data_models import BotData, storage, WorkHour, Reminder, ReminderFrequency, ReminderType
from sheets_integration import sheets_manager

logger = logging.getLogger(__name__)

class BotHandlers:
    """Class containing all bot message and callback handlers"""
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        roles = BotData.get_user_role(user.id)
        scopes = BotData.get_managed_scopes(user.id)
        
        # Mapping acronyms to full names
        area_map = {
            "QLD": "Qualidade",
            "GP": "Gestão de Pessoas",
            "DAF": "Adm. Financeiro",
            "MKT": "Marketing",
            "PSD": "PSD"
        }
        
        role_lines = []
        consumed_scopes = set()
        has_leadership = len(scopes) > 0
        
        # Separate roles
        director_roles = []
        member_roles = []
        
        if roles:
            for r in roles:
                if r in scopes:
                    director_roles.append(r)
                    consumed_scopes.add(r)
                else:
                    member_roles.append(r)
        
        # Add Director lines
        for r in director_roles:
            full_name = area_map.get(r, r)
            role_lines.append(f"👤 Cargo: Diretor(a) de {full_name}")
            
        # Add Member lines (aggregated) - Only if NO leadership
        if member_roles and not has_leadership:
             terms = []
             for r in member_roles:
                 name = area_map.get(r, r)
                 if r in ["Odoyá", "Maná", "Gelé"]:
                     terms.append(f"do {name}")
                 else:
                     terms.append(name)
             
             if len(terms) > 1:
                 last = terms.pop()
                 joined = ", ".join(terms) + " e " + last
             else:
                 joined = terms[0]
             
             final_str = f"Membro de {joined}"
             final_str = final_str.replace("de do ", "do ")
             role_lines.append(f"👤 Cargo: {final_str}")
            
        if scopes:
            # Only show scopes that weren't used to define Directorship
            remaining_scopes = [s for s in scopes if s not in consumed_scopes]
            if remaining_scopes:
                formatted_scopes = []
                for s in remaining_scopes:
                    prefix = "Gerente do" if s in ["Odoyá", "Maná", "Gelé"] else "Gerente de"
                    formatted_scopes.append(f"{prefix} {s}")
                role_lines.append(f"💼 Função: {', '.join(formatted_scopes)}")
            
        role_text = "\n" + "\n".join(role_lines) if role_lines else ""
            
        welcome_text = f"""
🌟 Olá {user.first_name}, Bem vinde ao EnactusBOT 🌟{role_text}

Selecione uma das opções abaixo para começar:
        """
        
        # Check permissions
        is_gp = BotData.is_user_in_role(user.id, "GP")
        managed_scopes = BotData.get_managed_scopes(user.id)
        is_manager = len(managed_scopes) > 0
        
        keyboard = [
            [KeyboardButton("📊 Marcar HO"), KeyboardButton("📁 Central Enactus")],
        ]
        
        if is_manager:
             keyboard.append([KeyboardButton("✅ Validar HOs")])

        if is_gp:
            keyboard.append([KeyboardButton("📈 Google Sheets"), KeyboardButton("🔔 Lembretes")])
            keyboard.append([KeyboardButton("❓ Ajuda")])
        else:
             keyboard.append([KeyboardButton("🔔 Lembretes"), KeyboardButton("❓ Ajuda")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
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
        
        # We handle get_my_id command differently, likely no persistent menu needed as it's a util command
        # But we can add a return button
        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def refresh_db_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force refresh of database (Members and Reminders) from Cloud"""
        # Security check: only allow managers or specific users? 
        # For now, open to all or check if user is manager.
        user_id = update.effective_user.id
        
        await update.message.reply_text("🔄 Atualizando banco de dados na nuvem...")
        
        try:
            from sheets_integration import sheets_manager
            from data_models import BotData, storage
            
            # 1. Reload Members
            members = sheets_manager.load_members()
            if members:
                BotData.set_members(members)
                
            # 2. Reload Reminders
            reminders = sheets_manager.load_reminders()
            if reminders:
                storage.reminders = reminders
            
            await update.message.reply_text(
                f"✅ **Banco de Dados Atualizado!**\n"
                f"👥 Membros: {len(members) if members else 0}\n"
                f"🔔 Lembretes: {len(reminders) if reminders else 0}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao atualizar: {str(e)}")
    
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
        elif query.data.startswith("toggle_pch_"):
            await self._handle_pch_toggle(query, session)
        elif query.data == "setup_ho_start":
            await self._start_ho_reminder_setup(query, session)
        elif query.data == "disable_ho":
            await self._disable_ho_reminder(query, session)
        elif query.data.startswith("validate_"):
            action = query.data.replace("validate_", "")
            await self._handle_validation_action(query, session, action)
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input from users"""
        user_id = update.effective_user.id
        session = storage.get_user_session(user_id)
        text = update.message.text.strip()
        
        # Check for main menu commands
        if text == "📊 Marcar HO":
            await self._start_ho_flow(update.message, session)
            return
        elif text == "📁 Central Enactus":
            await update.message.reply_text(f"📁 Central Enactus\n\nAcesse o drive compartilhado aqui:\n{BotData.CENTRAL_ENACTUS_LINK}")
            return
        elif text == "📈 Google Sheets":
            await self._show_sheets_menu(update.message, session)
            return
        elif text == "✅ Validar HOs":
            await self._handle_validation_flow(update.message, session)
            return
        elif text == "🔔 Lembretes":
            await self._show_reminders_menu(update.message, session)
            return
            
        # Reminder Menu Actions
        elif text == "📅 Ativar PCH" or text == "📅 Desativar PCH":
            await self._handle_pch_toggle_text(update, session, text)
            return
        elif text == "📝 Configurar HO" or text == "📝 Reconfigurar HO":
            await self._start_ho_reminder_setup(update.message, session)
            return
        elif text == "❌ Desativar Lembrete HO":
            await self._disable_ho_reminder_text(update, session)
            return
            
        elif text == "❓ Ajuda":
            await self._show_help(update.message)
            return

        if 'waiting_for' not in session:
            # No active session, show main menu message (restore keyboard if missing)
            await self._show_main_menu_message(update)
            return
        
        waiting_for = session['waiting_for']
        
        if waiting_for == 'description':
            await self._handle_description_input(update, session, text)
        elif waiting_for == 'date':
            await self._handle_date_input(update, session, text)
        elif waiting_for == 'hours':
            await self._handle_hours_input(update, session, text)
        elif waiting_for == 'member':
             await self._handle_member_selection_text(update, session, text)
        elif waiting_for == 'task_type':
             await self._handle_task_type_text(update, session, text)
        elif waiting_for == 'project_selection':
             await self._handle_project_area_text(update, session, text, is_project=True)
        elif waiting_for == 'area_selection':
             await self._handle_project_area_text(update, session, text, is_project=False)
        elif waiting_for == 'modality':
             await self._handle_modality_text(update, session, text)
        elif waiting_for == 'confirmation':
             await self._handle_confirmation_text(update, session, text)
        elif waiting_for == 'post_completion':
             await self._handle_post_completion_text(update, session, text)
        elif waiting_for == 'reminder_time':
            await self._handle_reminder_time_input(update, session, text)
        elif waiting_for == 'reminder_member_text':
            await self._handle_reminder_member_text(update, session, text)
        elif waiting_for == 'reminder_frequency_text':
            await self._handle_reminder_frequency_text(update, session, text)
        elif waiting_for == 'reminder_day_text':
            await self._handle_reminder_day_text(update, session, text)
            
    async def _respond(self, source, text, reply_markup=None, parse_mode='Markdown'):
        """Helper to respond to either a Message or CallbackQuery"""
        from telegram import Message, CallbackQuery
        
        if isinstance(source, Message):
            await source.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif isinstance(source, CallbackQuery):
            if isinstance(reply_markup, ReplyKeyboardMarkup):
                # Cannot edit message with ReplyKeyboard, must send new
                await source.delete_message()
                await source.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                await source.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            # Fallback if source is something else, though it shouldn't be
            logger.error(f"Unknown source type in _respond: {type(source)}")

    async def _show_main_menu_compat(self, source):
        """Helper to show main menu from various validation sources"""
        try:
            if hasattr(source, 'from_user'):
                user = source.from_user
            elif hasattr(source, 'effective_user'):
                user = source.effective_user
            else:
                logger.error(f"Could not find user in source: {type(source)}")
                return
                
            # Call the logic directly
            await self._show_menu_for_user(source, user)
        except Exception as e:
            logger.error(f"Error showing main menu: {e}", exc_info=True)


    async def _show_menu_for_user(self, reply_to, user):
        """Show main menu for specific user"""
        try:
            user_id = user.id
            roles = BotData.get_user_role(user_id)
            scopes = BotData.get_managed_scopes(user_id)
            
            # Mapping acronyms to full names
            area_map = {
                "QLD": "Qualidade",
                "GP": "Gestão de Pessoas",
                "DAF": "Adm. Financeiro",
                "MKT": "Marketing",
                "PSD": "Presidência"
            }
            
            role_lines = []
            consumed_scopes = set()
            has_leadership = len(scopes) > 0
            
            # Separate roles
            director_roles = []
            member_roles = []
            
            if roles:
                for r in roles:
                    if r in scopes:
                        director_roles.append(r)
                        consumed_scopes.add(r)
                    else:
                        member_roles.append(r)
            
            # Add Director lines
            for r in director_roles:
                full_name = area_map.get(r, r)
                role_lines.append(f"👤 Cargo: Diretor(a) de {full_name}")
                
            # Add Member lines (aggregated) - Only if NO leadership
            if member_roles and not has_leadership:
                 terms = []
                 for r in member_roles:
                     name = area_map.get(r, r)
                     if r in ["Odoyá", "Maná", "Gelé"]:
                         terms.append(f"do {name}")
                     else:
                         terms.append(name)
                 
                 if len(terms) > 1:
                     last = terms.pop()
                     joined = ", ".join(terms) + " e " + last
                 else:
                     joined = terms[0]
                 
                 final_str = f"Membro de {joined}"
                 final_str = final_str.replace("de do ", "do ")
                 role_lines.append(f"👤 Cargo: {final_str}")
                
            if scopes:
                # Only show scopes that weren't used to define Directorship
                remaining_scopes = [s for s in scopes if s not in consumed_scopes]
                if remaining_scopes:
                    formatted_scopes = []
                    for s in remaining_scopes:
                        prefix = "Gerente do" if s in ["Odoyá", "Maná", "Gelé"] else "Gerente de"
                        formatted_scopes.append(f"{prefix} {s}")
                    role_lines.append(f"💼 Função: {', '.join(formatted_scopes)}")
                
            role_text = "\n" + "\n".join(role_lines) if role_lines else ""
                
            text = f"""
    🌟 Olá {user.first_name}, o que você quer fazer?{role_text}
            """
            is_gp = BotData.is_user_in_role(user_id, "GP")
            managed_scopes = BotData.get_managed_scopes(user_id)
            is_manager = len(managed_scopes) > 0
            
            keyboard = [
                [KeyboardButton("📊 Marcar HO"), KeyboardButton("📁 Central Enactus")],
            ]
            
            if is_manager:
                 keyboard.append([KeyboardButton("✅ Validar HOs")])

            if is_gp:
                 keyboard.append([KeyboardButton("📈 Google Sheets"), KeyboardButton("🔔 Lembretes")])
                 keyboard.append([KeyboardButton("❓ Ajuda")])
            else:
                 keyboard.append([KeyboardButton("🔔 Lembretes"), KeyboardButton("❓ Ajuda")])
                
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await self._respond(reply_to, text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in _show_menu_for_user for user {user.id}: {e}", exc_info=True)

    async def _show_main_menu(self, query):
        """Show main menu - Edits message to point to persistent menu"""
        text = """
🌟 **EnactusBOT**

Utilize o menu abaixo para navegar 👇
        """
        # We don't attach the ReplyKeyboard here as we are editing an inline message.
        # ReplyKeyboards can only be sent with new messages.
        # We assume the user already has the keyboard.
        # If we wanted to ensure it, we would have to delete this message and send a new one.
        # For now, just editing to clear the inline clutter is good.
        
        await query.edit_message_text(text, parse_mode='Markdown')

    async def _show_main_menu_message(self, update):
        """Show main menu as new message (restores keyboard)"""
        user_id = update.effective_user.id
        
        roles = BotData.get_user_role(user_id)
        scopes = BotData.get_managed_scopes(user_id)
        
        # Mapping acronyms to full names
        area_map = {
            "QLD": "Qualidade",
            "GP": "Gestão de Pessoas",
            "DAF": "Adm. Financeiro",
            "MKT": "Marketing",
            "PSD": "Presidência"
        }
        
        role_lines = []
        consumed_scopes = set()
        has_leadership = len(scopes) > 0
        
        # Separate roles
        director_roles = []
        member_roles = []
        
        if roles:
            for r in roles:
                if r in scopes:
                    director_roles.append(r)
                    consumed_scopes.add(r)
                else:
                    member_roles.append(r)
        
        # Add Director lines
        for r in director_roles:
            full_name = area_map.get(r, r)
            role_lines.append(f"👤 Cargo: Diretor(a) de {full_name}")
            
        # Add Member lines (aggregated) - Only if NO leadership
        if member_roles and not has_leadership:
             terms = []
             for r in member_roles:
                 name = area_map.get(r, r)
                 if r in ["Odoyá", "Maná", "Gelé"]:
                     terms.append(f"do {name}")
                 else:
                     terms.append(name)
             
             if len(terms) > 1:
                 last = terms.pop()
                 joined = ", ".join(terms) + " e " + last
             else:
                 joined = terms[0]
             
             final_str = f"Membro de {joined}"
             final_str = final_str.replace("de do ", "do ")
             role_lines.append(f"👤 Cargo: {final_str}")
            
        if scopes:
            # Only show scopes that weren't used to define Directorship
            remaining_scopes = [s for s in scopes if s not in consumed_scopes]
            if remaining_scopes:
                formatted_scopes = []
                for s in remaining_scopes:
                    prefix = "Gerente do" if s in ["Odoyá", "Maná", "Gelé"] else "Gerente de"
                    formatted_scopes.append(f"{prefix} {s}")
                role_lines.append(f"💼 Função: {', '.join(formatted_scopes)}")
            
        role_text = "\n" + "\n".join(role_lines) if role_lines else ""
            
        text = f"""
🌟 Olá {update.effective_user.first_name}, o que você quer fazer?{role_text}
        """
        is_gp = BotData.is_user_in_role(user_id, "GP")
        managed_scopes = BotData.get_managed_scopes(user_id)
        is_manager = len(managed_scopes) > 0
        
        keyboard = [
            [KeyboardButton("📊 Marcar HO"), KeyboardButton("📁 Central Enactus")],
        ]
        
        if is_manager:
             keyboard.append([KeyboardButton("✅ Validar HOs")])

        if is_gp:
             keyboard.append([KeyboardButton("📈 Google Sheets"), KeyboardButton("🔔 Lembretes")])
             keyboard.append([KeyboardButton("❓ Ajuda")])
        else:
             keyboard.append([KeyboardButton("🔔 Lembretes"), KeyboardButton("❓ Ajuda")])
            
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _show_help(self, source):
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
        
        # When showing help, we usually don't need buttons if using persistent menu,
        # but we might want a "Close" button if it was inline?
        # If source is message (from menu), we just print help. 
        # If source is query (from inline "Help" button if any exist?), we might want to go back.
        # The main menu has "Ajuda", which is now a text command.
        
        await self._respond(source, help_text)
    
    async def _start_ho_flow(self, source, session):
        """Start the work hour registration flow"""
        # Clear previous session data
        session.clear()
        session['step'] = 'member_selection'
        session['waiting_for'] = 'member'
        
        text = """
👥 **Seleção de Membro**

Selecione seu nome no menu abaixo 👇
        """
        
        # Create keyboard with members (2 per row) - Using ReplyKeyboardMarkup
        keyboard = []
        for i in range(0, len(BotData.MEMBERS), 2):
            row = []
            row.append(KeyboardButton(BotData.MEMBERS[i]))
            if i + 1 < len(BotData.MEMBERS):
                row.append(KeyboardButton(BotData.MEMBERS[i + 1]))
            keyboard.append(row)
        
        keyboard.append([KeyboardButton("❌ Cancelar")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await self._respond(source, text, reply_markup)

    async def _handle_member_selection_text(self, update, session, text):
        """Handle member selection via text"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

        if text not in BotData.MEMBERS:
            await update.message.reply_text(
                "❌ **Membro não encontrado!**\n\nPor favor, selecione um nome da lista.",
                quote=False
            )
            return

        session['member'] = text
        session['step'] = 'task_type_selection'
        session['waiting_for'] = 'task_type'
        
        text_response = f"""
✅ **Membro selecionado:** {text}

📋 **Tipo de Tarefa**

A tarefa foi de área ou projeto?
        """
        
        keyboard = [
            [KeyboardButton("🎯 Projeto"), KeyboardButton("🏢 Área")],
            [KeyboardButton("❌ Cancelar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_task_type_text(self, update, session, text):
        """Handle task type selection via text"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return
            
        if text == "🎯 Projeto":
            session['task_type'] = "project"
            session['waiting_for'] = "project_selection"
            items = BotData.PROJECTS
            prompt_text = f"✅ **Tipo:** Projeto\n\n🎯 **Selecione o Projeto:**"
        elif text == "🏢 Área":
            session['task_type'] = "area"
            session['waiting_for'] = "area_selection"
            items = BotData.AREAS
            prompt_text = f"✅ **Tipo:** Área\n\n� **Selecione a Área:**"
        else:
            await update.message.reply_text("❌ Opção inválida. Escolha '🎯 Projeto' ou '🏢 Área'.")
            return
            
        keyboard = []
        for i in range(0, len(items), 2):
            row = []
            row.append(KeyboardButton(items[i]))
            if i + 1 < len(items):
                row.append(KeyboardButton(items[i+1]))
            keyboard.append(row)
        
        keyboard.append([KeyboardButton("❌ Cancelar")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(prompt_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_project_area_text(self, update, session, text, is_project):
        """Handle project or area selection via text"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return
            
        items = BotData.PROJECTS if is_project else BotData.AREAS
        
        if text not in items:
            await update.message.reply_text("❌ Opção inválida. Selecione um item da lista.")
            return
            
        session['project_area'] = text
        session['step'] = 'description_input'
        
        await self._ask_for_description(update.message, session)

    async def _ask_for_description(self, source, session):
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
        """
        
        # Provide Cancel button even for text input
        keyboard = [[KeyboardButton("❌ Cancelar")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await self._respond(source, text, reply_markup)

    async def _ask_for_date(self, source, session):
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

Para hoje, você pode selecionar o botão "Hoje" abaixo 👇
        """
        
        keyboard = [[KeyboardButton("Hoje")], [KeyboardButton("❌ Cancelar")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await self._respond(source, text, reply_markup)
    
    async def _handle_description_input(self, update, session, text):
        """Handle description input from user"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

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
        
        await self._ask_for_date(update.message, session)

    # _ask_for_date_from_message was redundant with the new flexible _ask_for_date that uses _respond,
    # but for safety I will remove it and use _ask_for_date everywhere suitable or alias it.
    # The previous code called _ask_for_date_from_message. I will redirect it.
    
    async def _ask_for_date_from_message(self, update, session):
         await self._ask_for_date(update.message, session)
    
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
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

        try:
            if text.lower() == "hoje" or text == "Hoje":
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

Digite o número de horas trabalhadas (use vírgula para decimais)
Exemplos: 2  |  1,5  |  0,5  |  3,25
            """
            
            keyboard = [[KeyboardButton("❌ Cancelar")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Data inválida!**\n\n"
                "Use o formato DD/MM/AAAA (ex: 21/08/2025) ou digite 'hoje' para a data atual.",
                parse_mode='Markdown'
            )
    
    async def _handle_hours_input(self, update, session, text):
        """Handle hours input from user"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

        try:
            # Replace comma with dot for decimal separation
            text = text.replace(',', '.')
            hours = float(text)
            
            if hours <= 0 or hours > 24:
                raise ValueError("Valor inválido")
            
            session['hours'] = hours
            session['step'] = 'modality_selection'
            session['waiting_for'] = 'modality'
            
            task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
            
            # Format hours for display (replace dot with comma)
            hours_display = str(hours).replace('.', ',')
            if hours_display.endswith(",0"):
                hours_display = hours_display[:-2]

            text_response = f"""
✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {hours_display}h

🌐 **Modalidade**

A atividade foi presencial ou EAD?
            """
            
            keyboard = []
            for i, modality in enumerate(BotData.MODALITIES):
                keyboard.append([KeyboardButton(modality)])
            
            keyboard.append([KeyboardButton("❌ Cancelar")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Número de horas inválido!**\n\n"
                "Digite um número válido entre 0.1 e 24 horas.\n"
                "Exemplos: 2  |  1,5  |  0,5  |  3,25",
                parse_mode='Markdown'
            )
    
    async def _handle_modality_text(self, update, session, text):
        """Handle modality selection via text"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

        if text not in BotData.MODALITIES:
            await update.message.reply_text("❌ Modalidade inválida. Selecione uma opção abaixo.")
            return
            
        session['modality'] = text
        session['step'] = 'confirmation'
        session['waiting_for'] = 'confirmation'
        
        task_type_display = "Projeto" if session['task_type'] == "project" else "Área"
        
        hours_display = str(session['hours']).replace('.', ',')
        if hours_display.endswith(",0"):
             hours_display = hours_display[:-2]

        text_response = f"""
📋 **Confirmação dos Dados**

✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {hours_display}h
✅ **Modalidade:** {text}

Confirma o registro desta HO?
        """
        
        keyboard = [
            [KeyboardButton("✅ Confirmar"), KeyboardButton("❌ Cancelar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_confirmation_text(self, update, session, text):
        """Handle final confirmation via text"""
        try:
            if text == "❌ Cancelar":
                await self._cancel_process(update.message, session)
                return
                
            if text == "✅ Confirmar":
                 await self._confirm_ho_text(update, session)
            else:
                 await update.message.reply_text("❌ Opção inválida.")
        except Exception as e:
            logger.error(f"Error in confirmation: {e}", exc_info=True)
            await update.message.reply_text("❌ Falha ao processar confirmação. Tente novamente.")

    async def _confirm_ho_text(self, update, session):
        """Confirm and save work hour (Text version)"""
        import uuid
        
        try:
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
                telegram_user_id=update.effective_user.id,
                ho_id=str(uuid.uuid4())
            )
            
            storage.add_work_hour(work_hour)
            
            # Attempt to sync to Google Sheets
            sync_status = ""
            try:
                if sheets_manager.is_available():
                    user_id = update.effective_user.id
                    if sheets_manager.sync_work_hour(work_hour, user_id):
                        sync_status = "\n📊 **Sincronizado com Google Sheets!**"
                    else:
                        sync_status = "\n⚠️ **Erro ao sincronizar com Google Sheets**"
                else:
                    sync_status = "\n📋 **Google Sheets não configurado**"
            except Exception as e:
                logger.error(f"Error syncing to sheets: {e}")
                sync_status = "\n⚠️ **Erro na integração com planilhas**"
            
            hours_display = str(session['hours']).replace('.', ',')
            if hours_display.endswith(",0"):
                 hours_display = hours_display[:-2]

            text = f"""
🎉 **HO Registrada com Sucesso!**

✅ **Membro:** {session['member']}
✅ **Tipo:** {task_type_display}
✅ **{task_type_display}:** {session['project_area']}
✅ **Descrição:** {session['description']}
✅ **Data:** {session['date']}
✅ **Horas:** {hours_display}h
✅ **Modalidade:** {session['modality']}
⏳ **Status:** Pendente de aprovação{sync_status}

O que deseja fazer agora?
            """
            
            # Same area/project option
            if session['task_type'] == "project":
                same_text = f"📊 Marcar outra HO do projeto {session['project_area']}"
            else:
                same_text = f"📊 Marcar outra HO da área {session['project_area']}"
                
            keyboard = [
                [KeyboardButton(same_text)],
                [KeyboardButton("🔄 Marcar outra (diferente)")],
                [KeyboardButton("✅ Finalizar"), KeyboardButton("🏠 Menu Principal")]
            ]
            
            session['step'] = 'post_completion'
            session['waiting_for'] = 'post_completion'
            
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
             logger.error(f"Error saving HO: {e}", exc_info=True)
             await update.message.reply_text("❌ Erro ao salvar HO. Por favor contacte o administrador.")

    async def _handle_post_completion_text(self, update, session, text):
        """Handle actions after completion"""
        try:
            if text == "🏠 Menu Principal":
                # Clear session and show menu
                storage.clear_user_session(update.effective_user.id)
                await self._show_main_menu_message(update)
                return

            if text == "✅ Finalizar":
                storage.clear_user_session(update.effective_user.id)
                await update.message.reply_text("🎉 **Obrigado!** Até a próxima! 🤝", parse_mode='Markdown')
                await self._show_main_menu_message(update)
                return
                
            if text == "🔄 Marcar outra (diferente)":
                 # Restart partial flow
                 member = session['member']
                 session.clear()
                 session['member'] = member
                 session['step'] = 'task_type_selection'
                 session['waiting_for'] = 'task_type'
                 # Re-prompt task type
                 keyboard = [
                    [KeyboardButton("🎯 Projeto"), KeyboardButton("🏢 Área")],
                    [KeyboardButton("❌ Cancelar")]
                 ]
                 reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                 await update.message.reply_text(f"✅ **Membro selecionado:** {member}\n\n📋 **Tipo de Tarefa**\n\nA tarefa foi de área ou projeto?", reply_markup=reply_markup, parse_mode='Markdown')
                 return

            # Check for dynamic "Same Project" button
            if text.startswith("📊 Marcar outra HO"):
                 # Keep context
                 member = session['member']
                 task_type = session['task_type']
                 project_area = session['project_area']
                 
                 session.clear()
                 session['member'] = member
                 session['task_type'] = task_type
                 session['project_area'] = project_area
                 session['step'] = 'description_input'
                 
                 await self._ask_for_description(update.message, session)
                 return
                 
            await update.message.reply_text("❌ Opção inválida.")
        except Exception as e:
            logger.error(f"Error in post-completion: {e}", exc_info=True)
            await update.message.reply_text("❌ Erro ao processar opção.")
    
            logger.error(f"Error in post-completion: {e}", exc_info=True)
            await update.message.reply_text("❌ Erro ao processar opção.")

    async def _handle_validation_flow(self, source, session):
        """Start validation flow for managers"""
        if hasattr(source, 'from_user'):
             user_id = source.from_user.id
        else:
             user_id = source.chat.id

        managed_scopes = BotData.get_managed_scopes(user_id)
        
        if not managed_scopes:
            await self._respond(source, "❌ Você não tem permissão para validar HOs.")
            return
            
        await self._respond(source, "🔄 Buscando pendências na planilha...")
        
        try:
            pending = sheets_manager.get_pending_approvals(managed_scopes)
        except Exception as e:
            logger.error(str(e))
            pending = []
        
        if not pending:
            await self._respond(source, "✅ **Tudo em dia!**\n\nNenhuma HO pendente para as suas áreas/projetos.")
            return
            
        session['validation_queue'] = pending
        session['validation_index'] = 0
        
        await self._show_next_validation(source, session)

    async def _show_next_validation(self, source, session):
        """Show next HO to validate"""
        queue = session.get('validation_queue', [])
        idx = session.get('validation_index', 0)
        
        if idx >= len(queue):
            session.pop('validation_queue', None)
            session.pop('validation_index', None)
            await self._respond(source, "🎉 **Validação Concluída!**\n\nTodas as pendências foram revisadas.")
            return
            
        item = queue[idx]
        total = len(queue)
        
        # Format date for display if needed, but item['date'] should be readable
        
        text = f"""
🛡️ **Validação de HO ({idx + 1}/{total})**

👤 **Membro:** {item['member']}
📂 **Projeto/Área:** {item['project']}
📅 **Data:** {item['date']}
⏱️ **Horas:** {item['hours']}
📝 **Descrição:**
{item['description']}

O que deseja fazer?
        """
        
        row_id = item['row_id']
        
        keyboard = [
            [InlineKeyboardButton("✅ Aprovar", callback_data=f"validate_approve_{row_id}")],
            [InlineKeyboardButton("❌ Rejeitar", callback_data=f"validate_reject_{row_id}")],
            [InlineKeyboardButton("⏭️ Pular", callback_data="validate_skip")],
            [InlineKeyboardButton("🚪 Sair", callback_data="validate_exit")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self._respond(source, text, reply_markup)

    async def _handle_validation_action(self, query, session, action):
        """Handle validation approve/reject/skip/exit"""
        if action == "exit":
            session.pop('validation_queue', None)
            session.pop('validation_index', None)
            await query.edit_message_text("🚪 Validação encerrada.")
            await self._show_main_menu_compat(query)
            return

        idx = session.get('validation_index', 0)
        queue = session.get('validation_queue', [])
        
        if idx >= len(queue):
             await query.edit_message_text("⚠️ Sessão de validação expirada ou concluída.")
             return
             
        # item = queue[idx] # Unused but good for debug
        
        if action == "skip":
             session['validation_index'] = idx + 1
             await self._show_next_validation(query, session)
             return
             
        # Action is approve_{row_id} or reject_{row_id}
        parts = action.split("_", 1)
        if len(parts) < 2:
             await query.edit_message_text("❌ Erro interno na ação.")
             return
             
        action_type, row_id_str = parts
        try:
            row_id = int(row_id_str)
        except ValueError:
             await query.edit_message_text("❌ Erro no ID da linha.")
             return
             
        validator_name = query.from_user.first_name
        new_status = "Aprovado" if action_type == "approve" else "Reprovado"
        
        await query.edit_message_text(f"🔄 Processando {new_status}...", parse_mode='Markdown')
        
        success = sheets_manager.update_ho_status(row_id, new_status, validator_name)
        
        if success:
            status_icon = "✅" if action_type == "approve" else "❌"
            # Edit text to show result, then move on?
            # Or just move on immediately?
            # Better to show result for a second or just update content.
            # We will call show_next, which sends a NEW message (edit or reply).
            # _respond treats CallbackQuery by editing. So subsequent _show_next will OVERWRITE this status message.
            # That's fine.
            pass 
        else:
            await query.message.reply_text(f"⚠️ **Erro ao salvar na planilha.** Verifique os logs.", parse_mode='Markdown')
            
        # Move to next
        session['validation_index'] = idx + 1
        await self._show_next_validation(query, session)
    
    async def _handle_modality_selection(self, query, session):
        """Handle modality selection"""
        modality_index = int(query.data.split("_")[1])
        selected_modality = BotData.MODALITIES[modality_index]
        session['modality'] = selected_modality
        session['step'] = 'confirmation'
        session['waiting_for'] = 'confirmation' # Set waiting_for for text handler
        
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
        session['step'] = 'post_completion' # Set step for callback queries
        session['waiting_for'] = 'post_completion_callback' # Differentiate from text handler
    
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
        session['waiting_for'] = 'description' # Set waiting_for for text handler
        
        await self._ask_for_description(query, session)
    
    async def _mark_another_different(self, query, session):
        """Mark another HO for different area/project"""
        # Keep only member
        member = session['member']
        session.clear()
        session['member'] = member
        session['step'] = 'task_type_selection'
        session['waiting_for'] = 'task_type' # Set waiting_for for text handler
        
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
    
    async def _cancel_process(self, source, session):
        """Cancel current process"""
        if hasattr(source, 'from_user'):
             user_id = source.from_user.id
        else:
             # creating a dummy user_id if needed, or assume source works
             user_id = source.chat.id # Fallback

        storage.clear_user_session(user_id)
        
        text = """
❌ **Processo Cancelado**

Operação cancelada. Você pode iniciar novamente quando quiser.
        """
        
        # When cancelling, restore main menu
        keyboard = [
            [KeyboardButton("📊 Marcar HO"), KeyboardButton("📁 Central Enactus")],
            [KeyboardButton("📈 Google Sheets"), KeyboardButton("🔔 Lembretes")],
            [KeyboardButton("❓ Ajuda")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await self._respond(source, text, reply_markup)
    
    # ==================== REMINDER FUNCTIONALITY ====================
    
    async def _show_reminders_menu(self, source, session):
        """Show reminders management menu"""
        user_id = source.from_user.id
        
        # Get independent reminders
        pch_reminder = storage.get_user_reminder_by_type(user_id, ReminderType.PCH)
        ho_reminder = storage.get_user_reminder_by_type(user_id, ReminderType.HO)
        
        # PCH Status
        if pch_reminder and pch_reminder.is_active:
            pch_status = "🟢 Ativo (Dom 12:00)"
            pch_btn_text = "📅 Desativar PCH"
            pch_action = "toggle_pch_off"
        else:
            pch_status = "🔴 Inativo"
            pch_btn_text = "📅 Ativar PCH"
            pch_action = "toggle_pch_on"
            
        # HO Status
        if ho_reminder and ho_reminder.is_active:
            freq_map = {
                ReminderFrequency.WEEKLY: "Semanal",
                ReminderFrequency.MONTHLY: "Mensal"
            }
            freq = freq_map.get(ho_reminder.frequency, "Personalizado")
            day_str = ""
            if ho_reminder.frequency == ReminderFrequency.WEEKLY:
                days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
                if ho_reminder.day_of_week is not None:
                     day_str = f" - {days[ho_reminder.day_of_week]}"
            elif ho_reminder.frequency == ReminderFrequency.MONTHLY:
                day_str = f" - Dia {ho_reminder.day_of_month}"
                
            time_str = ho_reminder.time_of_day.strftime('%H:%M')
            ho_status = f"🟢 {freq}{day_str} às {time_str}"
            ho_btn_text = "📝 Reconfigurar HO"
            ho_disable_btn = True
        else:
            ho_status = "🔴 Inativo"
            ho_btn_text = "📝 Configurar HO"
            ho_disable_btn = False
            
        text = f"""
🔔 **Central de Lembretes**

📅 **Lembrete PCH (Planilha)**
Status: {pch_status}
_Lembrete fixo aos Domingos, 12:00 com o link da planilha._

📝 **Lembrete de HO**
Status: {ho_status}
_Lembrete personalizado para marcar suas horas._

O que deseja fazer?
        """
        
        keyboard = [
            [KeyboardButton(pch_btn_text)],
            [KeyboardButton(ho_btn_text)]
        ]
        
        if ho_disable_btn:
            keyboard.append([KeyboardButton("❌ Desativar Lembrete HO")])
            
        keyboard.append([KeyboardButton("🏠 Menu Principal")])
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await self._respond(source, text, reply_markup)
    
    async def _handle_pch_toggle_text(self, update, session, text):
        """Toggle PCH reminder on/off (Text version)"""
        user_id = update.effective_user.id
        
        if text == "📅 Ativar PCH":
            # Create PCH reminder (Sunday 12:00)
            reminder = Reminder(
                user_id=user_id,
                member_name=update.effective_user.first_name, 
                type=ReminderType.PCH,
                frequency=ReminderFrequency.WEEKLY,
                day_of_week=6, # Sunday
                time_of_day=time(12, 0),
                is_active=True
            )
            storage.add_reminder(reminder)
            await update.message.reply_text("✅ **Lembrete PCH ativado!**", parse_mode='Markdown')
        else:
            storage.remove_user_reminder(user_id, ReminderType.PCH)
            await update.message.reply_text("❌ **Lembrete PCH desativado.**", parse_mode='Markdown')
            
        await self._show_reminders_menu(update.message, session)

    # Legacy callback based handler kept for compatibility if needed, or can be removed
    async def _handle_pch_toggle(self, query, session):
         await self._handle_pch_toggle_text(query, session, "📅 Ativar PCH" if query.data == "toggle_pch_on" else "📅 Desativar PCH")

    async def _disable_ho_reminder_text(self, update, session):
        """Disable HO reminder (Text version)"""
        user_id = update.effective_user.id
        storage.remove_user_reminder(user_id, ReminderType.HO)
        await update.message.reply_text("❌ **Lembrete HO desativado.**", parse_mode='Markdown')
        await self._show_reminders_menu(update.message, session)

    async def _start_ho_reminder_setup(self, source, session):
        """Start HO reminder setup flow"""
        session.clear()
        
        # Try to identify user by Telegram ID
        user_id = source.from_user.id
        member_profile = BotData.get_member(user_id)
        
        if member_profile:
            # Auto-dectected
            session['reminder_member'] = member_profile.name
            # Skip to frequency selection
            session['step'] = 'frequency_selection'
            session['waiting_for'] = 'reminder_frequency_text'
            
            text = f"""
✅ **Membro Identificado:** {member_profile.name}

📅 **Qual a frequência do lembrete?**
            """
            keyboard = [
                [KeyboardButton("Semanal"), KeyboardButton("Mensal")],
                [KeyboardButton("❌ Cancelar")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await self._respond(source, text, reply_markup)
            
        else:
            # Not identified, ask for name
            session['step'] = 'reminder_member'
            session['waiting_for'] = 'reminder_member_text'
            
            text = """
⚙️ **Configurar Lembrete HO**

Para quem é este lembrete? 👇
            """
            
            keyboard = []
            for i in range(0, len(BotData.MEMBERS), 2):
                row = []
                row.append(KeyboardButton(BotData.MEMBERS[i]))
                if i + 1 < len(BotData.MEMBERS):
                    row.append(KeyboardButton(BotData.MEMBERS[i + 1]))
                keyboard.append(row)
            
            keyboard.append([KeyboardButton("❌ Cancelar")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await self._respond(source, text, reply_markup)

    async def _handle_reminder_member_text(self, update, session, text):
        """Handle member selection for reminder"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return
            
        if text not in BotData.MEMBERS:
            await update.message.reply_text("❌ Membro inválido.")
            return
            
        session['reminder_member'] = text
        session['step'] = 'frequency_selection'
        session['waiting_for'] = 'reminder_frequency_text'
        
        text = f"""
✅ **Membro:** {text}

📅 **Qual a frequência do lembrete?**
        """
        
        keyboard = [
            [KeyboardButton("Semanal"), KeyboardButton("Mensal")],
            [KeyboardButton("❌ Cancelar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_reminder_frequency_text(self, update, session, text):
        """Handle frequency selection"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return

        map_freq = {
            "Semanal": (ReminderFrequency.WEEKLY, "Semanal"),
            "Mensal": (ReminderFrequency.MONTHLY, "Mensal")
        }
        
        if text not in map_freq:
            await update.message.reply_text("❌ Frequência inválida. Escolha Semanal ou Mensal.")
            return
            
        session['reminder_freq'] = map_freq[text][0]
        session['reminder_freq_text'] = map_freq[text][1]
        session['step'] = 'day_selection'
        session['waiting_for'] = 'reminder_day_text'
        
        if session['reminder_freq'] == ReminderFrequency.WEEKLY:
            text_response = """
📅 **Configuração Semanal**

Qual dia da semana você quer receber o aviso?
Selecione abaixo 👇
            """
            keyboard = [
                [KeyboardButton("Segunda"), KeyboardButton("Terça"), KeyboardButton("Quarta")],
                [KeyboardButton("Quinta"), KeyboardButton("Sexta")],
                [KeyboardButton("Sábado"), KeyboardButton("Domingo")],
                [KeyboardButton("❌ Cancelar")]
            ]
        else:
            text_response = """
📅 **Configuração Mensal**

Qual dia do mês você quer receber o aviso?
Selecione o dia abaixo 👇
            """
            # Create a 7-column numeric keypad for days 1-31
            days = [str(i) for i in range(1, 32)]
            keyboard = []
            row = []
            for day in days:
                row.append(KeyboardButton(day))
                if len(row) == 7:
                    keyboard.append(row)
                    row = []
            
            if row:
                keyboard.append(row)
                
            keyboard.append([KeyboardButton("❌ Cancelar")])
            
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(text_response, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_reminder_day_text(self, update, session, text):
        """Handle day selection"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return
            
        day_val = None
        if session['reminder_freq'] == ReminderFrequency.WEEKLY:
            days_map = {
                "Segunda": 0, "Terça": 1, "Quarta": 2, "Quinta": 3,
                "Sexta": 4, "Sábado": 5, "Domingo": 6
            }
            if text in days_map:
                day_val = days_map[text]
            else:
                 await update.message.reply_text("❌ Dia inválido. Selecione uma opção válida.")
                 return
        else:
            # Monthly
            try:
                val = int(text)
                if 1 <= val <= 31:
                    day_val = val
                else:
                    raise ValueError
            except ValueError:
                 await update.message.reply_text("❌ Dia inválido. Digite um número entre 1 e 31.")
                 return
        
        session['reminder_day'] = day_val
        session['step'] = 'time_input'
        session['waiting_for'] = 'reminder_time'
        
        text_resp = f"""
✅ **Frequência:** {session['reminder_freq_text']}
✅ **Dia:** {text}

🕐 **Horário do Lembrete**

Digite o horário no formato HH:MM (24h)
Exemplo: 09:00, 18:30
        """
        keyboard = [[KeyboardButton("❌ Cancelar")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(text_resp, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_reminder_time_input(self, update, session, text):
        """Handle time input and save reminder"""
        if text == "❌ Cancelar":
            await self._cancel_process(update.message, session)
            return
            
        try:
             t = datetime.strptime(text, "%H:%M").time()
        except ValueError:
             await update.message.reply_text("❌ Formato inválido. Use HH:MM (ex: 18:00).")
             return
             
        # Save Reminder
        user_id = update.effective_user.id
        
        reminder = Reminder(
            user_id=user_id,
            member_name=session.get('reminder_member', update.effective_user.first_name),
            type=ReminderType.HO,
            frequency=session['reminder_freq'],
            day_of_week=session['reminder_day'] if session['reminder_freq'] == ReminderFrequency.WEEKLY else None,
            day_of_month=session['reminder_day'] if session['reminder_freq'] == ReminderFrequency.MONTHLY else None,
            time_of_day=t,
            is_active=True
        )
        storage.add_reminder(reminder)
        
        storage.clear_user_session(user_id)
        
        await update.message.reply_text(
            "✅ **Lembrete de HO configurado com sucesso!**",
            parse_mode='Markdown'
        )
        
        # Return to main menu as requested ("any flow completion -> welcome message")
        await self._show_main_menu_compat(update)
    
    # Legacy handlers removed to avoid duplicates
    
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
    
    async def _show_sheets_menu(self, source, session):
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
        await self._respond(source, text, reply_markup)
    
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

https://docs.google.com/spreadsheets/d/1jhKWvxQ4FYgpTsxjuU7itWC_PYT6oWk_im2gzfo0Gu0/

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