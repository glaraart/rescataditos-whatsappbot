# Google Sheets API service
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from app.config import settings
import os
logger = logging.getLogger(__name__)

class SheetsService:
    def __init__(self):
        self.credentials_path = settings.GOOGLE_CREDENTIALS_PATH
        self.spreadsheet_id = settings.GOOGLE_SHEETS_ID
        self.client = self._authenticate()
        self.worksheet = None 
        self.spreadsheet = self.client.open_by_key(settings.KEY_SHEET)
    
    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scope
            )
            self.client = gspread.authorize(creds)
            logger.info("Successfully authenticated with Google Sheets API")
        except Exception as e:
            logger.error(f"Error authenticating with Google Sheets: {e}")
            raise

    def get_worksheet(self, worksheet_name: str = "Sheet1"):
        """Get worksheet by name"""
        try: 
            self.worksheet = self.spreadsheet.worksheet(worksheet_name)
            return self.worksheet
        except Exception as e:
            logger.error(f"Error getting worksheet {worksheet_name}: {e}")
            raise
    
    def get_headers(self, worksheet: gspread.worksheet.Worksheet) -> List[str]:
        """Get headers of the worksheet"""
        try:
            return worksheet.row_values(1)
        except Exception as e:
            logger.error(f"Failed to get headers: {str(e)}")
            return []

    def insert_sheet_from_dict(self,data: Dict[str, Any],worksheet_name: str) -> bool:
        """create a row in the worksheet based on dictionary data.
        Args:
            data: Dictionary with data to update or list of dictionaries
            worksheet: The worksheet to update
        Returns:
            True if successful, False otherwise
        """
        worksheet = self.get_worksheet(worksheet_name)
        # Handle list of dictionaries
        if isinstance(data, list):
            success = True
            for item in data:
                if not self.insert_sheet_from_dict(item, worksheet):
                    success = False
            return success
        
        try:
            headers = self.get_headers(worksheet)
            logger.info(f"Creating new entry for {data}")
                
                # Create a list with values in the correct order
            new_row = []
            for header in headers: 
                new_row.append(data.get(header, ""))
                
                # Append the new row
            worksheet.append_row(new_row)
            print("insertado ")
            return True
            
        except Exception as e:
            logger.error(f"Error updating sheet: {str(e)}")
            return False
    
    def log_message_with_analysis(self, message_data, analysis_result):
        """Log completo: mensaje + análisis de IA"""
        # Convertir timestamp Unix a formato legible
        timestamp = message_data.get('timestamp')
        dt = datetime.fromtimestamp(int(timestamp))
        formatted_timestamp = dt.strftime('%d/%m/%Y %H:%M:%S')
        sheet = self.get_worksheet('MENSAJES_WHATSAPP')
        sheet.append_row([
            formatted_timestamp,
            message_data.get('from_number'),
            message_data.get('type'),
            message_data.get('content'),
            analysis_result.get('tipo_registro', ''),
            str(analysis_result.get('detalles', {}))
        ])
    