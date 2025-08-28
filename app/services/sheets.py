# Google Sheets API service
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
import logging
from app.config import settings
logger = logging.getLogger(__name__)

class SheetsService:
    def __init__(self):
        self.credentials_path = settings.GOOGLE_CREDENTIALS_PATH
        self.spreadsheet_id = settings.GOOGLE_SHEETS_ID
        self.client = None
        self.worksheet = None
        #self._authenticate()
    
    #def _authenticate(self):
    #    """Authenticate with Google Sheets API"""
    #    try:
    #        scope = [
    #            "https://spreadsheets.google.com/feeds",
    #            "https://www.googleapis.com/auth/drive"
    #        ]
    #        
    #        creds = Credentials.from_service_account_file(
    #            #self.credentials_path, 
    #            scopes=scope
    #        )
    #        self.client = gspread.authorize(creds)
    #        logger.info("Successfully authenticated with Google Sheets API")
    #    except Exception as e:
    #        logger.error(f"Error authenticating with Google Sheets: {e}")
    #        raise
    
    #def get_worksheet(self, worksheet_name: str = "Sheet1"):
    #    """Get worksheet by name"""
    #    try:
    #        spreadsheet = self.client.open_by_key(self.spreadsheet_id)
    #        self.worksheet = spreadsheet.worksheet(worksheet_name)
    #        return self.worksheet
    #    except Exception as e:
    #        logger.error(f"Error getting worksheet {worksheet_name}: {e}")
    #        raise
#
 #
    #def add_animal(self, animal_data):
    #    """Agregar nuevo animal"""
    #    sheet = self.spreadsheet.worksheet('ANIMALES')
    #    sheet.append_row([
    #        animal_data['nombre'],
    #        animal_data['especie'],
    #        animal_data['fecha_rescate'],
    #        animal_data['estado'],
    #        animal_data['observaciones']
    #    ])
    #
    #def add_event(self, event_data):
    #    """Agregar evento"""
    #    sheet = self.spreadsheet.worksheet('EVENTOS')
    #    sheet.append_row([
    #        event_data['animal_id'],
    #        event_data['tipo_evento'],
    #        event_data['fecha'],
    #        event_data['observaciones']
    #    ])
    #
    #def log_message(self, message_data, analysis_result):
    #    """Log completo: mensaje + análisis de IA"""
    #    sheet = self.spreadsheet.worksheet('MENSAJES_WHATSAPP')
    #    sheet.append_row([
    #        message_data['timestamp'],
    #        message_data['from_number'],
    #        message_data['type'],
    #        message_data['content'],
    #        analysis_result.get('tipo_registro', ''),
    #        analysis_result.get('confianza', 0),
    #        str(analysis_result.get('detalles', {}))
    #    ])
    #