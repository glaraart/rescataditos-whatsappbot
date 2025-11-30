import json
import random
import logging
from datetime import datetime
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, NuevoRescateDetails
from app.services.ai import AIService

logger = logging.getLogger(__name__)


class NuevoRescateHandler(MessageHandler):
    version = "0.1"
    prompt_file = "nuevo_rescate_prompt.txt"
    details_class = NuevoRescateDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, NuevoRescateDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        # Verificar duplicado apenas tengamos el nombre (antes de validar otros campos)
        if result.detalles.nombre and self.db_service:
            existing_id = self.db_service.check_animal_name_exists(result.detalles.nombre)
            if existing_id:
                logger.warning(f"Animal '{result.detalles.nombre}' ya existe con ID={existing_id}")
                # Marcar como inválido para detener el flujo
                result.ok = False
                result.campos_faltantes = ["nombre_duplicado"]
                return result
        
        required_fields = {
            "nombre": result.detalles.nombre,
            "tipo_animal": result.detalles.tipo_animal,
            "edad": result.detalles.edad,
            "color_de_pelo": result.detalles.color_de_pelo,
            "condicion_de_salud_inicial": result.detalles.condicion_de_salud_inicial,
            "ubicacion": result.detalles.ubicacion,
            "cambio_estado": result.detalles.cambio_estado,
        }
        
        missing = [k for k, v in required_fields.items() if v is None or (isinstance(v, (list, str)) and not v)]
        result.campos_faltantes = missing
        result.ok = len(missing) == 0
        
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save nuevo_rescate records to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, NuevoRescateDetails):
            return False
        
        datos = result.detalles
        id = random.randint(10000, 999999999)
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Subir imágenes a Drive si hay
        image_url = None
        drive_file_id = None
        if raw and raw.images and self.drive_service:
            try:
                nombre = datos.nombre
                image_url = await self.drive_service.save_image(
                    str(id), nombre, raw.images, "ANIMALES"
                )
                # Extraer el file ID de la URL: https://drive.google.com/uc?id={file_id}
                if image_url and "id=" in image_url:
                    drive_file_id = image_url.split("id=")[1]
            except Exception as e:
                logger.error(f"Error subiendo imagen a Drive: {e}")
        
        try:
            # Save animales
            animal_record = {
                "id": id,  # Random ID entre 10000 y 999999999
                "nombre": datos.nombre,
                "tipo_animal": datos.tipo_animal,
                "fecha": fecha_actual,
                "ubicacion": datos.ubicacion,
                "edad": datos.edad,
                "color_de_pelo": [{"color": c.color, "porcentaje": c.porcentaje} for c in datos.color_de_pelo] if datos.color_de_pelo else [],
                "condicion_de_salud_inicial": datos.condicion_de_salud_inicial,
                "activo": True,
            }
            animal_ok = db_service.insert_record(animal_record, "animales")
            if not animal_ok:
                return False
            
            # Save eventos
            evento_record = {
                "animal_id": id,
                "ubicacion_id": datos.cambio_estado.ubicacion_id if datos.cambio_estado else None,
                "estado_id": datos.cambio_estado.estado_id if datos.cambio_estado else None,
                "persona": datos.cambio_estado.persona if datos.cambio_estado else None,
                "tipo_relacion_id": datos.cambio_estado.tipo_relacion_id if datos.cambio_estado else None,
                "fecha": fecha_actual,
            }
            evento_ok = db_service.insert_record(evento_record, "eventos")
            
            # Save interaccion si hay foto
            if image_url:
                interaccion_record = {
                    "animal_id": id,
                    "plataforma_id": 6,  # drive
                    "usuario": None,
                    "fecha": fecha_actual,
                    "tipo_interaccion": None,
                    "post_id": drive_file_id ,
                    "contenido": None,
                    "media_url": image_url,
                    "seguimiento_requerido": False,
                }
                db_service.insert_record(interaccion_record, "interaccion")
            
            return evento_ok
        except Exception as e:
            logger.error(f"Error guardando nuevo rescate: {e}")
            return False
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = NuevoRescateDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])
