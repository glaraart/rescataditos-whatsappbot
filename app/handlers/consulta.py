import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, ConsultaDetails
from app.services.ai import AIService


class ConsultaHandler(MessageHandler):
    version = "0.1"
    prompt_file = "consulta_prompt.txt"
    details_class = ConsultaDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, ConsultaDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        required_fields = {
            "tema": result.detalles.tema,
        }
        
        missing = [k for k, v in required_fields.items() if v is None or (isinstance(v, str) and not v)]
        result.campos_faltantes = missing
        result.ok = len(missing) == 0
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save consulta record to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, ConsultaDetails):
            return False
        
        datos = result.detalles
        
        try:
            consulta_record = {
                "tema": datos.tema,
                "respuesta_sugerida": datos.respuesta_sugerida,
                "nombre": datos.nombre,
            }
            consulta_ok = db_service.insert_record(consulta_record, "consultas")
            return consulta_ok
        except Exception:
            return False
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = ConsultaDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])

