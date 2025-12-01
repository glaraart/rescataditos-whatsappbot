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
        
        # Validar que haya al menos un item
        if not result.detalles.items or len(result.detalles.items) == 0:
            result.ok = False
            result.campos_faltantes = ["items"]
            return result
        
        # Validar que cada item tenga monto, categoria_id y descripcion
        for i, item in enumerate(result.detalles.items):
            if not item.monto or not item.categoria_id or not item.descripcion:
                result.ok = False
                result.campos_faltantes = [f"item_{i}_incompleto"]
                return result
        
        result.ok = True
        result.campos_faltantes = []
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save gasto records to database (one per item) and allocate to animals in gasto_animal."""
        if not isinstance(result.detalles, GastoDetails):
            return False
        
        datos = result.detalles
        
        # Normalize fecha
        fecha = datos.fecha
        if isinstance(fecha, str):
            try:
                # Intentar parsear con hora si viene en formato ISO
                fecha = datetime.fromisoformat(fecha.replace(" ", "T"))
            except Exception:
                try:
                    # Intentar solo fecha
                    fecha = datetime.strptime(fecha, "%Y-%m-%d")
                except Exception:
                    fecha = datetime.now()
        elif not fecha:
            fecha = datetime.now()
        
        # Subir imágenes a Drive si hay (recibo/comprobante)
        image_url = None
        drive_file_id = None
        if raw and raw.images and self.drive_service:
            try:
                # Usar timestamp como descripción para la imagen
                gasto_id = int(datetime.now().strftime("%Y%m%d%H%M%S"))
                proveedor_nombre = datos.proveedor or "gasto"
                image_url = await self.drive_service.save_image(
                    gasto_id, proveedor_nombre, raw.images, "GASTOS"
                )
                # Extraer el file ID de la URL: https://drive.google.com/uc?id={file_id}
                if image_url and "id=" in image_url:
                    drive_file_id = image_url.split("id=")[1]
                logger.info(f"Imagen de gasto subida a Drive: {image_url}")
            except Exception as e:
                logger.error(f"Error subiendo imagen a Drive: {e}")
        
        # Insertar UN registro por cada item
        all_ok = True
        try:
            for item in datos.items:
                gasto_record = {
                    "gasto_id": None,  # Auto-incrementado por PostgreSQL
                    "fecha": fecha,
                    "categoria_id": item.categoria_id,
                    "monto_total": item.monto,
                    "descripcion": item.descripcion,
                    "proveedor": datos.proveedor,
                    "responsable": datos.responsable,
                    "forma_de_pago": datos.forma_de_pago,
                    "foto": image_url,  # URL de Drive (compartida por todos los items del ticket)
                    "id_foto": drive_file_id,  # ID del archivo en Drive
                }
                item_ok = db_service.insert_record(gasto_record, "gastos")
                if not item_ok:
                    logger.error(f"Error guardando item: {item.descripcion}")
                    all_ok = False
                    continue
                
                # Obtener el gasto_id recién insertado
                try:
                    gasto_id = db_service.get_last_inserted_id("gastos", "gasto_id")
                    if not gasto_id:
                        logger.warning(f"No se pudo obtener gasto_id para item: {item.descripcion}")
                        continue
                    
                    # Asignar gasto a animales en gasto_animal
                    await self._allocate_gasto_to_animals(db_service, gasto_id, item)
                    
                except Exception as e:
                    logger.error(f"Error asignando gasto {gasto_id} a animales: {e}")
            
            return all_ok
        except Exception as e:
            logger.error(f"Error guardando gastos: {e}")
            return False
    
    async def _allocate_gasto_to_animals(self, db_service, gasto_id: int, item) -> bool:
        """Allocate expense to specific animal or distribute among active animals."""
        try:
            # CASO 1: Gasto específico para un animal (nombre_animal está presente)
            if item.nombre_animal:
                animal_id = db_service.check_animal_name_exists(item.nombre_animal)
                if not animal_id:
                    logger.warning(f"Animal '{item.nombre_animal}' no encontrado en DB")
                    return False
                
                # Insertar UN registro en gasto_animal para el animal específico
                gasto_animal_record = {
                    "gasto_id": gasto_id,
                    "animal_id": animal_id,
                    "monto": item.monto
                }
                return db_service.insert_record(gasto_animal_record, "gasto_animal")
            
            # CASO 2: Gasto compartido (alimento o piedritas) - distribuir entre animales activos
            elif item.categoria_id in [2, 3]:  # 2=Alimento, 3=Piedritas
                # Obtener animales activos en refugio
                animales_activos = db_service.get_animales_activos_en_refugio()
                if not animales_activos or len(animales_activos) == 0:
                    logger.warning(f"No hay animales activos para distribuir gasto {gasto_id}")
                    return False
                
                # Calcular monto por animal (distribución equitativa)
                monto_por_animal = item.monto / len(animales_activos)
                
                # Insertar un registro en gasto_animal por cada animal
                all_ok = True
                for animal in animales_activos:
                    gasto_animal_record = {
                        "gasto_id": gasto_id,
                        "animal_id": animal["id"],
                        "monto": monto_por_animal
                    }
                    if not db_service.insert_record(gasto_animal_record, "gasto_animal"):
                        logger.error(f"Error asignando gasto a animal {animal['id']}")
                        all_ok = False
                
                return all_ok
            
            # CASO 3: Gasto general (veterinario, transporte, etc.) - NO insertar en gasto_animal
            else:
                logger.info(f"Gasto {gasto_id} es general, no se asigna a animales")
                return True
                
        except Exception as e:
            logger.error(f"Error en _allocate_gasto_to_animals: {e}")
            return False
    
    def format_confirmation_fields(self, detalles) -> dict:
        """Formatea campos para mensaje de confirmación"""
        categorias = {
            1: "Veterinario",
            2: "Alimento",
            3: "Piedritas",
            4: "Limpieza",
            5: "Medicamentos",
            6: "Transporte",
            7: "Otros"
        }
        
        # Calcular monto total de todos los items
        monto_total = sum(item.monto for item in detalles.items)
        
        # Formatear lista de items con nombre de animal si aplica
        items_texto = "\n".join([
            f"  - {item.descripcion}: ${item.monto:.2f} ({categorias.get(item.categoria_id, 'Sin categoría')})"
            + (f" - {item.nombre_animal}" if item.nombre_animal else "")
            for item in detalles.items
        ])
        
        return {
            "nombre": detalles.nombre or "Gasto General",
            "Fecha": detalles.fecha or "No especificada",
            "Proveedor": detalles.proveedor or "No especificado",
            "Responsable": detalles.responsable or "No especificado",
            "Forma de Pago": detalles.forma_de_pago or "No especificada",
            "Items": f"\n{items_texto}",
            "TOTAL": f"${monto_total:.2f}"
        }
    
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        try:
            detalles = GastoDetails(**detalles_parciales)
            result = HandlerResult(detalles=detalles)
            return self.validate(result)
        except Exception as e:
            return HandlerResult(detalles=None, ok=False, campos_faltantes=["Error al reconstruir datos"])
