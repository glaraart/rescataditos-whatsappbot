# Utility functions
import logging
from typing import Dict, Any
from app.models.whatsapp import WhatsAppMessage

logger = logging.getLogger(__name__)

def extract_message_info(message_data: dict, webhook_value: dict) -> WhatsAppMessage:
    """Extrae información del mensaje desde el webhook de WhatsApp"""
    
    # Información básica
    message_id = message_data.get("id", "")
    from_number = message_data.get("from", "")
    timestamp = str(message_data.get("timestamp", ""))
    
    # Determinar tipo y contenido
    message_type = "text"  # Default
    content = None
    media_url = None
    media_mime_type = None
    
    if "text" in message_data:
        message_type = "text"
        content = message_data["text"]["body"]
        
    elif "audio" in message_data:
        message_type = "audio"
        audio_data = message_data["audio"]
        media_url = f"https://graph.facebook.com/v22.0/{audio_data['id']}"
        media_mime_type = audio_data.get("mime_type", "audio/ogg")
        
    elif "image" in message_data:
        message_type = "image"
        image_data = message_data["image"]
        media_url = f"https://graph.facebook.com/v22.0/{image_data['id']}"
        media_mime_type = image_data.get("mime_type", "image/jpeg")
        content = image_data.get("caption", "")
    
    return WhatsAppMessage(
        from_number=from_number,
        message_id=message_id,
        timestamp=timestamp,
        message_type=message_type,
        content=content,
        media_url=media_url,
        media_mime_type=media_mime_type
    )

async def send_whatsapp_response(to_number: str, message: str, whatsapp_service):
    """Envía respuesta por WhatsApp"""
    try:
        await whatsapp_service.send_message(to_number, message)
    except Exception as e:
        logger.error(f"Error enviando respuesta WhatsApp: {e}")
