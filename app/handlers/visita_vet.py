import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, VisitaVetDetails
from app.services.ai import AIService


class VisitaVetHandler(MessageHandler):
    version = "0.1"
    prompt_file = "visita_vet_prompt.txt"
    details_class = VisitaVetDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, VisitaVetDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        # no strict required fields for visita (all optional)
        result.campos_faltantes = []
        result.ok = True
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save visita_veterinario record to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, VisitaVetDetails):
            return False
        
        datos = result.detalles
        
        try:
            visita_record = {
                "veterinario": datos.veterinario,
                "fecha": datos.fecha,
                "diagnostico": datos.diagnostico,
                "tratamiento": datos.tratamiento,
                "proxima_cita": datos.proxima_cita,
                "persona_acompanante": datos.persona_acompanante,
            }
            visita_ok = db_service.insert_record(visita_record, "visita_veterinario")
            return visita_ok
        except Exception:
            return False
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = VisitaVetDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])

