import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, CambioEstadoDetails
from app.services.ai import AIService


class CambioEstadoHandler(MessageHandler):
    version = "0.1"

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service)
        self.ai = self.ai_service

    async def analyze(self, raw: RawContent) -> HandlerResult:
        try:
            resp_text = await self.ai.run_prompt(
                "cambio_estado_prompt.txt", 
                {"text": raw.text or ""}, 
                images=raw.images
            )
            data = json.loads(resp_text)
            detalles = CambioEstadoDetails(**data)
        except Exception:
            detalles = None

        hr = HandlerResult()
        hr.detalles = detalles
        hr.confidence = 0.85 if detalles else 0.0
        return hr

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

    def to_db_records(self, result: HandlerResult) -> dict:
        """Abstract method - not used in this implementation"""
        pass

    async def save_to_db(self, result: HandlerResult, db_service) -> bool:
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

