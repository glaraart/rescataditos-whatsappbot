import json
import logging
from datetime import datetime
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, TrackingMovimientoDetails
from app.services.ai import AIService

logger = logging.getLogger(__name__)


class TrackingMovimientoHandler(MessageHandler):
    version = "0.1"
    prompt_file = "tracking_movimiento_prompt.txt"
    details_class = TrackingMovimientoDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)

    def validate(self, result: HandlerResult) -> HandlerResult:
        """Validate tracking_movimiento data."""
        if not isinstance(result.detalles, TrackingMovimientoDetails):
            result.ok = False
            result.campos_faltantes = ["detalles_invalidos"]
            return result
        
        datos = result.detalles
        
        # Validar campos obligatorios
        if not datos.tipo or datos.tipo not in ['salida', 'regreso']:
            result.campos_faltantes.append("tipo")
        
        if not datos.destino or datos.destino not in ['parque', 'veterinaria', 'compras', 'entrega_adopcion']:
            result.campos_faltantes.append("destino")
        
        if not datos.animales or len(datos.animales) == 0:
            result.campos_faltantes.append("animales")
        
        result.ok = len(result.campos_faltantes) == 0
        return result

    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save tracking_movimiento record to database."""
        if not isinstance(result.detalles, TrackingMovimientoDetails):
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
        
        # Buscar animal_ids por nombres
        animal_ids = []
        for nombre in datos.animales:
            if nombre.lower() == "todos":
                # Si dice "todos", obtener todos los animales activos
                all_animals = db_service.get_all_active_animals()
                animal_ids = [a['id'] for a in all_animals]
                break
            else:
                # Buscar por nombre (retorna int o None)
                animal_id = db_service.get_animal_by_name(nombre)
                if animal_id:
                    animal_ids.append(animal_id)
                else:
                    logger.warning(f"Animal no encontrado: {nombre}")
        
        if not animal_ids:
            logger.error("No se encontraron animales válidos")
            return False
        
        # INSERT tracking_movimiento
        tracking_id = db_service.insert_tracking_movimiento({
            'tipo': datos.tipo,
            'destino': datos.destino,
            'responsable': datos.responsable,
            'fecha': fecha,
            'observaciones': datos.observaciones
        })
        
        if not tracking_id:
            logger.error("Error insertando tracking_movimiento")
            return False
        
        # INSERT tracking_movimiento_animales (relación N:N)
        for animal_id in animal_ids:
            db_service.insert_tracking_movimiento_animal({
                'tracking_id': tracking_id,
                'animal_id': animal_id
            })
        
        logger.info(f"✅ Tracking guardado: {datos.tipo} {datos.destino} con {len(animal_ids)} animales")
        return True

    def format_confirmation_fields(self, result: HandlerResult) -> dict:
        """Format data for confirmation message."""
        if not isinstance(result.detalles, TrackingMovimientoDetails):
            return {}
        
        datos = result.detalles
        
        # Emoji según tipo
        emoji = "🚶" if datos.tipo == "salida" else "🏠"
        
        # Destino legible
        destino_map = {
            'parque': '🌳 Parque Centenario',
            'veterinaria': '🏥 Veterinaria',
            'compras': '🛒 Compras',
            'entrega_adopcion': '🎉 Entrega en Adopción'
        }
        destino_texto = destino_map.get(datos.destino, datos.destino)
        
        # Animales
        animales_texto = ", ".join(datos.animales) if datos.animales else "No especificado"
        
        fields = {
            f"{emoji} Tipo": datos.tipo.upper(),
            "🎯 Destino": destino_texto,
            "🐾 Animales": animales_texto
        }
        
        if datos.responsable:
            fields["👤 Responsable"] = datos.responsable
        
        if datos.fecha:
            fields["📅 Fecha"] = datos.fecha
        
        if datos.observaciones:
            fields["📝 Observaciones"] = datos.observaciones
        
        return fields
