# Google Sheets API service
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from app.config import settings
from datetime import datetime, timedelta
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
        try: 
            timestamp = message_data.get('timestamp')
            dt = datetime.fromtimestamp(int(timestamp))
            formatted_timestamp = dt.strftime('%d/%m/%Y %H:%M:%S')
            sheet = self.get_worksheet('MENSAJES_WHATSAPP')
            sheet.append_row([
                formatted_timestamp,
                message_data.get('from_number'),
                message_data.get('type'),
                message_data.get('content'),
                analysis_result.get('tipo_registro', '')
            ]) 
        except Exception as e:
            logger.error(f"Error updating sheet: {str(e)}")
            return False
        
    async def search_phone_in_whatsapp_sheet(self, phone: str) -> Optional[List[str]]:
        """Buscar registro por teléfono en la hoja WHATSSAP y devolver lista de mensajes recientes (últimos 5 minutos)"""
        try:
            # Obtener la hoja WHATSSAP
            worksheet = self.get_worksheet("WHATSSAP")
            
            # Obtener todos los datos como lista de listas
            all_values = worksheet.get_all_values()
            
            # Crear DataFrame con pandas
            headers = all_values[0]  # Primera fila como headers
            data_rows = all_values[1:]  # Resto como datos
            
            if not data_rows:
                logger.info("No hay datos en la hoja WHATSSAP (solo headers)")
                return None
            
            # Crear DataFrame y limpiar datos
            df = pd.DataFrame(data_rows, columns=headers)
            
            # Limpiar espacios en blanco de los headers
            df.columns = df.columns.str.strip()
                    
            # Buscar coincidencias exactas por teléfono
            exact_matches = df[df['phone'] == phone]
            
            if not exact_matches.empty:
                # Calcular fecha límite (ahora - 5 minutos)
                now = datetime.now()
                five_minutes_ago = now - timedelta(minutes=5)
                # Filtrar por timestamp reciente
                recent_matches = exact_matches[exact_matches['timestamp_dt'] > five_minutes_ago]
                    
                if not recent_matches.empty:
                        # Extraer solo la columna 'messages' y convertir a lista
                        messages = recent_matches['messages'].tolist()
                        
                        # Filtrar mensajes vacíos
                        messages = [msg for msg in messages if msg and str(msg).strip()]
                        
                        logger.info(f"Teléfono {phone} encontrado con {len(messages)} mensajes recientes (últimos 5 min)")
                        return messages
                else:
                        logger.info(f"Teléfono {phone} encontrado pero sin mensajes recientes (últimos 5 min)")
                        return None
                                    
            logger.info(f"Teléfono {phone} no encontrado en la hoja WHATSSAP")
            return None
            
        except Exception as e:
            logger.error(f"Error buscando teléfono {phone} en WHATSSAP: {e}")
            return None
    
    async def delete_records_optimized(self, phone: str, worksheet_name: str) -> bool:
        """Versión optimizada de delete_records"""
        try:
            worksheet = self.get_worksheet(worksheet_name)
            all_values = worksheet.get_all_values()
            
            # Crear DataFrame
            df = pd.DataFrame(all_values[1:], columns=[col.strip() for col in all_values[0]])
                        
            # Filtrar registros
            initial_count = len(df)
            df_filtered = df[df['phone'] != phone]
            deleted_count = initial_count - len(df_filtered)
            
            if deleted_count == 0:
                logger.info(f"No se encontraron registros del teléfono {phone}")
                return True
            
            # Usar batch_update para mejor rendimiento
            headers = all_values[0]
            new_data = [headers] + df_filtered.values.tolist()
            
            # Limpiar y actualizar en una sola operación
            worksheet.clear()
            worksheet.update(new_data)
            
            logger.info(f"Eliminados {deleted_count} registros del teléfono {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando registros: {e}")
            return False