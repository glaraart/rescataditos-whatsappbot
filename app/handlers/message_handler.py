# Message handler with composition approach
import logging
import json
import random
import base64
from abc import ABC, abstractmethod
from datetime import datetime
from app.models.analysis import RawContent, HandlerResult
from app.models.whatsapp import  AIAnalysis
from app.services.ai import AIService
from app.config import settings
from app.services.postgres import PostgresService
from app.services.whatsapp import WhatsAppService
from app.services.drive import DriveService

logger = logging.getLogger(__name__)


class MessageHandler(ABC):
    """Base class para handlers de mensajes WhatsApp"""
    
    version: str = "0.1"
    
    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None):
        self.ai_service = ai_service or AIService()
        self.db_service = db_service
        self.whatsapp_service = whatsapp_service
        self.drive_service = None
    
    # ===== ABSTRACT METHODS (cada handler debe implementar) =====
    
    @abstractmethod
    async def analyze(self, raw: RawContent) -> HandlerResult:
        """Run analysis + extraction for this type."""
        pass

    @abstractmethod
    def validate(self, result: HandlerResult) -> HandlerResult:
        """Validate extracted fields, set campos_faltantes."""
        pass

    @abstractmethod
    async def save_to_db(self, result: HandlerResult, db_service) -> bool:
        """Save the result to database. Return True if successful."""
        pass
    
    # ===== SHARED METHODS (heredadas por todos los handlers) =====
    
    async def send_message(self, phone: str, message: str):
        """Enviar mensaje a WhatsApp"""
        if self.whatsapp_service:
            await self.whatsapp_service.send_message(phone, message)

    def delete_records_optimized(self, phone: str, table: str):
        """Eliminar registros de cache"""
        if self.db_service:
            self.db_service.delete_records_optimized(phone, table)

    async def send_completion_confirmation(self, phone: str, tipo: str, result):
        """Enviar confirmación detallada cuando se completa la información"""
        try:
            tipo_label = tipo.upper().replace("_", " ")
            detalles = result.detalles
            
            # Extract nombre from detalles if it exists
            nombre = None
            if hasattr(detalles, "nombre"):
                nombre = detalles.nombre
            
            nombre_display = nombre or "Sin nombre"
            
            mensaje = f"✅ {tipo_label} REGISTRADO EXITOSAMENTE\n"
            mensaje += f"**Información**: {nombre_display}\n"
            
            # Convert Pydantic model to dict for display
            if hasattr(detalles, "dict"):
                detalles_dict = detalles.dict(exclude_none=True)
            else:
                detalles_dict = detalles if isinstance(detalles, dict) else {}
            
            for detalle_key, detalle_val in detalles_dict.items():
                if detalle_val is not None and detalle_key != "nombre":
                    detalle_legible = detalle_key.replace("_", " ").title()
                    mensaje += f"\n• **{detalle_legible}**: {detalle_val}"
            
            await self.send_message(phone, mensaje)
        except Exception as e:
            logger.error(f"Error enviando confirmación: {e}")
            await self.send_message(phone, "✅ Información registrada exitosamente.")

    async def request_missing_fields(self, phone: str, tipo: str, result):
        """Pedir campos faltantes usando directamente la respuesta del handler"""
        try:
            # Crear mensaje estructurado basado en lo que el handler identificó
            tipo_registro = tipo.replace("_", " ").upper()
            header = f"📋 **INFORMACIÓN INCOMPLETA - {tipo_registro}**\n\n"
            header += "🔍 **CAMPOS FALTANTES:**\n\n"
            # Convertir la lista de campos faltantes en un mensaje claro
            missing_sections = []
            for i, campo in enumerate(result.campos_faltantes, 1):
                # Hacer más legible el nombre del campo
                campo_legible = campo.replace("_", " ").title()
                missing_sections.append(f"  {i}. **{campo_legible}**")
            campos_text = "\n".join(missing_sections)
            complete_message = header + campos_text
            await self.send_message(phone, complete_message)
            logger.info(
                f"Solicitados {len(result.campos_faltantes)} campos faltantes para {phone}: {result.campos_faltantes}"
            )
        except Exception as e:
            logger.error(f"Error pidiendo campos faltantes: {e}")
            await self.send_message(
                phone, "📝 Necesito más información para completar el registro. Por favor proporciona más detalles."
            )

    async def send_error_response(self, phone: str, error_msg: str):
        """Envía respuesta de error al usuario"""
        try:
            await self.send_message(
                phone,
                f"❌ Lo siento, hubo un error procesando tu mensaje:\n{error_msg}\n\nPor favor intenta nuevamente.",
            )
        except Exception as e:
            logger.error(f"Error enviando respuesta de error: {e}")

    async def send_confirmation_request(self, phone: str, tipo: str, result):
        """Enviar solicitud de confirmación con botones Sí/No antes de guardar en BD"""
        try:
            tipo_label = tipo.upper().replace("_", " ")
            detalles = result.detalles
            
            # Extraer nombre si existe
            nombre = None
            if hasattr(detalles, "nombre"):
                nombre = detalles.nombre
            
            nombre_display = nombre or "Sin nombre"
            
            # Construir mensaje de confirmación
            mensaje = f"📋 **CONFIRMAR {tipo_label}**\n\n"
            mensaje += f"**Información a registrar**: {nombre_display}\n\n"
            mensaje += "**Detalles:**\n"
            
            # Convertir Pydantic model a dict para display
            if hasattr(detalles, "dict"):
                detalles_dict = detalles.dict(exclude_none=True)
            else:
                detalles_dict = detalles if isinstance(detalles, dict) else {}
            
            for detalle_key, detalle_val in detalles_dict.items():
                if detalle_val is not None and detalle_key != "nombre":
                    detalle_legible = detalle_key.replace("_", " ").title()
                    mensaje += f"\n• **{detalle_legible}**: {detalle_val}"
            
            mensaje += "\n\n¿Deseas confirmar y guardar este registro?"
            
            # Enviar mensaje con botones interactivos
            # WhatsApp usa "reply buttons" o "list items"
            if self.whatsapp_service:
                await self.whatsapp_service.send_message_with_buttons(
                    phone,
                    mensaje,
                    buttons=[
                        {"id": "confirm_yes", "title": "✅ Sí, confirmar"},
                        {"id": "confirm_no", "title": "❌ No, cancelar"},
                    ]
                )
            else:
                # Fallback: enviar sin botones
                await self.send_message(phone, mensaje)
                
            logger.info(f"Solicitud de confirmación enviada a {phone} para {tipo}")
        except Exception as e:
            logger.error(f"Error enviando solicitud de confirmación: {e}")
            await self.send_message(phone, "⚠️ Hubo un error. Por favor intenta de nuevo.")

    def prompt_for_missing(self, missing: list) -> str:
        """Return a user-facing question for missing fields."""
        return "Por favor, proporciona los siguientes campos: " + ", ".join(missing)
    
    async def handle_message_flow(self, phone: str, raw: RawContent, tipo: str):
        """
        Executa el flujo completo de procesamiento: analyze → validate → confirmation/request
        - Si result.ok == True: Enviar solicitud de confirmación con botones
        - Si result.ok == False: Guardar campos faltantes en whatsapp_messages y pedir
        """
        try:
            # Analizar mensaje
            result = await self.analyze(raw)
            result = self.validate(result)
            
            logger.info("Handler result: %s", result)
            
            # VALIDAR SI LOS DATOS ESTÁN COMPLETOS
            if result.ok:
                # Datos completos: solicitar confirmación ANTES de guardar
                await self.send_confirmation_request(phone, tipo, result)
            else:
                # Datos incompletos: guardar campos faltantes en whatsapp_messages
                self._add_incomplete_request_to_context(phone, tipo, result)
                # Pedir campos faltantes
                await self.request_missing_fields(phone, tipo, result)
                
            return result
        except Exception as e:
            logger.error(f"Error en handle_message_flow: {e}")
            await self.send_error_response(phone, str(e))
            raise


class MessageProcessorOrchestrator:
    """Orchestrator para procesar diferentes tipos de mensajes de WhatsApp"""
    def __init__(self):
        self.ai_service = AIService()
        self.db_service = PostgresService()
        self.whatsapp_service = WhatsAppService()
        self.drive_service = DriveService()
        # Map message types to their handler classes
        # Lazy import to avoid circular dependencies
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
        """Procesa mensaje con contexto de conversación inteligente.
        Si hay confirmación pendiente, se ejecuta directamente sin clasificar.
        """
        try:
            phone = message.get("from")
            # Agregar mensaje al contexto de conversación
            self._add_to_conversation(phone, message)
            
            # Construir RawContent directamente desde la conversación
            raw = await self.build_history_conversation(phone)
            logger.info("raw content: %s", raw)
            
            # VERIFICAR SI HAY CONFIRMACIÓN PENDIENTE
            confirmation_status = self._check_pending_confirmation(phone, message)
            
            if confirmation_status and confirmation_status["confirmed"]:
                # El usuario confirmó: ir directo a save_to_db sin clasificar
                logger.info(f"Confirmación detectada para {phone}. Tipo: {confirmation_status['tipo']}")
                
                tipo = confirmation_status["tipo"]
                result = confirmation_status["result"]
                
                # Instanciar handler con servicios compartidos
                handler_cls = self.handlers[tipo]
                handler = handler_cls(
                    ai_service=self.ai_service,
                    db_service=self.db_service,
                    whatsapp_service=self.whatsapp_service
                )
                
                # Guardar directamente en BD (sin pasar por handle_message_flow)
                try:
                    success = await handler.save_to_db(result, self.db_service)
                    if success:
                        await handler.send_completion_confirmation(phone, tipo, result)
                        # Limpiar cache después de procesar
                        self.db_service.delete_records_optimized(phone, "whatsapp_messages")
                    else:
                        await handler.send_error_response(phone, "Error al guardar en la base de datos")
                except Exception as e:
                    logger.error(f"Error al guardar confirmación: {e}")
                    await handler.send_error_response(phone, str(e))
                
                return
            
            elif confirmation_status and not confirmation_status["confirmed"]:
                # El usuario canceló: enviar mensaje de cancelación
                logger.info(f"Cancelación detectada para {phone}")
                await self.whatsapp_service.send_message(
                    phone,
                    "❌ Registro cancelado. ¿Deseas intentar de nuevo o realizar otra solicitud?"
                )
                return
            
            # FLUJO NORMAL: Clasificar y procesar
            # Clasificar
            classification = await self.ai_service.classify(raw)
            tipo = classification.tipo
            
            if not tipo or tipo not in self.handlers:
                logger.warning("No handler found for tipo=%s for phone=%s", tipo, phone)
                await self.whatsapp_service.send_message(
                    phone,
                    "❌ No pude procesar tu solicitud. Intenta de nuevo o contacta a soporte."
                )
                return
            
            # Instanciar handler con servicios compartidos
            handler_cls = self.handlers[tipo]
            handler = handler_cls(
                ai_service=self.ai_service,
                db_service=self.db_service,
                whatsapp_service=self.whatsapp_service
            )
            
            # Delegar al handler el flujo de procesamiento
            await handler.handle_message_flow(phone, raw, tipo)
                
        except Exception as e:
            logger.error(f"Error procesando mensaje completo: {e}")
            phone = message.get("from")
            await self.whatsapp_service.send_message(
                phone,
                f"❌ Lo siento, hubo un error procesando tu mensaje:\n{str(e)}\n\nPor favor intenta nuevamente.",
            )
            raise
    
    # ===== HELPER METHODS (para orchestrator) =====
    
    async def _handle_audio(self, message) -> str:
        """Handler para mensajes de audio - retorna texto transcrito"""
        try:
            audio_data = message["audio"]
            media_url = f"https://graph.facebook.com/v22.0/{audio_data['id']}"
            audio_bytes = await self.whatsapp_service.download_media(media_url)
            text = await self.ai_service.audio_to_text(audio_bytes)
            return text
        except Exception as e:
            logger.error(f"Error procesando mensaje de audio: {e}")
            return ""

    def _check_pending_confirmation(self, phone: str, current_message: dict):
        """
        Revisa si hay una solicitud de confirmación pendiente en el historial.
        Retorna:
        - None: No hay confirmación pendiente
        - {"confirmed": True, "tipo": "...", "result": ...}: Usuario confirmó (presionó Sí)
        - {"confirmed": False, "tipo": "...", "result": ...}: Usuario canceló (presionó No)
        """
        try:
            phone_info = self.db_service.search_phone_in_whatsapp_sheet(phone)
            
            if not phone_info:
                return None
            
            # Buscar la última solicitud incompleta (pending confirmation)
            pending_incomplete_request = None
            
            for msg in phone_info:
                if msg.get("type") == "incomplete_request":
                    # Encontrar la más reciente
                    pending_incomplete_request = msg
            
            if not pending_incomplete_request:
                return None
            
            # Si encontramos un pending_incomplete_request, revisar si el mensaje actual es una confirmación
            # Detectar si el mensaje contiene palabras clave de confirmación
            current_text = ""
            
            if current_message.get("type") == "text":
                current_text = current_message.get("text", {}).get("body", "").lower()
            
            # Palabras clave para confirmación
            confirmacion_palabras = ["sí", "si", "yes", "yep", "ok", "okay", "confirmar", "confirm", "adelante", "go"]
            cancelacion_palabras = ["no", "nope", "cancelar", "cancel", "no gracias", "no thanks", "abortar"]
            
            # También detectar si es respuesta de botón
            is_confirm_button = (
                current_message.get("type") == "interactive" and
                current_message.get("interactive", {}).get("button_reply", {}).get("id") == "confirm_yes"
            )
            
            is_cancel_button = (
                current_message.get("type") == "interactive" and
                current_message.get("interactive", {}).get("button_reply", {}).get("id") == "confirm_no"
            )
            
            confirmed = is_confirm_button or any(palabra in current_text for palabra in confirmacion_palabras)
            cancelled = is_cancel_button or any(palabra in current_text for palabra in cancelacion_palabras)
            
            if not confirmed and not cancelled:
                # No es una respuesta de confirmación/cancelación
                return None
            
            # Reconstruir el result desde pending_incomplete_request
            tipo_solicitud = pending_incomplete_request.get("tipo_solicitud", "")
            detalles_parciales = pending_incomplete_request.get("detalles_parciales", {})
            
            if confirmed:
                logger.info(f"Confirmación detectada para {phone}: {tipo_solicitud}")
                
                # Crear un HandlerResult con los detalles
                # Nota: Necesitamos reconstruir el result correcto
                # Por ahora, retornar información para que el handler lo reconstruya
                return {
                    "confirmed": True,
                    "tipo": tipo_solicitud,
                    "detalles_parciales": detalles_parciales,
                    "result": None  # Placeholder - el handler debe reconstruir esto
                }
            
            elif cancelled:
                logger.info(f"Cancelación detectada para {phone}: {tipo_solicitud}")
                return {
                    "confirmed": False,
                    "tipo": tipo_solicitud,
                    "detalles_parciales": detalles_parciales,
                    "result": None
                }
        
        except Exception as e:
            logger.error(f"Error verificando confirmación pendiente: {e}")
            return None
    
    async def build_history_conversation(self, phone: str):
        """Construye RawContent desde el historial de conversación, incluyendo solicitudes incompletas"""
        try:
            phone_info = self.db_service.search_phone_in_whatsapp_sheet(phone)
            images = []
            context_text = ""
            
            if not phone_info:
                return RawContent(phone=phone, text="", images=[])
            
            for msg in phone_info:
                if msg.get("type") == "text":
                    context_text += msg.get("text", {}).get("body", "")
                elif msg.get("type") == "image":
                    image_data = msg["image"]
                    media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
                    image_bytes = await self.whatsapp_service.download_media(media_url)
                    base64_image = base64.b64encode(image_bytes).decode()
                    images.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    })
                    context_text += msg["image"].get("caption", "")
                elif msg.get("type") == "audio":
                    context_text += await self._handle_audio(msg)
                elif msg.get("type") == "incomplete_request":
                    # Incluir contexto de solicitud incompleta anterior
                    tipo_sol = msg.get("tipo_solicitud", "")
                    campos_falt = msg.get("campos_faltantes", [])
                    detalles_parc = msg.get("detalles_parciales", {})
                    
                    # Agregar al contexto los datos que ya teníamos
                    context_text += f"\n[SOLICITUD ANTERIOR: {tipo_sol} - INCOMPLETA]\n"
                    context_text += f"Datos ya proporcionados: {json.dumps(detalles_parc, ensure_ascii=False)}\n"
                    context_text += f"Campos faltantes anteriormente: {', '.join(campos_falt)}\n"
            
            return RawContent(phone=phone, text=context_text, images=images)
        except Exception as e:
            logger.error(f"Error construyendo historial: {e}")
            return RawContent(phone=phone, text="Error procesando conversación", images=[])
    
    def _add_incomplete_request_to_context(self, phone: str, tipo: str, result: HandlerResult):
        """
        Guarda una solicitud incompleta en whatsapp_messages para mantener contexto.
        Permite que futuros mensajes sepan qué campos faltaban.
        """
        now = datetime.now()
        
        # Construir datos parciales que se extrajeron
        detalles_parciales = {}
        if result.detalles and hasattr(result.detalles, "dict"):
            detalles_parciales = result.detalles.dict(exclude_none=True)
        
        # Mensaje que almacena el estado incompleto
        incomplete_data = {
            "type": "incomplete_request",
            "tipo_solicitud": tipo,
            "detalles_parciales": detalles_parciales,
            "campos_faltantes": result.campos_faltantes,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        phone_info = {
            "phone": phone,
            "messages": json.dumps(incomplete_data, ensure_ascii=False),
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        try:
            self.db_service.insert_record(phone_info, "whatsapp_messages")
            logger.info(
                f"Solicitud incompleta guardada en contexto para {phone}: "
                f"tipo={tipo}, campos_faltantes={result.campos_faltantes}"
            )
        except Exception as e:
            logger.error(f"Error guardando solicitud incompleta en contexto: {e}")
    
    def _add_to_conversation(self, phone: str, message_data: dict):
        """Agregar mensaje al cache de conversación"""
        now = datetime.now()
        phone_info = {
            "phone": phone,
            "messages": json.dumps(message_data, ensure_ascii=False),
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # Insertar/actualizar información previa del teléfono en WHATSAPP
        try:
            self.db_service.insert_record(phone_info, "whatsapp_messages")
        except Exception as e:
            logger.error(f"Error agregando mensaje a la conversación cache: {e}")
