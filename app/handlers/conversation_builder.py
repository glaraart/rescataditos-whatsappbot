import logging
import json
import base64
from app.models.analysis import RawContent

logger = logging.getLogger(__name__)


class ConversationBuilder:
    """Construye RawContent desde historial de mensajes"""
    
    def __init__(self, db_service, whatsapp_service, ai_service):
        self.db_service = db_service
        self.whatsapp_service = whatsapp_service
        self.ai_service = ai_service
    
    async def build_raw_content(self, phone: str, phone_history: list = None) -> RawContent:
        """Construye RawContent completo desde historial"""
         
        text_parts = []
        images = []
        
        for msg in phone_history:
            msg_type = msg.get("type")
            
            if msg_type == "text":
                text_parts.append(msg.get("text", {}).get("body", ""))
            
            elif msg_type == "image":
                image_data = await self._process_image(msg["image"])
                images.append(image_data)
                text_parts.append(msg["image"].get("caption", ""))
            
            elif msg_type == "audio":
                audio_text = await self._process_audio(msg)
                text_parts.append(audio_text)
            
            elif msg_type == "incomplete_request":
                context = self._build_incomplete_context(msg)
                text_parts.append(context)
            
            # Ignorar mensajes de tipo "pending_confirmation" - no son parte del contexto
            elif msg_type == "pending_confirmation":
                continue
        
        return RawContent(phone=phone, text="\n".join(text_parts), images=images)
    
    async def _process_image(self, image_data: dict) -> dict:
        """Procesa imagen para AI"""
        media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
        image_bytes = await self.whatsapp_service.download_media(media_url)
        base64_image = base64.b64encode(image_bytes).decode()
        
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
        }
    
    async def _process_audio(self, audio_msg: dict) -> str:
        """Procesa audio y retorna transcripción"""
        try:
            audio_data = audio_msg["audio"]
            media_url = f"https://graph.facebook.com/v22.0/{audio_data['id']}"
            audio_bytes = await self.whatsapp_service.download_media(media_url)
            return await self.ai_service.audio_to_text(audio_bytes)
        except Exception as e:
            logger.error(f"Error procesando audio: {e}")
            return ""
    
    def _build_incomplete_context(self, msg: dict) -> str:
        """Construye contexto de solicitud incompleta"""
        tipo = msg.get("tipo_solicitud", "")
        detalles = msg.get("detalles_parciales", {})
        campos = msg.get("campos_faltantes", [])
        
        return (
            f"\n[SOLICITUD ANTERIOR: {tipo} - INCOMPLETA]\n"
            f"Datos ya proporcionados: {json.dumps(detalles, ensure_ascii=False)}\n"
            f"Campos faltantes: {', '.join(campos)}\n"
        )
