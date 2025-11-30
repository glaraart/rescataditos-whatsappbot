# Message handler with composition approach
import logging
import json
from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.analysis import RawContent, HandlerResult
from app.services.ai import AIService

logger = logging.getLogger(__name__)


class MessageHandler(ABC):
    """Base class para handlers de mensajes WhatsApp"""
    
    version: str = "0.1"
    prompt_file: str = None  # Cada handler define su prompt
    details_class: type = None  # Cada handler define su clase de detalles
    
    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        self.ai_service = ai_service or AIService()
        self.db_service = db_service
        self.whatsapp_service = whatsapp_service
        self.confirmation_manager = confirmation_manager
        self.drive_service = None
    
    # ===== ABSTRACT METHODS (cada handler debe implementar) =====
    
    async def analyze(self, raw: RawContent) -> HandlerResult:
        """Análisis genérico usando IA con el prompt específico del handler"""
        resp_text = None
        try:
            logger.info(f"Iniciando análisis con prompt: {self.prompt_file}, texto: {raw.text}")
            resp_text = await self.ai_service.run_prompt(
                self.prompt_file,
                {"text": raw.text or ""},
                images=raw.images
            )
            logger.info(f"Respuesta AI raw: {resp_text[:500]}")  # Primeros 500 caracteres
            data = json.loads(resp_text)
            logger.info(f"JSON parseado: {data}")
            detalles = self.details_class(**data)
            logger.info(f"Detalles creados exitosamente")
        except Exception as e:
            logger.error(f"Error en análisis AI: {type(e).__name__}: {e}")
            if resp_text:
                logger.error(f"Respuesta AI que causó error: {resp_text[:1000]}")
            else:
                logger.error(f"No se obtuvo respuesta del AI")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            detalles = None
        
        return HandlerResult(detalles=detalles)

    @abstractmethod
    def validate(self, result: HandlerResult) -> HandlerResult:
        """Validate extracted fields, set campos_faltantes."""
        pass

    @abstractmethod
    async def save_to_db(self, result: HandlerResult, db_service, raw: RawContent = None) -> bool:
        """Save the result to database. Return True if successful."""
        pass
    
    @abstractmethod
    def reconstruct_result(self, detalles_parciales: dict) -> HandlerResult:
        """Reconstruye HandlerResult desde confirmación pendiente"""
        pass
    
    # ===== SHARED METHODS (heredadas por todos los handlers) =====
    
    async def _handle_confirmation_response(self, phone: str, status: dict, tipo: str, phone_history: list):
        """Maneja respuesta de confirmación (sí/no)"""
        if status["confirmed"]:
            # Usuario confirmó: guardar en BD
            result = self.reconstruct_result(status["detalles_parciales"])
            
            # Obtener raw content para imágenes desde phone_history
            raw = self._get_raw_from_history(phone_history)
            
            success = await self.save_to_db(result, self.db_service, raw)
            
            if success:
                # Actualizar dashboard si es nuevo_rescate o cambio_estado
                if tipo in ["NUEVO_RESCATE", "CAMBIO_ESTADO"]:
                    self._update_dashboard()
                
                await self.send_completion_confirmation(phone, tipo, result)
                self.confirmation_manager.clear_pending_confirmation(phone)
            else:
                await self.send_error_response(phone, "Error al guardar")
        else:
            # Usuario canceló
            await self.send_message(phone, "❌ Registro cancelado. ¿Deseas intentar de nuevo?")
            self.confirmation_manager.clear_pending_confirmation(phone)
    
    def _get_raw_from_history(self, phone_history: list) -> RawContent:
        """Reconstruye RawContent básico desde historial (para recuperar imágenes)"""
        # Buscar mensajes con imágenes
        images = []
        for msg in phone_history:
            if msg.get("type") == "image" and msg.get("image"):
                image_data = msg["image"]
                images.append({
                    "id": image_data.get("id"),
                    "url": image_data.get("url"),
                    "caption": image_data.get("caption", "")
                })
        
        return RawContent(phone="", text="", images=images)
    
    def _update_dashboard(self):
        """Actualizar la hoja DASHBOARD con los datos actualizados"""
        try:
            from app.services.sheets import SheetsService
            
            # Obtener datos del dashboard desde Postgres
            dashboard_data = self.db_service.get_dashboard_data()
            
            if dashboard_data:
                # Actualizar Google Sheets
                sheets_service = SheetsService()
                sheets_service.update_dashboard(dashboard_data)
                logger.info("Dashboard actualizado exitosamente")
        except Exception as e:
            logger.error(f"Error actualizando dashboard: {e}")
    
    def _save_incomplete_request(self, phone: str, tipo: str, result):
        """Guarda solicitud incompleta en caché"""
               
        detalles = result.detalles.dict(exclude_none=True) if hasattr(result.detalles, "dict") else {}
        
        now_argentina = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        timestamp_str = now_argentina.strftime("%Y-%m-%d %H:%M:%S")
        
        data = {
            "type": "incomplete_request",
            "tipo_solicitud": tipo,
            "detalles_parciales": detalles,
            "campos_faltantes": result.campos_faltantes,
            "timestamp": timestamp_str,
        }
        
        record = {
            "phone": phone,
            "messages": json.dumps(data, ensure_ascii=False),
            "timestamp": timestamp_str,
        }
        
        self.db_service.insert_record(record, "whatsapp_messages")

    async def send_message(self, phone: str, message: str):
        """Enviar mensaje a WhatsApp"""
        if self.whatsapp_service:
            await self.whatsapp_service.send_message(phone, message)

    def delete_records_optimized(self, phone: str, table: str):
        """Eliminar registros de cache"""
        if self.db_service:
            self.db_service.delete_records_optimized(phone, table)
    
    def _format_detalles(self, detalles, exclude_nombre=False) -> str:
        """Formatea detalles para mostrar"""
        detalles_dict = self._extract_detalles(detalles)
        
        lines = []
        for key, val in detalles_dict.items():
            if val and (not exclude_nombre or key != "nombre"):
                key_formatted = key.replace("_", " ").title()
                lines.append(f"• **{key_formatted}**: {val}")
        
        return "\n".join(lines)
    
    def _extract_detalles(self, detalles) -> dict:
        """Convierte detalles a dict"""
        if hasattr(detalles, "dict"):
            return detalles.dict(exclude_none=True)
        return detalles if isinstance(detalles, dict) else {}

    async def send_completion_confirmation(self, phone: str, tipo: str, result):
        """Enviar confirmación detallada cuando se completa la información"""
        try:
            tipo_label = tipo.upper().replace("_", " ")
            detalles_dict = self._extract_detalles(result.detalles)
            nombre = detalles_dict.get("nombre", "Sin nombre")
            
            mensaje = f"✅ {tipo_label} REGISTRADO EXITOSAMENTE\n"
            mensaje += f"**Información**: {nombre}\n\n"
            mensaje += self._format_detalles(result.detalles, exclude_nombre=True)
            
            await self.send_message(phone, mensaje)
        except Exception as e:
            logger.error(f"Error enviando confirmación: {e}")
            await self.send_message(phone, "✅ Información registrada exitosamente.")

    async def request_missing_fields(self, phone: str, tipo: str, result):
        """Pedir campos faltantes usando directamente la respuesta del handler"""
        try:
            tipo_label = tipo.replace("_", " ").upper()
            
            mensaje = f"📋 **INFORMACIÓN INCOMPLETA - {tipo_label}**\n\n"
            mensaje += "🔍 **CAMPOS FALTANTES:**\n\n"
            
            for i, campo in enumerate(result.campos_faltantes, 1):
                campo_legible = campo.replace("_", " ").title()
                mensaje += f"  {i}. **{campo_legible}**\n"
            
            await self.send_message(phone, mensaje)
            logger.info(f"Solicitados {len(result.campos_faltantes)} campos a {phone}")
        except Exception as e:
            logger.error(f"Error pidiendo campos faltantes: {e}")
            await self.send_message(phone, "📝 Necesito más información para completar el registro.")

    async def send_error_response(self, phone: str, error_msg: str):
        """Envía respuesta de error al usuario"""
        mensaje = f"❌ Lo siento, hubo un error:\n{error_msg}\n\nIntenta nuevamente."
        await self.send_message(phone, mensaje)

    async def handle_message_flow(self, phone: str, raw: RawContent, tipo: str, phone_history: list):
        """Flujo completo: verificar confirmación → analyze → validate → save/request"""
        try:
            # Primero verificar si es respuesta a confirmación
            last_message = phone_history[-1] if phone_history else {}
            
            confirmation_status = self.confirmation_manager.check_confirmation_status(phone, last_message, phone_history)
            if confirmation_status:
                await self._handle_confirmation_response(phone, confirmation_status, tipo, phone_history)
                return
            
            # Flujo normal: analizar y validar
            result = await self.analyze(raw)
            logger.info(f"Resultado de IA {result}")
            result = self.validate(result)
            
            logger.info(f"Handler result: {result}")
            
            # Verificar si hay nombre duplicado (caso especial)
            if not result.ok and "nombre_duplicado" in result.campos_faltantes:
                nombre = result.detalles.nombre if result.detalles else "desconocido"
                await self.send_message(
                    phone,
                    f"⚠️ El animal '{nombre}' ya existe en el sistema.\n\n"
                    f"Si es un animal diferente, por favor usa otro nombre e intenta nuevamente."
                )
                # Limpiar historial para empezar de nuevo
                self.delete_records_optimized(phone, "whatsapp_messages")
                return
            
            if result.ok:
                # Datos completos: pedir confirmación
                await self.confirmation_manager.send_confirmation_request(phone, tipo, result)
            else:
                # Datos incompletos: pedir campos faltantes y guardar en caché
                await self.request_missing_fields(phone, tipo, result)
                self._save_incomplete_request(phone, tipo, result)
            
        except Exception as e:
            logger.error(f"Error en handle_message_flow: {e}")
            await self.send_error_response(phone, str(e))
            raise
