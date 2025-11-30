import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, CambioEstadoDetails
from app.services.ai import AIService


class CambioEstadoHandler(MessageHandler):
    version = "0.1"
    prompt_file = "cambio_estado_prompt.txt"
    details_class = CambioEstadoDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, CambioEstadoDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        required_fields = {
            "ubicacion_id": result.detalles.ubicacion_id,
            "estado_id": result.detalles.estado_id,
        }
        
        missing = [k for k, v in required_fields.items() if v is None]
        result.campos_faltantes = missing
        result.ok = len(missing) == 0
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save evento record to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, CambioEstadoDetails):
            return False
        
        datos = result.detalles
        
        try:
            evento_record = {
                "ubicacion_id": datos.ubicacion_id,
                "estado_id": datos.estado_id,
                "persona": datos.persona,
                "tipo_relacion_id": datos.tipo_relacion_id,
                "fecha": None,
            }
            evento_ok = db_service.insert_record(evento_record, "eventos")
            return evento_ok
        except Exception:
            return False
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = CambioEstadoDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])

