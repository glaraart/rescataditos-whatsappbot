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
    
    async def verify_webhook(self, request: Request) -> str:
        """Verify webhook for WhatsApp"""
        try:
            mode = request.query_params.get("hub.mode")
            token = request.query_params.get("hub.verify_token")
            challenge = request.query_params.get("hub.challenge")
            
            if mode == "subscribe" and token == self.verify_token:
                logger.info("Webhook verified successfully")
                return challenge
            else:
                raise HTTPException(status_code=403, detail="Forbidden")
        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            raise HTTPException(status_code=400, detail="Bad request")
    
    async def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming WhatsApp messages"""
        try:
            logger.info(f"Processing webhook payload: {payload}")
            
            # Extract message data
            entries = payload.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    for message in messages:
                        await self._handle_message(message)
            
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual message"""
        message_type = message.get("type")
        sender = message.get("from")
        
        logger.info(f"Handling message type: {message_type} from: {sender}")
        
        # Process different message types
        if message_type == "text":
            text_content = message.get("text", {}).get("body", "")
            await self._process_text_message(sender, text_content)
        elif message_type == "image":
            await self._process_image_message(sender, message)
        # Add more message types as needed
    
    async def _process_text_message(self, sender: str, text: str):
        """Process text messages"""
        logger.info(f"Processing text message from {sender}: {text}")
        # Implement text message processing logic
    
    async def _process_image_message(self, sender: str, message: Dict[str, Any]):
        """Process image messages"""
        logger.info(f"Processing image message from {sender}")
        # Implement image message processing logic
    
    async def send_message(self, recipient: str, message: str) -> Dict[str, Any]:
        """Send message to WhatsApp user"""
        # Implement message sending logic
        logger.info(f"Sending message to {recipient}: {message}")
        return {"status": "sent"}
    
    async def download_media(self, media_url: str) -> bytes:
        """Descarga un archivo multimedia desde una URL protegida (requiere access_token)"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient() as client:
            print("url" , media_url)
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            print("Media downloaded successfully")
            return response.content
