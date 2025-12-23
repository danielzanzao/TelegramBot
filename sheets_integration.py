"""
Google Sheets Integration for EnactusBOT
Handles synchronization of work hour data with Google Sheets
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from data_models import WorkHour, MemberProfile, Reminder, ReminderType, ReminderFrequency

load_dotenv()

logger = logging.getLogger(__name__)

class SheetsManager:
    """Manages Google Sheets operations for EnactusBOT"""
    
    def __init__(self):
        """Initialize the Sheets Manager"""
        self.service = None
        self.ho_spreadsheet_id = None
        self.db_spreadsheet_id = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets service with authentication using fragmented credentials"""
        try:
            # Get individual credential components from environment variables
            project_id = os.environ.get('GOOGLE_PROJECT_ID')
            private_key_id = os.environ.get('GOOGLE_PRIVATE_KEY_ID')
            private_key = os.environ.get('GOOGLE_PRIVATE_KEY')
            client_email = os.environ.get('GOOGLE_CLIENT_EMAIL')
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            
            # Spreadsheet IDs
            self.ho_spreadsheet_id = os.environ.get('ENACTUS_SPREADSHEET_ID')
            self.db_spreadsheet_id = os.environ.get('ENACTUS_DB_SPREADSHEET_ID')
            
            # Check if we have the required credentials
            required_vars = [project_id, private_key, client_email]
            if not all(required_vars):
                logger.warning("Missing required Google credentials")
                logger.info("Required: GOOGLE_PROJECT_ID, GOOGLE_PRIVATE_KEY, GOOGLE_CLIENT_EMAIL")
                return
            if not project_id:
                logger.warning("Project ID faltando")
                
            if not private_key:
                logger.warning("Private KEY faltando")
                
            if not client_email:
                logger.warning("Client Email faltando")
                return
            
            if not self.ho_spreadsheet_id:
                logger.warning("HO Spreadsheet ID not found (ENACTUS_SPREADSHEET_ID)")
            
            if not self.db_spreadsheet_id:
                logger.warning("DB Spreadsheet ID not found (ENACTUS_DB_SPREADSHEET_ID). Persistence features may be limited.")
            
            # Clean up the private key (remove quotes and fix formatting)
            if private_key:
                # ... (Key processing logic kept same or assumed already correct in replacement) ...
                logger.info("Processing Private Key...")
                raw_len = len(private_key)
                private_key = private_key.strip('"').strip("'")
                private_key = private_key.replace('\\n', '\n')
                private_key = private_key.strip()
                
                if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                    if '-----BEGIN PRIVATE KEY-----' not in private_key:
                        private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}\n-----END PRIVATE KEY-----"
                    else:
                        private_key = private_key.strip()
                
                # ... (logging kept same) ...
            
            # Build credentials info from fragments
            credentials_info = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": private_key_id or "default",
                "private_key": private_key,
                "client_email": client_email,
                "client_id": client_id or "default",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40') if client_email else 'default'}"
            }
            
            # Set up credentials with required scopes
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Create credentials from the service account info
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=scopes
            )
            
            # Build the service
            self.service = build('sheets', 'v4', credentials=credentials)
            
            logger.info("Google Sheets service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {str(e)}")
            self.service = None
    
    def is_available(self) -> bool:
        """Check if HO Sheets integration is available"""
        return self.service is not None and self.ho_spreadsheet_id is not None

    def is_db_available(self) -> bool:
        """Check if DB Sheets integration is available"""
        return self.service is not None and self.db_spreadsheet_id is not None
    
    def create_enactus_spreadsheet(self, title: str = "Enactus HO Tracking") -> Optional[str]:
        """Create a new spreadsheet for Enactus HO tracking"""
        if not self.service:
            logger.error("Google Sheets service not available")
            return None
            
        try:
            spreadsheet_body = {
                'properties': {
                    'title': title
                },
                'sheets': [
                    {
                        'properties': {
                            'title': 'Registro HO',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 13
                            }
                        }
                    }
                ]
            }
            
            spreadsheet = self.service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            logger.info(f"Created new spreadsheet: {spreadsheet_id}")
            
            # Set up headers
            self._setup_headers(spreadsheet_id)
            
            return spreadsheet_id
            
        except HttpError as e:
            logger.error(f"Failed to create spreadsheet: {str(e)}")
            return None
    
    def _setup_headers(self, spreadsheet_id: str):
        """Set up column headers in the spreadsheet"""
        if not self.service:
            return
            
        headers = [
            ['Data/Hora', 'Membro', 'Tipo', 'Projeto/Área', 'Descrição', 'Data Trabalho', 'Horas', 'Modalidade', 'Status', 'HO ID', 'ID Telegram', 'Aprovado Por', 'Data Aprovação']
        ]
        
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Registro HO!A1:M1',
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
            
            # Format headers (bold)
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': 13
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'bold': True
                                },
                                'backgroundColor': {
                                    'red': 0.9,
                                    'green': 0.9,
                                    'blue': 0.9
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                }
            ]
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            logger.info("Headers set up successfully")
            
        except HttpError as e:
            logger.error(f"Failed to set up headers: {str(e)}")
    
    def sync_work_hour(self, work_hour: WorkHour, user_id: int) -> bool:
        """Sync a single work hour entry to Google Sheets with auto-retry on auth failure"""
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            if not self.is_available():
                logger.info("Service not available, attempting initialization...")
                self._initialize_service()
                if not self.is_available():
                    logger.warning("Google Sheets still not available after init.")
                    if attempt == max_retries: return False
                    continue

            try:
                # Prepare row data
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                work_date = work_hour.date
                
                row_data = [
                    timestamp,                    # Data/Hora de registro
                    work_hour.member_name,        # Membro
                    work_hour.task_type,          # Tipo (Projeto/Área)
                    work_hour.project_area,       # Projeto/Área específica
                    work_hour.description,        # Descrição da atividade
                    work_date,                    # Data do trabalho
                    str(work_hour.hours).replace('.', ','),         # Horas trabalhadas
                    work_hour.modality,           # Modalidade (Presencial/EAD)
                    work_hour.status,             # Status (Pendente/Aprovado/Reprovado)
                    work_hour.ho_id or '',        # HO ID único
                    str(user_id),                 # ID do usuário Telegram
                    work_hour.approved_by or '',  # Aprovado por
                    work_hour.approval_date.strftime('%d/%m/%Y %H:%M:%S') if work_hour.approval_date else ''
                ]
                
                # Find next empty row
                next_row = self._get_next_empty_row()
                range_name = f'Registro HO!A{next_row}:M{next_row}'
                
                if not self.service:
                    raise Exception("Service lost during operation")

                result = self.service.spreadsheets().values().update(
                    spreadsheetId=self.ho_spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': [row_data]}
                ).execute()
                
                updated_cells = result.get('updatedCells', 0)
                if updated_cells > 0:
                    logger.info(f"Successfully synced work hour to row {next_row}")
                    return True
                else:
                    logger.warning("No cells were updated during sync")
                    return False
                    
            except Exception as e:
                error_str = str(e)
                logger.error(f"Sync attempt {attempt+1} failed: {error_str}")
                
                # Check for auth errors to trigger re-init
                is_auth_error = "invalid_grant" in error_str or "unauthorized" in error_str.lower() or "401" in error_str
                
                if is_auth_error and attempt < max_retries:
                    logger.warning("Authentication error detected. Forcing service re-initialization...")
                    self.service = None # Clear bad service
                    self._initialize_service()
                    continue
                
                if attempt == max_retries:
                    return False
        return False
    
    def sync_multiple_work_hours(self, work_hours: List[WorkHour], user_id: int) -> int:
        """Sync multiple work hour entries to Google Sheets"""
        if not self.is_available():
            logger.warning("Google Sheets not available for batch sync")
            return 0
            
        if not work_hours:
            return 0
            
        try:
            # Prepare batch data
            batch_data = []
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            
            for work_hour in work_hours:
                work_date = work_hour.date  # WorkHour uses 'date' field
                row_data = [
                    timestamp,
                    work_hour.member_name,
                    work_hour.task_type,
                    work_hour.project_area,
                    work_hour.description,
                    work_date,
                    str(work_hour.hours).replace('.', ','),
                    work_hour.modality,
                    work_hour.status,
                    work_hour.ho_id or '',
                    str(user_id),
                    work_hour.approved_by or '',
                    work_hour.approval_date.strftime('%d/%m/%Y %H:%M:%S') if work_hour.approval_date else ''
                ]
                batch_data.append(row_data)
            
            # Find next empty row
            start_row = self._get_next_empty_row()
            end_row = start_row + len(batch_data) - 1
            range_name = f'Registro HO!A{start_row}:M{end_row}'
            
            # Batch update
            if not self.service:
                return 0
                
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.ho_spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': batch_data}
            ).execute()
            
            updated_cells = result.get('updatedCells', 0)
            synced_rows = updated_cells // 13  # 13 columns per row
            
            logger.info(f"Successfully synced {synced_rows} work hours to Google Sheets")
            return synced_rows
            
        except HttpError as e:
            logger.error(f"Failed to batch sync work hours: {str(e)}")
            return 0
    
    def _get_next_empty_row(self) -> int:
        """Find the next empty row in the spreadsheet"""
        if not self.service:
            return 2
            
        try:
            # Get all data from column A to determine last used row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.ho_spreadsheet_id,
                range='Registro HO!A:A'
            ).execute()
            
            values = result.get('values', [])
            return len(values) + 1  # Next empty row
            
        except HttpError:
            # If there's an error, assume row 2 (after headers)
            return 2
    
    def get_member_summary(self, member_name: str) -> Dict[str, Any]:
        """Get work hour summary for a specific member"""
        if not self.is_available():
            return {}
            
        try:
            # Get all data
            if not self.service:
                return {}
                
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.ho_spreadsheet_id,
                range='Registro HO!A:J'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers or empty
                return {'total_hours': 0, 'entries': 0, 'projects': [], 'areas': []}
            
            # Process data for specific member
            total_hours = 0
            entries = 0
            projects = set()
            areas = set()
            
            for row in values[1:]:  # Skip headers
                if len(row) >= 6 and row[1] == member_name:  # Check member name
                    try:
                        hours = float(row[5])  # Hours column
                        total_hours += hours
                        entries += 1
                        
                        task_type = row[2]  # Tipo
                        project_area = row[3]  # Projeto/Área
                        
                        if task_type == 'Projeto':
                            projects.add(project_area)
                        elif task_type == 'Área':
                            areas.add(project_area)
                            
                    except (ValueError, IndexError):
                        continue
            
            return {
                'total_hours': total_hours,
                'entries': entries,
                'projects': list(projects),
                'areas': list(areas)
            }
            
        except HttpError as e:
            logger.error(f"Failed to get member summary: {str(e)}")
            return {}
    
    def get_spreadsheet_url(self) -> Optional[str]:
        """Get the URL of the current spreadsheet"""
        if not self.ho_spreadsheet_id:
            return None
        return f"https://docs.google.com/spreadsheets/d/{self.ho_spreadsheet_id}/edit"


    def get_pending_approvals(self, managed_scopes: List[str]) -> List[Dict]:
        """Get pending HOs for specific scopes"""
        if not self.is_available(): return []
        
        try:
            # Read all data
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.ho_spreadsheet_id,
                range='Registro HO!A:K'  # Read up to K just in case
            ).execute()
            
            rows = result.get('values', [])
            if not rows or len(rows) < 2: return [] # No data or just header
            
            pending = []
            # Start from row 2 (index 1 in 0-based list, but row number is index+1)
            for i, row in enumerate(rows):
                if i == 0: continue # Skip header
                
                # Check bounds
                if len(row) <= 8: continue # Not enough cols for Status
                
                status = row[8] # Col I
                project_area = row[3] if len(row) > 3 else "" # Col D
                
                if status == "Pendente" and project_area in managed_scopes:
                    member = row[1] if len(row) > 1 else "Desconhecido" # Col B
                    description = row[4] if len(row) > 4 else "" # Col E
                    date_val = row[5] if len(row) > 5 else "" # Col F
                    hours = row[6] if len(row) > 6 else "" # Col G
                    
                    pending.append({
                        'row_id': i + 1,
                        'member': member,
                        'project': project_area,
                        'description': description,
                        'date': date_val,
                        'hours': hours,
                        'telegram_id': row[10] if len(row) > 10 else None
                    })
            return pending
            
        except Exception as e:
            logger.error(f"Error fetching pending approvals: {e}")
            return []

    def update_ho_status(self, row_id: int, new_status: str, approver_name: str) -> bool:
        """Update status of a HO record"""
        if not self.is_available(): return False
        
        try:
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            
            # Update Status (Col I)
            self.service.spreadsheets().values().update(
                spreadsheetId=self.ho_spreadsheet_id,
                range=f'Registro HO!I{row_id}',
                valueInputOption='RAW',
                body={'values': [[new_status]]}
            ).execute()
            
            # Update Approved By and Date (Cols L, M)
            # Col L is index 11 (12th col), M is index 12 (13th col)
            self.service.spreadsheets().values().update(
                spreadsheetId=self.ho_spreadsheet_id,
                range=f'Registro HO!L{row_id}:M{row_id}',
                valueInputOption='RAW',
                body={'values': [[approver_name, timestamp]]}
            ).execute()
            
            logger.info(f"Updated HO row {row_id} to {new_status} by {approver_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating HO status: {e}")
            return False

    # ========================== DB SPREADSHEET METHODS ==========================
    
    def ensure_db_structure(self):
        """Ensure the DB spreadsheet has 'Membros' and 'Lembretes' tabs"""
        if not self.is_db_available():
            logger.warning("DB Spreadsheet unavailable for structure check")
            return
            
        try:
            metadata = self.service.spreadsheets().get(spreadsheetId=self.db_spreadsheet_id).execute()
            sheets = metadata.get('sheets', [])
            sheet_titles = [s['properties']['title'] for s in sheets]
            
            requests = []
            
            # Check for 'Membros'
            if 'Membros' not in sheet_titles:
                requests.append({
                    'addSheet': {'properties': {'title': 'Membros'}}
                })
                
            # Check for 'Lembretes'
            if 'Lembretes' not in sheet_titles:
                requests.append({
                    'addSheet': {'properties': {'title': 'Lembretes'}}
                })
                
            if requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.db_spreadsheet_id,
                    body={'requests': requests}
                ).execute()
                logger.info("Created missing DB sheets (Membros/Lembretes)")
                
                # Update headers for new sheets
                if 'Membros' not in sheet_titles:
                    self._setup_members_header()
                if 'Lembretes' not in sheet_titles:
                    self._setup_reminders_header()
            
        except Exception as e:
            logger.error(f"Error ensuring DB structure: {e}")

    def _setup_members_header(self):
        """Set up headers for 'Membros' sheet"""
        values = [['Nome', 'Telegram ID', 'Cargos', 'Áreas Gerenciadas', 'Email', 'Matrícula']]
        self.service.spreadsheets().values().update(
            spreadsheetId=self.db_spreadsheet_id,
            range='Membros!A1:F1',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

    def _setup_reminders_header(self):
        """Set up headers for 'Lembretes' sheet"""
        values = [['Telegram ID', 'Nome', 'Tipo (HO/PCH)', 'Frequência', 'Dia Semana', 'Dia Mês', 'Hora', 'Ativo?']]
        self.service.spreadsheets().values().update(
            spreadsheetId=self.db_spreadsheet_id,
            range='Lembretes!A1:H1',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

    def load_members(self) -> List[MemberProfile]:
        """Load members from DB spreadsheet"""
        if not self.is_db_available(): return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.db_spreadsheet_id,
                range='Membros!A:F'
            ).execute()
            
            rows = result.get('values', [])
            if not rows or len(rows) < 2: return []
            
            members = []
            for i, row in enumerate(rows):
                if i == 0: continue # Skip header
                if not row: continue
                
                name = row[0]
                tid_str = row[1] if len(row) > 1 else None
                roles_str = row[2] if len(row) > 2 else ""
                scopes_str = row[3] if len(row) > 3 else ""
                
                telegram_id = int(tid_str) if tid_str and tid_str.isdigit() else None
                roles = [r.strip() for r in roles_str.split(',')] if roles_str else []
                scopes = [s.strip() for s in scopes_str.split(',')] if scopes_str else []
                email = row[4] if len(row) > 4 else None
                matricula = row[5] if len(row) > 5 else None
                
                members.append(MemberProfile(
                    name=name,
                    telegram_id=telegram_id,
                    roles=roles,
                    managed_scopes=scopes,
                    email=email,
                    matricula=matricula
                ))
            
            logger.info(f"Loaded {len(members)} members from DB")
            return members
            
        except Exception as e:
            logger.error(f"Error loading members: {e}")
            return []

    def save_members(self, members: List[MemberProfile]):
        """Save entire member list to DB overwriting"""
        if not self.is_db_available(): return
        
        try:
            # Prepare data
            rows = [['Nome', 'Telegram ID', 'Cargos', 'Áreas Gerenciadas', 'Email', 'Matrícula']]
            for m in members:
                rows.append([
                    m.name,
                    str(m.telegram_id) if m.telegram_id else "",
                    ", ".join(m.roles),
                    ", ".join(m.managed_scopes),
                    m.email if m.email else "",
                    m.matricula if m.matricula else ""
                ])
                
            # Clear existing
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.db_spreadsheet_id,
                range='Membros!A:F'
            ).execute()
            
            # Write new
            self.service.spreadsheets().values().update(
                spreadsheetId=self.db_spreadsheet_id,
                range='Membros!A1',
                valueInputOption='RAW',
                body={'values': rows}
            ).execute()
            
            logger.info("Saved members to DB")
            
        except Exception as e:
            logger.error(f"Error saving members: {e}")

    def load_reminders(self) -> List[Reminder]:
        """Load reminders from DB spreadsheet"""
        if not self.is_db_available(): return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.db_spreadsheet_id,
                range='Lembretes!A:H'
            ).execute()
            
            rows = result.get('values', [])
            if not rows or len(rows) < 2: return []
            
            reminders = []
            for i, row in enumerate(rows):
                if i == 0: continue # Skip header
                if len(row) < 8: continue
                
                try:
                    user_id = int(row[0])
                    name = row[1]
                    r_type_str = row[2]
                    freq_str = row[3]
                    day_week = int(row[4]) if row[4] and row[4] != 'None' else None
                    day_month = int(row[5]) if row[5] and row[5] != 'None' else None
                    
                    time_parts = row[6].split(':')
                    time_val = datetime.strptime(row[6], '%H:%M:%S').time() if len(time_parts) in [2,3] else None
                    
                    is_active = row[7].lower() == 'true'
                    
                    # Convert enums
                    r_type = ReminderType.PCH if r_type_str == 'pch' else ReminderType.HO
                    
                    freq_map = {'daily': ReminderFrequency.DAILY, 'weekly': ReminderFrequency.WEEKLY, 'monthly': ReminderFrequency.MONTHLY}
                    freq = freq_map.get(freq_str, ReminderFrequency.WEEKLY)
                    
                    reminders.append(Reminder(
                        user_id=user_id,
                        member_name=name,
                        type=r_type,
                        frequency=freq,
                        time_of_day=time_val,
                        day_of_week=day_week,
                        day_of_month=day_month,
                        is_active=is_active
                    ))
                except Exception as parse_err:
                    logger.warning(f"Skipping invalid reminder row {i+1}: {parse_err}")
                    continue
            
            logger.info(f"Loaded {len(reminders)} reminders from DB")
            return reminders
            
        except Exception as e:
            logger.error(f"Error loading reminders: {e}")
            return []

    def save_reminders(self, reminders: List[Reminder]):
        """Save all reminders to DB spreadsheet (Overwrite)"""
        if not self.is_db_available(): return
        
        try:
            rows = [['Telegram ID', 'Nome', 'Tipo (HO/PCH)', 'Frequência', 'Dia Semana', 'Dia Mês', 'Hora', 'Ativo?']]
            
            for r in reminders:
                rows.append([
                    str(r.user_id),
                    r.member_name,
                    r.type.value,
                    r.frequency.value,
                    str(r.day_of_week) if r.day_of_week is not None else 'None',
                    str(r.day_of_month) if r.day_of_month is not None else 'None',
                    r.time_of_day.strftime('%H:%M:%S'),
                    str(r.is_active)
                ])
                
            # Clear existing
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.db_spreadsheet_id,
                range='Lembretes!A:H'
            ).execute()
            
            # Write new
            self.service.spreadsheets().values().update(
                spreadsheetId=self.db_spreadsheet_id,
                range='Lembretes!A1',
                valueInputOption='RAW',
                body={'values': rows}
            ).execute()
            
            logger.info("Saved reminders to DB")
            
        except Exception as e:
            logger.error(f"Error saving reminders: {e}")

    def log_member_movement(self, member_name: str, telegram_id: int, role_change: str, movement_type: str = "Cadastro") -> bool:
        """Log a member movement (role change, registration) to Historico sheet"""
        if not self.is_db_available(): return False
        
        try:
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            
            # Check if Historico sheet exists - we assume ensure_db_structure was called
            # but strictly speaking we should just append.
            
            row_data = [
                timestamp,
                member_name,
                str(telegram_id),
                movement_type,
                role_change
            ]
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.db_spreadsheet_id,
                range='Historico!A:E',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            logger.info(f"Logged movement for {member_name}: {movement_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging member movement: {e}")
            return False

    def update_member_registration(self, member_name: str, telegram_id: int, roles: List[str], managed_scopes: List[str] = None, email: str = None, matricula: str = None) -> bool:
        """Update member's registration info (ID, Roles, Managed Scopes, Email, Matricula) in Membros sheet"""
        if not self.is_db_available(): return False
        
        try:
            # First, find the row for this member
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.db_spreadsheet_id,
                range='Membros!A:A'
            ).execute()
            
            rows = result.get('values', [])
            row_index = -1
            
            # Find matching name
            for i, row in enumerate(rows):
                if row and row[0] == member_name:
                    row_index = i + 1
                    break
            
            if row_index == -1:
                # Member not found in list, should we add? 
                # For now, let's append if not found, though usually we expect pre-populated list
                row_index = len(rows) + 1
                logger.info(f"Member {member_name} not found in DB, appending new row {row_index}")
                
                # Write Name
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.db_spreadsheet_id,
                    range=f'Membros!A{row_index}',
                    valueInputOption='RAW',
                    body={'values': [[member_name]]}
                ).execute()

            # Prepare Update Data (Cols B, C, D, E, F)
            # B: Telegram ID
            # C: Roles
            # D: Managed Scopes
            # E: Email
            # F: Matricula
            
            roles_str = ", ".join(roles)
            scopes_str = ", ".join(managed_scopes) if managed_scopes else ""
            email_str = email if email else ""
            matricula_str = matricula if matricula else ""
            
            update_values = [[str(telegram_id), roles_str, scopes_str, email_str, matricula_str]]
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.db_spreadsheet_id,
                range=f'Membros!B{row_index}:F{row_index}',
                valueInputOption='RAW',
                body={'values': update_values}
            ).execute()
            
            logger.info(f"Updated registration for {member_name} at row {row_index}")
            return True

        except Exception as e:
            logger.error(f"Error updating member registration: {e}")
            return False

# Global instance
sheets_manager = SheetsManager()