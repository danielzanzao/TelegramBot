
import os
import logging
from dotenv import load_dotenv
from sheets_integration import sheets_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_database():
    """Verify and setup DB structure"""
    load_dotenv()
    
    if not sheets_manager.is_db_available():
        logger.warning("DB Spreadsheet ID not found in environment.")
        # Try to create if we have service but no ID
        if sheets_manager.service and not sheets_manager.db_spreadsheet_id:
            logger.info("Attempting to create new DB Spreadsheet...")
            new_id = sheets_manager.create_enactus_spreadsheet("EnactusBot DB")
            if new_id:
                logger.info(f"Created NEW DB Spreadsheet: {new_id}")
                logger.info("PLEASE ADD THIS TO YOUR .env FILE: ENACTUS_DB_SPREADSHEET_ID=" + new_id)
                sheets_manager.db_spreadsheet_id = new_id
            else:
                logger.error("Failed to create DB spreadsheet.")
                return
        else:
            return

    logger.info(f"Checking structure for DB: {sheets_manager.db_spreadsheet_id}")
    
    # 1. Ensure basic sheets (Membros, Lembretes)
    sheets_manager.ensure_db_structure()
    
    # 2. Check for 'Historico' sheet
    try:
        metadata = sheets_manager.service.spreadsheets().get(spreadsheetId=sheets_manager.db_spreadsheet_id).execute()
        sheets = metadata.get('sheets', [])
        sheet_titles = [s['properties']['title'] for s in sheets]
        
        if 'Historico' not in sheet_titles:
            logger.info("Creating 'Historico' sheet...")
            
            requests = [{
                'addSheet': {'properties': {'title': 'Historico'}}
            }]
            
            sheets_manager.service.spreadsheets().batchUpdate(
                spreadsheetId=sheets_manager.db_spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            # Setup Header
            headers = [['Data', 'Nome', 'Telegram ID', 'Ação', 'Detalhes']]
            sheets_manager.service.spreadsheets().values().update(
                spreadsheetId=sheets_manager.db_spreadsheet_id,
                range='Historico!A1:E1',
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
            logger.info("Historico sheet created successfully.")
        else:
            logger.info("'Historico' sheet already exists.")
            
    except Exception as e:
        logger.error(f"Error checking/creating Historico: {e}")

if __name__ == "__main__":
    setup_database()
