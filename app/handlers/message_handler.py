# Message handler with composition approach
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.models.whatsapp import WhatsAppMessage, AIAnalysis
from app.services.ai import AIService
from app.services.sheets import SheetsService
from app.services.whatsapp import WhatsAppService
import tempfile
import os
#from app.services.drive import DriveService

logger = logging.getLogger(__name__)

class MessageHandler:
    """Handler para procesar diferentes tipos de mensajes de WhatsApp"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.sheets_service = SheetsService()
        self.whatsapp_service = WhatsAppService()
        #self.drive_service = DriveService()
        # Cache para mantener contexto de conversación
        self.conversation_cache = {}  # {phone_number: {messages: [], timestamp: datetime, waiting_for: str}}
        self.WAIT_TIME = 300  # segundos para esperar mensajes relacionados        
        # Registry de handlers por tipo de mensaje
        self.handlers = {
            "text": self._handle_text,
            "audio": self._handle_audio,
            "image": self._handle_image
        }
     
    
    async def process_message(self, message) :
        """Procesa mensaje con contexto de conversación inteligente"""
        try:
            phone = message.get("from") 
            
            # Agregar mensaje al contexto de conversación
            await self._add_to_conversation(phone, message)
               
            # Hay imagen reciente + texto/audio - procesar todo el contexto
            analysis = await self._process_conversation_context(phone)
            print("analysis", analysis)
            if analysis.informacion_completa:
                    # Información completa - procesar y guardar
                    await self._handle_analysis_result(message, analysis)
                    await self._send_completion_confirmation(message, analysis)
                            # Limpiar cache después de procesar
                    self.conversation_cache[phone] = {"messages": [], "timestamp": datetime.now(), "waiting_for": None}
            else:
                await self._request_missing_fields_from_ai(phone, analysis) 

            
        except Exception as e:
            logger.error(f"Error procesando mensaje completo: {e}")
            await self._send_error_response(phone, str(e))
            raise

    
    async def _handle_analysis_result(self, message, analysis: AIAnalysis):
        """Maneja el resultado del análisis de IA"""
        try:
     
            analysis_dict = {
                'tipo_registro': analysis.tipo_registro,
                'detalles': analysis.detalles
            }
            print("analysis dict", analysis_dict)
            await self.sheets_service.log_message_with_analysis(message, analysis_dict)
            
            # Crear registros según tipo
            if analysis.tipo_registro == "nuevo_rescate": 
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles, "ANIMAL")
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles, "POST")
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles,"EVENTO")

            elif analysis.tipo_registro == "cambio_estado":
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles,"EVENTO")
                
            elif analysis.tipo_registro == "visita_vet":
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles,"VISITA_VETERINARIA")
                
            elif analysis.tipo_registro == "gasto":
                await self.sheets_service.insert_sheet_from_dict(analysis.detalles,"GASTOS")

            elif analysis.tipo_registro == "consulta":
                # Solo log, no crear registro adicional
                logger.info(f"Consulta registrada: {analysis.detalles}")
            
            logger.info(f"Análisis procesado: {analysis.tipo_registro}")
            
        except Exception as e:
            logger.error(f"Error manejando resultado de análisis: {e}")
            raise
    
        
    async def _handle_text(self, message: str) -> AIAnalysis:
        """Handler para mensajes de texto"""
        try:
          
            # Analizar texto con IA
            analysis = await self.ai_service.analyze_text(message)
            return analysis
        except Exception as e:
            logger.error(f"Error procesando mensaje de texto: {e}")
            return AIAnalysis(
                tipo_registro="error",
                informacion_completa=False,
                campos_faltantes=[],
                confianza=0.0,
                detalles={"error": str(e), "tipo_original": "text"}
            )

    
    async def _handle_audio(self, message) -> str:
        """Handler para mensajes de audio - retorna texto transcrito"""
        try:
            # Convertir audio a texto con Whisper
            audio_data = message["audio"]
            media_url = f"https://graph.facebook.com/v22.0/{audio_data['id']}"
            audio_bytes = await self.whatsapp_service.download_media(media_url)
            
            # Convertir audio a texto con Whisper directamente desde bytes
            text = await self.ai_service.audio_to_text(audio_bytes)
            
            return text
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de audio: {e}")
            return ""  # Retornar string vacío en caso de error
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de audio: {e}")

    
    async def _handle_image(self ,phone, image, combined_text) -> AIAnalysis: 
        """Handler para mensajes con imagen"""
        try:
            # Descargar imagen desde WhatsApp
            image_data = image["image"]
            media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
            content = image_data.get("caption", "")
            image_file = await self.whatsapp_service.download_media(media_url)
            combined_text =content + " " + combined_text 

            if not image_file:
                raise Exception("No se pudo descargar la imagen")
            # Subir imagen a Google Drive
            #drive_url = await self.drive_service.upload_file(
            #    image_file, 
            #    f"rescate_{message.message_id}.jpg"
            #)
         #
            #Analizar imagen + texto (si hay caption) con IA
            analysis = await self.ai_service.analyze_image_and_text( image_bytes=image_file,text=combined_text)
 
            return analysis
            
        except Exception as e:
            logger.error(f"Error procesando mensaje con imagen: {e}")
        
    # ===== FUNCIONES DE CONTEXTO DE CONVERSACIÓN =====
    
    async def _add_to_conversation(self, phone: str, message_data: dict):
        """Agregar mensaje al cache de conversación"""
        now = datetime.now()
        
        if phone not in self.conversation_cache:
            self.conversation_cache[phone] = {
                "messages": [],
                "timestamp": now,
                "waiting_for": None
            }
        
        # Limpiar cache viejo (más de 5 minutos)
        if now - self.conversation_cache[phone]["timestamp"] > timedelta(minutes=5):
            self.conversation_cache[phone] = {
                "messages": [],
                "timestamp": now,
                "waiting_for": None
            }
        
        self.conversation_cache[phone]["messages"].append(message_data)
        self.conversation_cache[phone]["timestamp"] = now
        
    async def _process_conversation_context(self, phone: str):
        """Procesar todo el contexto de conversación acumulado"""        
        messages = self.conversation_cache[phone]["messages"]
        # Extraer componentes del contexto
        text_content = ""
        image_data = None
        audio_content = "" 
        for msg in messages:
            if msg.get("type") == "text":
                text_content += msg.get("text", {}).get("body", "") + " "
            elif msg.get("type") == "image":
                image_data = msg
                text_content += image_data.get("caption", "")
            elif msg.get("type") == "audio":
                # Usar el handler de audio para procesar correctamente
                audio_text = await self._handle_audio(msg) 
                audio_content += audio_text + " "
        
        # Combinar todo el contenido textual
        combined_text = (text_content + audio_content).strip()
        
        # Analizar según el tipo de contenido disponible
        if image_data and combined_text:
            # Imagen + texto/audio
            analysis = await self._handle_image(phone, image_data, combined_text)
        elif combined_text:
            # Solo texto/audio
            analysis=await self._handle_text( combined_text)
        elif image_data:
            # Solo imagen - pedir descripción
            print("Descripción de la imagen:")
            analysis = AIAnalysis(
                tipo_registro="pendiente", 
                informacion_completa=False,
                campos_faltantes=["descripcion_imagen"],
                detalles={"status": "waiting_for_description"}
            )
        else:
            # Caso de fallback - no hay contenido procesable
            analysis = AIAnalysis(
                tipo_registro="error",
                informacion_completa=False,
                campos_faltantes=[],
                detalles={"error": "No hay contenido procesable en la conversación"}
            )

        return analysis
    
    
    async def _request_missing_fields_from_ai(self, phone: str, analysis: AIAnalysis):
        """Pedir campos faltantes usando directamente la respuesta de la IA"""
        try:
                 
            # Crear mensaje estructurado basado en lo que la IA identificó
            tipo_registro = analysis.tipo_registro.replace("_", " ").upper()
            
            header = f"📋 **INFORMACIÓN INCOMPLETA - {tipo_registro}**\n\n" 
            header += "🔍 **CAMPOS FALTANTES:**\n\n"
            
            # Convertir la lista de campos faltantes en un mensaje claro
            missing_sections = []
            for i, campo in enumerate(analysis.campos_faltantes, 1):
                # Hacer más legible el nombre del campo
                campo_legible = campo.replace("_", " ").title()
                missing_sections.append(f"  {i}. **{campo_legible}**")
            
            campos_text = "\n".join(missing_sections)
            
            complete_message = header + campos_text 
            
            await self.whatsapp_service.send_message(phone, complete_message)
            
            # Marcar en cache que estamos esperando información específica
            if phone in self.conversation_cache:
                self.conversation_cache[phone]["waiting_for"] = analysis.tipo_registro
                self.conversation_cache[phone]["partial_analysis"] = analysis
                
            logger.info(f"Solicitados {len(analysis.campos_faltantes)} campos faltantes para {phone}: {analysis.campos_faltantes}")
            
        except Exception as e:
            logger.error(f"Error pidiendo campos faltantes: {e}")
            await self.whatsapp_service.send_message(phone, 
                "📝 Necesito más información para completar el registro. Por favor proporciona más detalles.")
   
    async def _send_completion_confirmation(self, phone: str, analysis: AIAnalysis):
        """Enviar confirmación detallada cuando se completa la información"""
        try:
            tipo = analysis.tipo_registro.upper().replace("_", " ") 
            detalles = analysis.detalles

            mensaje=  f"""{tipo} +  REGISTRADO EXITOSAMENTE
                    **Animal**: {analysis.animal_nombre}"""
            for  detalle in detalles:
                mensaje += f"\n• **{detalle.replace('_', ' ').title()}**: {detalles[detalle]}"
            await self.whatsapp_service.send_message(phone, mensaje)
        except Exception as e:
            logger.error(f"Error enviando confirmación: {e}")
            await self.whatsapp_service.send_message(phone, "✅ Información registrada exitosamente.")

    async def _send_error_response(self, phone, error_msg: str):
        """Envía respuesta de error al usuario"""
        try:
            await self.whatsapp_service.send_message(
                    phone, 
                    f"❌ Lo siento, hubo un error procesando tu mensaje:\n{error_msg}\n\nPor favor intenta nuevamente."
                )
        except Exception as e:
            logger.error(f"Error enviando respuesta de error: {e}")
