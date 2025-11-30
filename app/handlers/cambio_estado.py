import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, CambioEstadoDetails
from app.services.ai import AIService

logger = logging.getLogger(__name__)


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
        
        # Validar campos requeridos del análisis IA
        required_fields = {
            "nombre": result.detalles.nombre,
            "estado_id": result.detalles.estado_id,
        }
        
        missing = [k for k, v in required_fields.items() if v is None]
        
        # Si falta el nombre, no podemos buscar el animal
        if missing:
            result.campos_faltantes = missing
            result.ok = False
            return result
        
        # Buscar animal_id por nombre en la base de datos
        try:
            animal_id = self.db_service.get_animal_by_name(result.detalles.nombre)
            if not animal_id:
                result.campos_faltantes = [f"animal_no_encontrado: {result.detalles.nombre}"]
                result.ok = False
                logger.warning(f"Animal no encontrado: {result.detalles.nombre}")
                return result
            
            # Asignar animal_id al resultado
            result.detalles.animal_id = animal_id
            logger.info(f"Animal encontrado: {result.detalles.nombre} -> ID {result.detalles.animal_id}")
            
        except Exception as e:
            logger.error(f"Error buscando animal: {e}")
            result.campos_faltantes = ["error_busqueda_animal"]
            result.ok = False
            return result
        
        result.ok = True
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save evento record to database. Only called when result.ok == True."""
        # Validation of result.ok is done in handle_message_flow()
        if not isinstance(result.detalles, CambioEstadoDetails):
            return False
        
        datos = result.detalles
        
        # Asignar fecha actual de Buenos Aires
        now_argentina = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        fecha_str = now_argentina.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            evento_record = {
                "animal_id": datos.animal_id,
                "ubicacion_id": datos.ubicacion_id,
                "estado_id": datos.estado_id,
                "persona": datos.persona,
                "tipo_relacion_id": datos.tipo_relacion_id,
                "fecha": fecha_str,
            }
            evento_ok = db_service.insert_record(evento_record, "eventos")
            return evento_ok
        except Exception:
            return False
    
    def format_confirmation_fields(self, detalles) -> dict:
        """Formatea campos para mensaje de confirmación con descripciones legibles"""
        ubicaciones = {1: "Refugio", 2: "Tránsito", 3: "Veterinaria", 4: "Hogar adoptante"}
        estados = {1: "Perdido", 2: "En Tratamiento", 3: "En Adopción", 5: "Adoptado", 6: "Fallecido"}
        relaciones = {1: "Adoptante", 2: "Transitante", 3: "Veterinario", 4: "Voluntario", 5: "Interesado"}
        
        return {
            "nombre": detalles.nombre,
            "Ubicación": ubicaciones.get(detalles.ubicacion_id, str(detalles.ubicacion_id)),
            "Estado": estados.get(detalles.estado_id, str(detalles.estado_id)),
            "Persona": detalles.persona or "No especificado",
            "Tipo de Relación": relaciones.get(detalles.tipo_relacion_id, str(detalles.tipo_relacion_id))
        }
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = CambioEstadoDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])

