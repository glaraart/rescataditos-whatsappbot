# WhatsApp webhook service
from fastapi import Request, HTTPException
from typing import Dict, Any
import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.verify_token = settings.WHATSAPP_VERIFY_TOKEN
    
    

    async def send_message(self, phone: str, complete_message: str) -> Dict[str, Any]:
        """Send message to WhatsApp user"""
        try:
            # URL de la API de WhatsApp Business
            url = f"https://graph.facebook.com/v22.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
            
            # Headers para la petición
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Payload del mensaje
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {
                    "body": complete_message
                }
            }
            
            # Enviar mensaje
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Mensaje enviado a {phone}: {complete_message[:50]}...")
                return result
                
        except Exception as e:
            logger.error(f"Error enviando mensaje a {phone}: {e}")
            raise HTTPException(status_code=500, detail=f"Error enviando mensaje: {e}")
    
    async def download_media(self, media_url: str) -> bytes:
        """Descarga un archivo multimedia desde una URL protegida (requiere access_token)"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient() as client:
            # Primera llamada: obtener información del media
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            # Parsear JSON para obtener la URL real
            media_info = response.json()
            
            real_download_url = media_info.get("url")
            if not real_download_url:
                raise Exception("No se encontró URL de descarga en la respuesta")            
            # Segunda llamada: descargar el archivo real
            download_response = await client.get(real_download_url, headers=headers)
            download_response.raise_for_status()
            return download_response.content
