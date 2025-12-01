import logging
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import json

logger = logging.getLogger(__name__)


class ConfirmationManager:
    """Maneja el flujo de confirmaciones de usuario"""
    
    def __init__(self, db_service, whatsapp_service):
        self.db_service = db_service
        self.whatsapp_service = whatsapp_service
    
    async def send_confirmation_request(self, phone: str, tipo: str, result, formatted_fields: dict):
        """Envía solicitud de confirmación con campos ya formateados"""
        mensaje = self._build_confirmation_message(tipo, formatted_fields)
        
        # Enviar mensaje de confirmación con botones de Sí/No
        buttons = [
            {"id": "confirm_yes", "title": "✅ Sí, confirmar"},
            {"id": "confirm_no", "title": "❌ No, cancelar"}
        ]
        
        await self.whatsapp_service.send_message_with_buttons(phone, mensaje, buttons)
        
        # Guardar estado de confirmación pendiente en el historial
        self._save_pending_confirmation(phone, tipo, result)
        
        logger.info(f"Confirmación enviada a {phone} para {tipo}")
    
    def check_confirmation_status(self, phone: str, current_message: dict, phone_history: list = None) -> Optional[Dict[str, Any]]:
        """
        Verifica si hay confirmación pendiente y detecta respuesta.
        Retorna: None | {"confirmed": bool, "tipo": str, "detalles_parciales": dict}
        """
        pending = self._get_pending_request(phone, phone_history)
        if not pending:
            return None
        
        response = self._detect_user_response(current_message)
        
        if response in ["confirmed", "cancelled"]:
            return {
                "confirmed": response == "confirmed",
                "tipo": pending["tipo_solicitud"],
                "detalles_parciales": pending["detalles_parciales"]
            }
        
        return None
    
    def _get_pending_request(self, phone: str, phone_history: list = None) -> Optional[Dict]:
        """Busca última solicitud de confirmación pendiente (datos completos esperando confirmación)"""
           
        # Buscar el mensaje más reciente de tipo "pending_confirmation"
        # phone_history viene en orden cronológico (más antiguo → más reciente)
        # Iterar en reversa para encontrar el más reciente primero
        for msg in reversed(phone_history):
            if msg.get("type") == "pending_confirmation":
                return msg
        
        return None
    
    def _detect_user_response(self, message: dict) -> Optional[str]:
        """Detecta confirmación/cancelación. Retorna: 'confirmed' | 'cancelled' | None"""
        # Detectar botones
        if message.get("type") == "interactive":
            button_id = message.get("interactive", {}).get("button_reply", {}).get("id")
            if button_id == "confirm_yes":
                return "confirmed"
            elif button_id == "confirm_no":
                return "cancelled"
        
        # Detectar texto
        if message.get("type") == "text":
            text = message.get("text", {}).get("body", "").lower().strip()
            
            # Palabras de confirmación (solo palabras completas)
            confirmacion = ["sí", "si", "yes", "yep", "ok", "okay", "confirmar", "confirm", "adelante", "go"]
            # Verificar si el texto es exactamente una palabra de confirmación o empieza con ella
            if text in confirmacion or any(text.startswith(palabra + " ") for palabra in confirmacion):
                return "confirmed"
            
            # Palabras de cancelación (solo palabras completas)
            cancelacion = ["no", "nope", "cancelar", "cancel", "no gracias", "no thanks", "abortar"]
            # Verificar si el texto es exactamente una palabra de cancelación o empieza con ella
            if text in cancelacion or any(text.startswith(palabra + " ") for palabra in cancelacion):
                return "cancelled"
        
        return None
    
    def _build_confirmation_message(self, tipo: str, formatted_fields: dict) -> str:
        """Construye mensaje de confirmación con campos ya formateados por el handler"""
        tipo_label = tipo.upper().replace("_", " ")
        nombre = formatted_fields.get("nombre", "Sin nombre")
        
        mensaje = f"📋 **CONFIRMAR {tipo_label}**\n\n"
        mensaje += f"**Información a registrar**: {nombre}\n\n**Detalles:**\n"
        
        # Mostrar todos los campos excepto 'nombre' (ya está en el título)
        for key, val in formatted_fields.items():
            if key != "nombre":
                mensaje += f"\n• **{key}**: {val}"
        
        mensaje += "\n\n✅ Presiona un botón para continuar"
        return mensaje
    
    def _save_pending_confirmation(self, phone: str, tipo: str, result):
        """Guarda registro de confirmación pendiente en el historial"""
        # Extraer detalles completos (con todos los campos incluidos None)
        if hasattr(result.detalles, "dict"):
            detalles_dict = result.detalles.dict()
        else:
            detalles_dict = result.detalles if isinstance(result.detalles, dict) else {}
        
        now_argentina = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        timestamp_str = now_argentina.strftime("%Y-%m-%d %H:%M:%S")
        
        pending_data = {
            "type": "pending_confirmation",
            "tipo_solicitud": tipo,
            "detalles_parciales": detalles_dict,
            "timestamp": timestamp_str,
        }
        
        record = {
            "phone": phone,
            "messages": json.dumps(pending_data, ensure_ascii=False),
            "timestamp": timestamp_str,
        }
        
        try:
            self.db_service.insert_record(record, "whatsapp_messages")
            logger.info(f"Confirmación pendiente guardada para {phone}: tipo={tipo}")
        except Exception as e:
            logger.error(f"Error guardando confirmación pendiente: {e}")
    
    def clear_pending_confirmation(self, phone: str):
        """Limpia la confirmación pendiente después de procesar (confirmar o cancelar)"""
        try:
            # Eliminar registros de confirmación pendiente
            self.db_service.delete_records_optimized(phone, "whatsapp_messages")
            logger.info(f"Confirmación pendiente limpiada para {phone}")
        except Exception as e:
            logger.error(f"Error limpiando confirmación pendiente: {e}")
