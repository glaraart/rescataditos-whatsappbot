# Google Sheets API service
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any
import logging
from app.config import settings
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
            
            # Usar JSON desde variable de entorno si está disponible
            if settings.GOOGLE_CREDENTIALS_JSON:
                import json

                credentials_dict = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
            else:
                # Usar archivo si no hay JSON en variable de entorno
                creds = Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=scope
                )
            
            client = gspread.authorize(creds)
            logger.info("Successfully authenticated with Google Sheets API")
            return client
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
    
    def update_dashboard(self, dashboard_data: List[Dict[str, Any]]) -> bool:
        """Actualizar la hoja DASHBOARD con los datos del dashboard"""
        try:
            logger.info("Actualizando hoja DASHBOARD...")
            worksheet = self.get_worksheet("DASHBOARD")
            
            # Definir headers esperados (coinciden con el sheet)
            headers = [
                "animal_id", "Nombre", "Estado ID", "Estado",
                "Ubicación", "Fecha Rescate", "Fecha Estado",
                "Contenido", "Post ID"
            ]
            
            # Construir datos para actualizar
            rows_to_update = [headers]  # Primera fila: headers
            
            for record in dashboard_data:
                row = [
                    record.get("animal_id", ""),
                    record.get("Nombre", ""),
                    record.get("Estado ID", ""),
                    record.get("Estado", ""),
                    record.get("Ubicación", ""),
                    str(record.get("Fecha Rescate", "")) if record.get("Fecha Rescate") else "",
                    str(record.get("Fecha Estado", "")) if record.get("Fecha Estado") else "",
                    record.get("Contenido", ""),
                    record.get("Post ID", "")
                ]
                rows_to_update.append(row)
            
            # Limpiar y actualizar en una sola operación
            worksheet.clear()
            worksheet.update(rows_to_update, value_input_option='USER_ENTERED')
            
            logger.info(f"DASHBOARD actualizado: {len(dashboard_data)} registros")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando DASHBOARD: {e}")
            return False