import json
import logging
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, GastoDetails
from app.services.ai import AIService
from datetime import datetime

logger = logging.getLogger(__name__)


class GastoHandler(MessageHandler):
    version = "0.1"
    prompt_file = "gasto_prompt.txt"
    details_class = GastoDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

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

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
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
        
        # Subir imágenes a Drive si hay (recibo/comprobante)
        image_url = None
        drive_file_id = None
        if raw and raw.images and self.drive_service:
            try:
                descripcion = datos.descripcion or "gasto"
                # Usar timestamp numérico como ID único
                gasto_id = int(datetime.now().strftime("%Y%m%d%H%M%S"))
                image_url = await self.drive_service.save_image(
                    gasto_id, descripcion, raw.images, "GASTOS"
                )
                # Extraer el file ID de la URL: https://drive.google.com/uc?id={file_id}
                if image_url and "id=" in image_url:
                    drive_file_id = image_url.split("id=")[1]
            except Exception as e:
                logger.error(f"Error subiendo imagen a Drive: {e}")
        
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
                "foto": image_url,  # URL de Drive
                "id_foto": drive_file_id,  # ID del archivo en Drive
            }
            gasto_ok = db_service.insert_record(gasto_record, "gastos")
            return gasto_ok
        except Exception as e:
            logger.error(f"Error guardando gasto: {e}")
            return False
    
    def format_confirmation_fields(self, detalles) -> dict:
        """Formatea campos para mensaje de confirmación"""
        categorias = {
            1: "Veterinaria",
            2: "Alimento",
            3: "Medicamentos",
            4: "Suministros",
            5: "Transporte",
            6: "Otros"
        }
        
        return {
            "nombre": detalles.nombre or "General",
            "Monto": f"${detalles.monto:.2f}",
            "Fecha": detalles.fecha or "No especificada",
            "Categoría": categorias.get(detalles.categoria_id, "No especificada") if detalles.categoria_id else "No especificada",
            "Descripción": detalles.descripcion or "No especificada",
            "Proveedor": detalles.proveedor or "No especificado",
            "Responsable": detalles.responsable or "No especificado",
            "Forma de Pago": detalles.forma_de_pago or "No especificada"
        }
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = GastoDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])
