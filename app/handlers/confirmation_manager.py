import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ConfirmationManager:
    """Maneja el flujo de confirmaciones de usuario"""
    
    def __init__(self, db_service, whatsapp_service):
        self.db_service = db_service
        self.whatsapp_service = whatsapp_service
    
    async def send_confirmation_request(self, phone: str, tipo: str, result):
        """Envía solicitud de confirmación"""
        mensaje = self._build_confirmation_message(tipo, result)
        
        # Enviar mensaje de confirmación (sin botones por ahora)
        await self.whatsapp_service.send_message(phone, mensaje)
        
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
            text = message.get("text", {}).get("body", "").lower()
            
            confirmacion = ["sí", "si", "yes", "yep", "ok", "okay", "confirmar", "confirm", "adelante", "go"]
            if any(palabra in text for palabra in confirmacion):
                return "confirmed"
            
            cancelacion = ["no", "nope", "cancelar", "cancel", "no gracias", "no thanks", "abortar"]
            if any(palabra in text for palabra in cancelacion):
                return "cancelled"
        
        return None
    
    def _build_confirmation_message(self, tipo: str, result) -> str:
        """Construye mensaje de confirmación"""
        tipo_label = tipo.upper().replace("_", " ")
        detalles_dict = self._extract_detalles(result.detalles)
        nombre = detalles_dict.get("nombre", "Sin nombre")
        
        mensaje = f"📋 **CONFIRMAR {tipo_label}**\n\n"
        mensaje += f"**Información a registrar**: {nombre}\n\n**Detalles:**\n"
        
        for key, val in detalles_dict.items():
            if val and key != "nombre":
                mensaje += f"\n• **{key.replace('_', ' ').title()}**: {val}"
        
        mensaje += "\n\n¿Deseas confirmar y guardar este registro?"
        return mensaje
    
    def _extract_detalles(self, detalles) -> dict:
        """Extrae detalles como diccionario"""
        if hasattr(detalles, "dict"):
            return detalles.dict(exclude_none=True)
        return detalles if isinstance(detalles, dict) else {}
    
    def _save_pending_confirmation(self, phone: str, tipo: str, result):
        """Guarda registro de confirmación pendiente en el historial"""
        detalles_dict = self._extract_detalles(result.detalles)
        
        pending_data = {
            "type": "pending_confirmation",
            "tipo_solicitud": tipo,
            "detalles_parciales": detalles_dict,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        record = {
            "phone": phone,
            "messages": json.dumps(pending_data, ensure_ascii=False),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
