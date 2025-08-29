# Message handler with composition approach
import logging
from typing import Dict, Any
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
 
        
        # Registry de handlers por tipo de mensaje
        self.handlers = {
            "text": self._handle_text,
            "audio": self._handle_audio,
            "image": self._handle_image
        }
     
    
    async def process_message(self, message) -> AIAnalysis:
        """Procesa mensaje completo: análisis + manejo del resultado + respuesta automática"""
        try:
            # Procesar mensaje
            handler = self.handlers.get(message.get("type"))
            analysis = await handler(message) 
            # Manejar resultado (logging + crear registros)
            await self._handle_analysis_result(message, analysis)
            
            # Enviar respuesta automática al usuario
            await self._send_response_to_user(message, analysis)
            
            return analysis
            
        except Exception as e:
            # En caso de error, enviar mensaje de error al usuario
            logger.error(f"Error procesando mensaje completo: {e}")
            await self._send_error_response(message, str(e))
            raise
    
    async def _handle_analysis_result(self, message: WhatsAppMessage, analysis: AIAnalysis):
        """Maneja el resultado del análisis de IA"""
        try:
            # Registrar mensaje completo + análisis en Sheets
            message_dict = {
                'timestamp': message.timestamp,
                'from_number': message.from_number,
                'type': message.message_type,
                'content': message.content or '',
                'message_id': message.message_id
            }
            analysis_dict = {
                'tipo_registro': analysis.tipo_registro,
                'confianza': analysis.confianza,
                'detalles': analysis.detalles
            }
            await self.sheets_service.log_message_with_analysis(message_dict, analysis_dict)
            
            # Crear registros según tipo
            if analysis.tipo_registro == "nuevo_rescate":
                await self.sheets_service.create_animal_record(analysis.detalles)
                
            elif analysis.tipo_registro == "cambio_estado":
                await self.sheets_service.create_state_change_record(analysis.detalles)
                
            elif analysis.tipo_registro == "visita_vet":
                await self.sheets_service.create_vet_visit_record(analysis.detalles)
                
            elif analysis.tipo_registro == "gasto":
                await self.sheets_service.create_expense_record(analysis.detalles)
                
            elif analysis.tipo_registro == "consulta":
                # Solo log, no crear registro adicional
                logger.info(f"Consulta registrada: {analysis.detalles}")
            
            logger.info(f"Análisis procesado: {analysis.tipo_registro}")
            
        except Exception as e:
            logger.error(f"Error manejando resultado de análisis: {e}")
            raise
    
    async def _send_response_to_user(self, message: WhatsAppMessage, analysis: AIAnalysis):
        """Envía respuesta automática al usuario basada en el análisis"""
        try:
            # Generar mensaje de confirmación
            success_message = f"✅ Mensaje procesado: {analysis.tipo_registro}"
            
            if analysis.confianza < 0.5:
                success_message += f" (confianza: {analysis.confianza:.1%})"
            
            # Agregar detalles específicos según el tipo
            if analysis.tipo_registro == "nuevo_rescate" and analysis.animal_nombre:
                success_message += f"\n🐾 Animal: {analysis.animal_nombre}"
            
            elif analysis.tipo_registro == "cambio_estado":
                estado = analysis.detalles.get("nuevo_estado", "")
                if estado:
                    success_message += f"\n📋 Estado: {estado}"
            
            elif analysis.tipo_registro == "visita_vet":
                fecha = analysis.detalles.get("fecha", "")
                if fecha:
                    success_message += f"\n🏥 Fecha: {fecha}"
            
            elif analysis.tipo_registro == "gasto":
                monto = analysis.detalles.get("monto", "")
                if monto:
                    success_message += f"\n💰 Monto: {monto}"
            
            # Enviar respuesta
            await self.whatsapp_service.send_message(message.from_number, success_message)
            
            logger.info(f"Respuesta enviada a {message.from_number}: {analysis.tipo_registro}")
            
        except Exception as e:
            logger.error(f"Error enviando respuesta al usuario: {e}")
            # No re-lanzar error para no afectar el procesamiento principal
    
    async def validate_message(self, message: WhatsAppMessage) -> bool:

        """Valida si el mensaje puede ser procesado"""
        if message.message_type not in self.handlers:
            return False
        
        # Validaciones específicas por tipo
        if message.message_type == "text" and not message.content:
            return False
        
        if message.message_type in ["audio", "image"] and not message.media_url:
            return False
        
        return True
    
    async def _handle_text(self, message: WhatsAppMessage) -> AIAnalysis:
        """Handler para mensajes de texto"""
        try:
            # Determinar tipo y contenido
            message_type = "text"  # Default
            content = message["text"]["body"]
            media_url = None
            media_mime_type = None
              
            # Analizar texto con IA
            analysis = await self.ai_service.analyze_text(content)
            return analysis
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de texto: {e}")
            # Devolver análisis por defecto en caso de error
            return AIAnalysis(
                tipo_registro="consulta",
                confianza=0.0,
                detalles={"error": str(e), "mensaje_original": message.content}
            )
    
    async def _handle_audio(self, message) -> AIAnalysis:
        """Handler para mensajes de audio"""
        try:
                                   
            # Convertir audio a texto con Whisper
            audio_data = message["audio"]
            media_id = audio_data['id']
            media_mime_type = audio_data.get("mime_type", "audio/ogg")
            audio_bytes = await self.whatsapp_service.download_media(media_id)
            
            # Convertir audio a texto con Whisper directamente desde bytes
            text = await self.ai_service.audio_to_text(audio_bytes)
            print("Transcripción de audio:", text)
            # Analizar el texto transcrito 
             
            analysis = await self.ai_service.analyze_text(text)
            
            # Agregar información de que fue audio original
            analysis.detalles["audio_transcrito"] = text
            analysis.detalles["tipo_original"] = "audio"
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de audio: {e}")
            return AIAnalysis(
                tipo_registro="consulta",
                confianza=0.0,
                detalles={"error": str(e), "tipo_original": "audio"}
            )
    
    def _get_audio_extension(self, mime_type: str) -> str:
        """Obtiene la extensión correcta basada en el mime type"""
        mime_to_extension = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".mp4",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
            "audio/aac": ".aac"
        }
        return mime_to_extension.get(mime_type, ".ogg")

    async def _handle_image(self, message ) -> AIAnalysis:
        """Handler para mensajes con imagen"""
        try:
            # Descargar imagen desde WhatsApp
            image_data = message["image"]
            media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
            media_mime_type = image_data.get("mime_type", "image/jpeg")
            content = image_data.get("caption", "")
            image_file = await self.whatsapp_service.download_media(media_url)
            
            if not image_file:
                raise Exception("No se pudo descargar la imagen")
            
            # Subir imagen a Google Drive
            #drive_url = await self.drive_service.upload_file(
            #    image_file, 
            #    f"rescate_{message.message_id}.jpg"
            #)
         #
            # Analizar imagen + texto (si hay caption) con IA
            #analysis = await self.ai_service.analyze_image_and_text(
            #    image_url=drive_url,
            #    text=message.content or ""
            #)
            #
            ## Agregar información adicional
            #analysis.detalles["imagen_url"] = drive_url
            #analysis.detalles["tipo_original"] = "imagen"
            #if message.content:
            #    analysis.detalles["caption"] = message.content
            #
            #return analysis
            
        except Exception as e:
            logger.error(f"Error procesando mensaje con imagen: {e}")
            return AIAnalysis(
                tipo_registro="consulta",
                confianza=0.0,
                detalles={
                    "error": str(e), 
                    "tipo_original": "imagen",
                    "caption": message.content or ""
                }
            )
