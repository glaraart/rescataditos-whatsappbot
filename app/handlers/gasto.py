import json
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, GastoDetails
from app.services.ai import AIService
from datetime import datetime


class GastoHandler(MessageHandler):
    version = "0.1"

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service)
        self.ai = self.ai_service

    async def analyze(self, raw: RawContent) -> HandlerResult:
        # Prompt tailored for gastos with multimodal support
        try:
            resp_text = await self.ai.run_prompt(
                "gasto_prompt.txt", 
                {"text": raw.text or ""}, 
                images=raw.images
            )
            data = json.loads(resp_text)
            detalles = GastoDetails(**data)
        except Exception:
            detalles = None

        hr = HandlerResult()
        hr.detalles = detalles
        hr.confidence = 0.9 if detalles else 0.0
        return hr

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, GastoDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        required_fields = {
            "monto": result.detalles.monto,
        }
        
        missing = [k for k, v in required_fields.items() if v is None]
        result.campos_faltantes = missing
        result.ok = len(missing) == 0
        return result

    def to_db_records(self, result: HandlerResult) -> dict:
        """Abstract method - not used in this implementation"""
        pass

    async def save_to_db(self, result: HandlerResult, db_service) -> bool:
        """Save gasto record to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, GastoDetails):
            return False
        
        datos = result.detalles
        
        # Normalize fecha
        fecha = datos.fecha
        if isinstance(fecha, str):
            try:
                fecha = datetime.fromisoformat(fecha)
            except Exception:
                fecha = datetime.now()
        elif not fecha:
            fecha = datetime.now()
        
        try:
            gasto_record = {
                "gasto_id": None,
                "fecha": fecha,
                "categoria_id": datos.categoria_id,
                "monto_total": datos.monto,
                "descripcion": datos.descripcion,
                "proveedor": datos.proveedor,
                "responsable": datos.responsable,
                "forma_de_pago": datos.forma_de_pago,
                "foto": None,
                "id_foto": None,
            }
            gasto_ok = db_service.insert_record(gasto_record, "gastos")
            return gasto_ok
        except Exception:
            return False
