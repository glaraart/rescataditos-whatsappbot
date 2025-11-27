import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, VisitaVetDetails
from app.services.ai import AIService


class VisitaVetHandler(MessageHandler):
    version = "0.1"

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service)
        self.ai = self.ai_service

    async def analyze(self, raw: RawContent) -> HandlerResult:
        try:
            resp_text = await self.ai.run_prompt(
                "visita_vet_prompt.txt", 
                {"text": raw.text or ""}, 
                images=raw.images
            )
            data = json.loads(resp_text)
            detalles = VisitaVetDetails(**data)
        except Exception:
            detalles = None

        hr = HandlerResult()
        hr.detalles = detalles
        hr.confidence = 0.8 if detalles else 0.0
        return hr

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, VisitaVetDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        # no strict required fields for visita (all optional)
        result.campos_faltantes = []
        result.ok = True
        return result

    def to_db_records(self, result: HandlerResult) -> dict:
        """Abstract method - not used in this implementation"""
        pass

    async def save_to_db(self, result: HandlerResult, db_service) -> bool:
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

