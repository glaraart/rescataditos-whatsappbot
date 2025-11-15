# Message handler with composition approach
import logging
import json
import random
import base64
from datetime import datetime
from app.models.whatsapp import  AIAnalysis
from app.services.ai import AIService
from app.services.sheets import SheetsService
from app.services.whatsapp import WhatsAppService

#from app.services.drive import DriveService

logger = logging.getLogger(__name__)

class MessageHandler:
    """Handler para procesar diferentes tipos de mensajes de WhatsApp"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.sheets_service = SheetsService()
        self.whatsapp_service = WhatsAppService()
        
        # Registry de creadores de registros
        self.record_creators = {
            "nuevo_rescate": self._create_nuevo_rescate,
            "cambio_estado": self._create_cambio_estado,
            "visita_vet": self._create_visita_vet,
            "gasto": self._create_gasto,
            "consulta": self._handle_consulta
        } 
         
    async def process_message(self, message) :
        """Procesa mensaje con contexto de conversación inteligente"""
        try:
            phone = message.get("from") 
            # Agregar mensaje al contexto de conversación
            self._add_to_conversation(phone, message) 
            
            # Construir contenido multimodal desde toda la conversación
            content_list = await self._build_content_from_conversation(phone)
            
            # Análisis único con IA multimodal
            analysis = await self.ai_service.analyze_multimodal(content_list)
            # Buscar el creador de registro apropiado
            creator = self.record_creators.get(analysis.tipo_registro, self._handle_unknown_record_type)
            
            # Ejecutar el creador correspondiente
            success = await creator(message, analysis)

            if success:
                await self._send_completion_confirmation(phone, analysis)
                # Limpiar cache después de procesar - eliminar registros del teléfono
                self.sheets_service.delete_records_optimized(phone, "WHATSAPP")
            elif not analysis.informacion_completa :
                # El creator ya envió el mensaje de error específico
                await self._request_missing_fields_from_ai(phone, analysis) 
            else:
                pass

        except Exception as e:
            logger.error(f"Error procesando mensaje completo: {e}")
            await self._send_error_response(phone, str(e))
            raise

    # ===== CREADORES DE REGISTROS (REGISTRY PATTERN) =====
    
    async def _create_nuevo_rescate(self, message, analysis: AIAnalysis):
        """Crear registro de nuevo rescate"""
        if analysis.animal_nombre and self.sheets_service.check_animal_name_exists(analysis.animal_nombre):
            await self.whatsapp_service.send_message(message.get("from"), f"❌ Ya existe un animal registrado con el nombre '{analysis.animal_nombre}'. Por favor elige otro nombre.")
            return False
        elif analysis.informacion_completa:
            try:
                # Generar ID único de 10 dígitos para el rescate
                rescue_id = random.randint(1000000000, 9999999999) 
                fecha = datetime.fromtimestamp(int(message.get("timestamp")))

                animal = {
                    "id": rescue_id, 
                    "nombre": analysis.animal_nombre,
                    "tipo_animal": analysis.detalles.get("tipo_animal"),
                    "fecha": fecha.strftime('%d/%m/%Y %H:%M:%S'),
                    "ubicacion": analysis.detalles.get("ubicacion"),
                    "edad": analysis.detalles.get("edad"),
                    "color_de_pelo": str(analysis.detalles.get("color_de_pelo")),
                    "condicion_de_salud_inicial": analysis.detalles.get("condicion_de_salud_inicial"),
                    "activo": True,
                    "fecha_actualizacion": fecha.strftime('%d/%m/%Y'),
                    "media_url": analysis.detalles.get("media_url"),
                    "animal_id": rescue_id, 
                }
                
                analysis.detalles["cambio_estado"]["animal_id"] = rescue_id
                analysis.detalles["cambio_estado"]["fecha"] = fecha.strftime('%d/%m/%Y %H:%M:%S')
                    
                # Insertar registros
                self.sheets_service.insert_sheet_from_dict(animal, "ANIMAL")
                self.sheets_service.insert_sheet_from_dict(animal, "INTERACCION")
                self.sheets_service.insert_sheet_from_dict(analysis.detalles["cambio_estado"], "EVENTO")
                return True
            except Exception as e:
                logger.error(f"Error creando nuevo rescate: {e}")
                await self.whatsapp_service.send_message(message.get("from"), "❌ Error interno al crear el rescate. Intenta nuevamente.")
                return False
        else:
            return False  # Información incompleta, pero no es un error
        
    async def _create_cambio_estado(self, message, analysis: AIAnalysis):
        """Crear registro de cambio de estado"""
        animal_id = self.sheets_service.check_animal_name_exists(analysis.animal_nombre)
        if animal_id:
            try:
                analysis.detalles["animal_id"] = animal_id
                fecha = datetime.fromtimestamp(int(message.get("timestamp")))
                analysis.detalles["fecha"] = fecha.strftime('%d/%m/%Y %H:%M:%S')
                self.sheets_service.insert_sheet_from_dict(analysis.detalles, "EVENTO")
                return True
            except Exception as e:
                logger.error(f"Error creando cambio de estado: {e}")
                await self.whatsapp_service.send_message(message.get("from"), "❌ Error interno al registrar cambio de estado. Intenta nuevamente.")
                return False
        else:
            await self.whatsapp_service.send_message(message.get("from"), f"❌ No existe un animal registrado con el nombre '{analysis.animal_nombre}'. Verifica el nombre.")
            return False
        
    
    async def _create_visita_vet(self, message, analysis: AIAnalysis):
        """Crear registro de visita veterinaria"""
        animal_id = self.sheets_service.check_animal_name_exists(analysis.animal_nombre)
        if animal_id:
            try:
                analysis.detalles["animal_id"] = animal_id
                
                # Usar fecha de analysis si existe, sino timestamp del mensaje
                if analysis.detalles.get("fecha"):
                    # Ya tiene fecha, mantenerla
                    fecha_str = analysis.detalles["fecha"]
                else:
                    # Usar timestamp del mensaje como fallback
                    fecha = datetime.fromtimestamp(int(message.get("timestamp")))
                    fecha_str = fecha.strftime('%d/%m/%Y %H:%M:%S')
                    analysis.detalles["fecha"] = fecha_str
                
                self.sheets_service.insert_sheet_from_dict(analysis.detalles, "VISITA_VETERINARIA")
                return True
            except Exception as e:
                logger.error(f"Error creando visita veterinaria: {e}")
                await self.whatsapp_service.send_message(message.get("from"), "❌ Error interno al registrar visita veterinaria. Intenta nuevamente.")
                return False
    
    async def _create_gasto(self, message, analysis: AIAnalysis):
        """Crear registro de gasto"""
        try:
            # Usar fecha de analysis si existe, sino timestamp del mensaje
            
            gasto_id = random.randint(1000000000, 9999999999)
            analysis.detalles["gasto_id"] = gasto_id 
            if not analysis.detalles.get("fecha"):
                fecha = datetime.fromtimestamp(int(message.get("timestamp")))
                analysis.detalles["fecha"] = fecha.strftime('%d/%m/%Y %H:%M:%S')
            
            self.sheets_service.insert_sheet_from_dict(analysis.detalles, "GASTOS")
            animal_nombre = self.sheets_service.check_animal_name_exists(analysis.animal_nombre)
            if analysis.animal_nombre and animal_nombre:
                analysis.detalles["animal_id"] = animal_nombre 
                self.sheets_service.insert_sheet_from_dict(analysis.detalles, "GASTO_ANIMAL")

            return True
        except Exception as e:
            logger.error(f"Error creando gasto: {e}")
            await self.whatsapp_service.send_message(message.get("from"), "❌ Error interno al registrar gasto. Intenta nuevamente.")
            return False
    
    async def _handle_consulta(self, message, analysis: AIAnalysis):
        """Manejar consulta - solo log"""
        logger.info(f"Consulta registrada: {analysis.detalles}")
        phone =message.get("from")
        respuesta_sugerida = analysis.detalles.respuesta_sugerida
        await self.whatsapp_service.send_message(phone, respuesta_sugerida )
        return False  # Las consultas siempre son exitosas
    
    async def _handle_unknown_record_type(self, message, analysis: AIAnalysis):
        """Manejar tipos de registro desconocidos"""
        logger.warning(f"Tipo de registro desconocido: {analysis.tipo_registro}")
        logger.info(f"Detalles del registro desconocido: {analysis.detalles}")
        await self.whatsapp_service.send_message(message.get("from"), f"❌ Tipo de registro no reconocido: {analysis.tipo_registro}")
        return False
    
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
        
    # ===== FUNCIONES DE CONTEXTO DE CONVERSACIÓN =====
    
    async def _build_content_from_conversation(self, phone: str):
        """Construye lista de contenido multimodal desde la conversación"""
        try:
            phone_info = self.sheets_service.search_phone_in_whatsapp_sheet(phone)
            content_list = []
            context_text = ""
            for msg in phone_info:
                if msg.get("type") == "text":
                    context_text += msg.get("text", {}).get("body", "")

                elif msg.get("type") == "image":
                    # Descargar y convertir imagen
                    image_data = msg["image"]
                    media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
                    image_bytes = await self.whatsapp_service.download_media(media_url)
                    base64_image = base64.b64encode(image_bytes).decode()
                    content_list.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                        
                        # Agregar caption si existe
                    context_text +=  image_data.get("caption", "") 
                        
                elif msg.get("type") == "audio":
                    # Convertir audio a texto y agregarlo como texto
                    context_text += await self._handle_audio(msg)

            content_list.append({"type": "text", "text": context_text})
            return content_list
            
        except Exception as e:
            logger.error(f"Error construyendo contenido de conversación: {e}")
            return [{"type": "text", "text": "Error procesando conversación"}]
    
    def _add_to_conversation(self, phone: str, message_data: dict):
        """Agregar mensaje al cache de conversación"""
        now = datetime.now()    
        phone_info= {
                "phone": phone,
                "messages": json.dumps(message_data, ensure_ascii=False),  # Convertir a JSON string
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S") 
            }         
        # Buscar si existe información previa del teléfono en WHATSSAP
        self.sheets_service.insert_sheet_from_dict(phone_info,"WHATSAPP")
    
    
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