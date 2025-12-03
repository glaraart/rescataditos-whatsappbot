import logging
import json 
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class MessageProcessorOrchestrator:
    """Orchestrator simplificado para procesar mensajes"""
    
    def __init__(self):
        from app.services.ai import AIService
        from app.services.postgres import PostgresService
        from app.services.whatsapp import WhatsAppService
        from app.handlers.confirmation_manager import ConfirmationManager
        from app.handlers.conversation_builder import ConversationBuilder
        
        self.ai_service = AIService()
        self.db_service = PostgresService()
        self.whatsapp_service = WhatsAppService()
        
        # Componentes auxiliares
        self.conversation_builder = ConversationBuilder(
            self.db_service, self.whatsapp_service, self.ai_service
        )
        self.confirmation_manager = ConfirmationManager(
            self.db_service, self.whatsapp_service
        )
        
        self._init_handlers()
    
    def _init_handlers(self):
        """Inicializa handlers disponibles"""
        from app.handlers.nuevo_rescate import NuevoRescateHandler
        from app.handlers.gasto import GastoHandler
        from app.handlers.veterinaria import VeterinariaHandler
        from app.handlers.cambio_estado import CambioEstadoHandler
        from app.handlers.consulta import ConsultaHandler
        from app.handlers.tracking_movimiento import TrackingMovimientoHandler
        
        self.handlers = {
            "NUEVO_RESCATE": NuevoRescateHandler,
            "GASTO": GastoHandler,
            "VETERINARIA": VeterinariaHandler,
            "CAMBIO_ESTADO": CambioEstadoHandler,
            "CONSULTA": ConsultaHandler,
            "TRACKING_MOVIMIENTO": TrackingMovimientoHandler,
        }
    
    async def process_message(self, message):
        """Procesa mensaje con contexto inteligente"""
        phone = message.get("from")
        
        try:
            # Guardar mensaje en caché
            self._add_to_conversation(phone, message)
            
            # Obtener historial una sola vez (optimización)
            phone_history = self.db_service.search_phone_in_whatsapp_sheet(phone)
            
            # Construir raw content para clasificación
            raw = await self.conversation_builder.build_raw_content(phone, phone_history)
            logger.info(f"Raw content: {raw}")
            
            # Clasificar SIEMPRE primero (saber qué tipo de mensaje es)
            classification = await self.ai_service.classify(raw)
            tipos = classification.tipos  # Array de tipos
            
            logger.info(f"Tipos detectados: {tipos}")
            
            # Validar que haya al menos un tipo
            if not tipos or len(tipos) == 0:
                logger.warning(f"No se detectó ningún tipo, phone={phone}")
                logger.warning(f"Raw text: {raw.text[:200]}...")  # Log primeros 200 chars
                await self.whatsapp_service.send_message(
                    phone, 
                    "🤔 No pude identificar qué tipo de información es este mensaje.\n\n"
                    "Por favor intenta ser más específico sobre:\n"
                    "• Rescate de un animal\n"
                    "• Cambio de estado (adopción, tránsito, etc)\n"
                    "• Visita veterinaria\n"
                    "• Gasto realizado\n"
                    "• Salida/regreso de animales"
                )
                return
            
            # Procesar cada tipo detectado en secuencia
            for tipo in tipos:
                tipo_upper = tipo.upper()
                
                if tipo_upper not in self.handlers:
                    logger.warning(f"No handler para tipo={tipo_upper}, phone={phone}")
                    continue
                
                # El handler se encarga de TODO: confirmación, análisis, validación, guardado
                handler = self._get_handler_instance(tipo_upper)
                await handler.handle_message_flow(phone, raw, tipo_upper, phone_history)

            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await self.whatsapp_service.send_message(
                phone, f"❌ Error: {str(e)}\n\nIntenta nuevamente."
            )
    
    def _get_handler_instance(self, tipo: str):
        """Obtiene instancia de handler con servicios inyectados"""
        handler_cls = self.handlers[tipo]
        return handler_cls(
            ai_service=self.ai_service,
            db_service=self.db_service,
            whatsapp_service=self.whatsapp_service,
            confirmation_manager=self.confirmation_manager
        )
    
    def _add_to_conversation(self, phone: str, message_data: dict):
        """Agrega mensaje al caché con hora de Argentina"""
        now_argentina = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        logger.info(f"Fecha: {now_argentina}")
        record = {
            "phone": phone,
            "messages": json.dumps(message_data, ensure_ascii=False),
            "timestamp": now_argentina.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.db_service.insert_record(record, "whatsapp_messages")
