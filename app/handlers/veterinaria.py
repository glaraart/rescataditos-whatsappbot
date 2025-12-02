import json
import logging
from datetime import datetime
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, VeterinariaDetails
from app.services.ai import AIService

logger = logging.getLogger(__name__)


class VeterinariaHandler(MessageHandler):
    version = "0.1"
    prompt_file = "veterinaria_prompt.txt"
    details_class = VeterinariaDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        if not isinstance(result.detalles, VeterinariaDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        datos = result.detalles
        
        # Validar que si hay items, tengan los campos necesarios
        if datos.items:
            for item in datos.items:
                if not item.monto or not item.categoria_id or not item.descripcion:
                    result.ok = False
                    result.campos_faltantes.append("item_incompleto")
                    return result
        
        # No hay campos estrictamente requeridos, pero debe tener al menos algo
        result.campos_faltantes = []
        result.ok = True
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save veterinaria record + gastos (if any) to database."""
        if not isinstance(result.detalles, VeterinariaDetails):
            return False
        
        datos = result.detalles
        
        # Normalize fecha
        fecha = datos.fecha
        if isinstance(fecha, str):
            try:
                fecha = datetime.fromisoformat(fecha.replace(" ", "T"))
            except Exception:
                try:
                    fecha = datetime.strptime(fecha, "%Y-%m-%d")
                except Exception:
                    fecha = datetime.now()
        elif not fecha:
            fecha = datetime.now()
        
        # Buscar animal_id por nombre
        animal_id = None
        if datos.nombre:
            animal_id = db_service.check_animal_name_exists(datos.nombre)
            if not animal_id:
                logger.warning(f"Animal '{datos.nombre}' no encontrado en DB")
        
        # 1. Guardar visita veterinaria
        try:
            visita_record = {
                "animal_id": animal_id,
                "veterinario": datos.veterinario,
                "fecha": fecha,
                "diagnostico": datos.diagnostico,
                "tratamiento": datos.tratamiento,
                "proxima_cita": datos.proxima_cita,
                "persona_acompanante": datos.persona_acompanante,
            }
            visita_ok = db_service.insert_record(visita_record, "visita_veterinario")
            if not visita_ok:
                logger.error("Error guardando visita veterinaria")
        except Exception as e:
            logger.error(f"Error guardando visita veterinaria: {e}")
            visita_ok = False
        
        # 2. Guardar gastos veterinarios si existen
        gastos_ok = True
        if datos.items and len(datos.items) > 0:
            # Subir imágenes a Drive si hay (recibo/factura)
            image_url = None
            drive_file_id = None
            if raw and raw.images and self.drive_service:
                try:
                    gasto_id = int(datetime.now().strftime("%Y%m%d%H%M%S"))
                    proveedor_nombre = datos.proveedor or "veterinaria"
                    image_url = await self.drive_service.save_image(
                        gasto_id, proveedor_nombre, raw.images, "GASTOS"
                    )
                    if image_url and "id=" in image_url:
                        drive_file_id = image_url.split("id=")[1]
                    logger.info(f"Imagen de factura veterinaria subida a Drive: {image_url}")
                except Exception as e:
                    logger.error(f"Error subiendo imagen a Drive: {e}")
            
            # Insertar UN registro en gastos por cada item
            for item in datos.items:
                try:
                    gasto_record = {
                        "gasto_id": None,
                        "fecha": fecha,
                        "categoria_id": 1,  # Siempre categoría 1 (Veterinario)
                        "monto_total": item.monto,
                        "descripcion": item.descripcion,
                        "proveedor": datos.proveedor,
                        "responsable": datos.responsable,
                        "forma_de_pago": datos.forma_de_pago,
                        "foto": image_url,
                        "id_foto": drive_file_id,
                    }
                    item_ok = db_service.insert_record(gasto_record, "gastos")
                    
                    if item_ok:
                        # Obtener gasto_id y asignar a animal en gasto_animal
                        gasto_id = db_service.get_last_inserted_id("gastos", "gasto_id")
                        if gasto_id and item.nombre_animal:
                            # Buscar animal por nombre
                            animal_id_gasto = db_service.check_animal_name_exists(item.nombre_animal)
                            if animal_id_gasto:
                                gasto_animal_record = {
                                    "gasto_id": gasto_id,
                                    "animal_id": animal_id_gasto,
                                    "monto": item.monto
                                }
                                db_service.insert_record(gasto_animal_record, "gasto_animal")
                    else:
                        logger.error(f"Error guardando gasto veterinario: {item.descripcion}")
                        gastos_ok = False
                        
                except Exception as e:
                    logger.error(f"Error procesando gasto veterinario: {e}")
                    gastos_ok = False
        
        # Retorna True si al menos la visita se guardó correctamente
        return visita_ok
    
    def format_confirmation_fields(self, detalles) -> dict:
        """Formatea campos para mensaje de confirmación"""
        fields = {
            "nombre": detalles.nombre or "No especificado",
            "Veterinario": detalles.veterinario or "No especificado",
            "Fecha": detalles.fecha or "No especificada",
            "Diagnóstico": detalles.diagnostico or "No especificado",
            "Tratamiento": detalles.tratamiento or "No especificado",
            "Próxima Cita": detalles.proxima_cita or "No especificada",
            "Persona Acompañante": detalles.persona_acompanante or "No especificada"
        }
        
        # Agregar información de gastos si existen
        if detalles.items and len(detalles.items) > 0:
            monto_total = sum(item.monto for item in detalles.items)
            items_texto = "\n".join([
                f"  - {item.descripcion}: ${item.monto:.2f}"
                + (f" ({item.nombre_animal})" if item.nombre_animal else "")
                for item in detalles.items
            ])
            fields["Proveedor"] = detalles.proveedor or "No especificado"
            fields["Responsable"] = detalles.responsable or "No especificado"
            fields["Forma de Pago"] = detalles.forma_de_pago or "No especificada"
            fields["Gastos"] = f"\n{items_texto}"
            fields["TOTAL"] = f"${monto_total:.2f}"
        
        return fields
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = VeterinariaDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            logger.error(f"Error reconstruyendo resultado: {e}")
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])
