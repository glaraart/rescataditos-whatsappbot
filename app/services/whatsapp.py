# WhatsApp webhook service
from fastapi import HTTPException
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
        """Send message to WhatsApp user (con log de error detallado)"""
        try:
            url = f"https://graph.facebook.com/v22.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": "541115" + phone[5:],
                "type": "text",
                "text": {"body": complete_message}
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)

                # Si falla, loguear el cuerpo de error y lanzar excepción
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                    except Exception:
                        error_data = response.text
                    logger.error(
                        f"Error enviando mensaje a {phone}: "
                        f"status={response.status_code}, detalle={error_data}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_data
                    )

                result = response.json()
                logger.info(f"Mensaje enviado a {phone}: {complete_message[:80]}...")
                return result

        except Exception as e:
            logger.error(f"Excepción inesperada enviando mensaje a {phone}: {e}")
            raise HTTPException(status_code=500, detail=f"Error enviando mensaje: {e}")

    async def send_message_with_buttons(self, phone: str, message: str, buttons: list) -> Dict[str, Any]:
        """
        Envía mensaje con botones interactivos.
        
        Args:
            phone: Número de teléfono
            message: Texto del mensaje
            buttons: Lista de botones, cada uno con formato:
                     [{"id": "button_id", "title": "Texto del botón"}]
                     Máximo 3 botones
        """
        try:
            url = f"https://graph.facebook.com/v22.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Formatear botones según API de WhatsApp
            button_list = []
            for btn in buttons[:3]:  # Máximo 3 botones
                button_list.append({
                    "type": "reply",
                    "reply": {
                        "id": btn["id"],
                        "title": btn["title"]
                    }
                })
            
            payload = {
                "messaging_product": "whatsapp",
                "to": "541115" + phone[5:],
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": message
                    },
                    "action": {
                        "buttons": button_list
                    }
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                    except Exception:
                        error_data = response.text
                    logger.error(
                        f"Error enviando mensaje con botones a {phone}: "
                        f"status={response.status_code}, detalle={error_data}"
                    )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_data
                    )

                result = response.json()
                logger.info(f"Mensaje con botones enviado a {phone}")
                return result

        except Exception as e:
            logger.error(f"Excepción inesperada enviando mensaje con botones a {phone}: {e}")
            raise HTTPException(status_code=500, detail=f"Error enviando mensaje con botones: {e}")

    async def download_media(self, media_url: str) -> bytes:
        """Descarga un archivo multimedia desde una URL protegida (requiere access_token)"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient() as client:
            # Primera llamada: obtener información del media
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            print("response:", response)
            # Parsear JSON para obtener la URL real
            media_info = response.json()
            
            real_download_url = media_info.get("url")
            if not real_download_url:
                raise Exception("No se encontró URL de descarga en la respuesta")            
            # Segunda llamada: descargar el archivo real
            download_response = await client.get(real_download_url, headers=headers)
            download_response.raise_for_status()
            return download_response.content 
