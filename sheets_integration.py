"""
Google Sheets Integration for EnactusBOT
Handles synchronization of work hour data with Google Sheets
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from data_models import WorkHour

logger = logging.getLogger(__name__)

class SheetsManager:
    """Manages Google Sheets operations for EnactusBOT"""
    
    def __init__(self):
        """Initialize the Sheets Manager"""
        self.service = None
        self.spreadsheet_id = None
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
            spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
            
            # Check if we have the required credentials
            required_vars = [project_id, private_key, client_email]
            if not all(required_vars):
                logger.warning("Google credentials not found - using fragmented credential method")
                logger.info("Required: GOOGLE_PROJECT_ID, GOOGLE_PRIVATE_KEY, GOOGLE_CLIENT_EMAIL")
                return
            
            if not spreadsheet_id:
                logger.warning("Google Sheets Spreadsheet ID not found in environment variables")
                return
            
            # Clean up the private key (remove quotes and fix formatting)
            if private_key:
                # Remove any escaped newlines and ensure proper formatting
                private_key = private_key.replace('\\n', '\n')
                private_key = private_key.strip()
                
                # Ensure proper header/footer
                if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                    private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}\n-----END PRIVATE KEY-----"
                elif not private_key.endswith('-----END PRIVATE KEY-----'):
                    private_key = f"{private_key}\n-----END PRIVATE KEY-----"
            
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
            self.spreadsheet_id = spreadsheet_id
            
            logger.info("Google Sheets service initialized successfully with fragmented credentials")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {str(e)}")
            self.service = None
    
    def is_available(self) -> bool:
        """Check if Google Sheets integration is available"""
        return self.service is not None and self.spreadsheet_id is not None
    
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
        """Sync a single work hour entry to Google Sheets"""
        if not self.is_available():
            logger.warning("Google Sheets not available for sync")
            return False
            
        try:
            # Prepare row data
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            work_date = work_hour.date  # WorkHour uses 'date' field, not 'work_date'
            
            row_data = [
                timestamp,                    # Data/Hora de registro
                work_hour.member_name,        # Membro
                work_hour.task_type,          # Tipo (Projeto/Área)
                work_hour.project_area,       # Projeto/Área específica
                work_hour.description,        # Descrição da atividade
                work_date,                    # Data do trabalho
                str(work_hour.hours),         # Horas trabalhadas
                work_hour.modality,           # Modalidade (Presencial/EAD)
                work_hour.status,             # Status (Pendente/Aprovado/Reprovado)
                work_hour.ho_id or '',        # HO ID único
                str(user_id),                 # ID do usuário Telegram
                work_hour.approved_by or '',  # Aprovado por
                work_hour.approval_date.strftime('%d/%m/%Y %H:%M:%S') if work_hour.approval_date else ''  # Data de aprovação
            ]
            
            # Find next empty row
            next_row = self._get_next_empty_row()
            range_name = f'Registro HO!A{next_row}:M{next_row}'
            
            # Append the data
            if not self.service:
                return False
                
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
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
                
        except HttpError as e:
            logger.error(f"Failed to sync work hour: {str(e)}")
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
                    str(work_hour.hours),
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
                spreadsheetId=self.spreadsheet_id,
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
                spreadsheetId=self.spreadsheet_id,
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
                spreadsheetId=self.spreadsheet_id,
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
        if not self.spreadsheet_id:
            return None
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"


# Global instance
sheets_manager = SheetsManager()