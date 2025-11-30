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
        from app.handlers.visita_vet import VisitaVetHandler
        from app.handlers.cambio_estado import CambioEstadoHandler
        from app.handlers.consulta import ConsultaHandler
        
        self.handlers = {
            "NUEVO_RESCATE": NuevoRescateHandler,
            "GASTO": GastoHandler,
            "VISITA_VET": VisitaVetHandler,
            "CAMBIO_ESTADO": CambioEstadoHandler,
            "CONSULTA": ConsultaHandler,
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
            tipo = classification.tipo
            
            # Convertir a mayúsculas para coincidir con los handlers
            if tipo:
                tipo = tipo.upper()
            
            # Validar tipo y delegar TODO al handler
            if not tipo or tipo not in self.handlers:
                logger.warning(f"No handler para tipo={tipo}, phone={phone}")
                await self.whatsapp_service.send_message(
                    phone, "❌ No pude procesar tu solicitud."
                )
                return
            
            # El handler se encarga de TODO: confirmación, análisis, validación, guardado
            handler = self._get_handler_instance(tipo)
            await handler.handle_message_flow(phone, raw, tipo, phone_history)

            
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
        record = {
            "phone": phone,
            "messages": json.dumps(message_data, ensure_ascii=False),
            "timestamp": now_argentina.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.db_service.insert_record(record, "whatsapp_messages")
