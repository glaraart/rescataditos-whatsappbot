"""
Sistema WhatsApp para Rescatistas de Animales
FastAPI + Google Sheets + OpenAI + Cloud Run
"""
import os
import json
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse 
# ===== HANDLERS =====
from app.handlers.message_handler import MessageHandler
from app.services.whatsapp import WhatsAppService
# ===== UTILS =====
from app.utils.helpers import extract_message_info

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== CONFIGURACIÓN =====

class Config:
    # WhatsApp
    VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "rescate_verify_token_123")
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Google
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/service-account.json")
    SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Rescate WhatsApp DB")
    DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
    
    # Cloud Run
    PORT = int(os.getenv("PORT", 8080))
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

config = Config()
# ===== INICIALIZAR FASTAPI =====

app = FastAPI(
    title="Sistema WhatsApp 101 Rescataditos",
    description="API para procesar mensajes de WhatsApp de 101 Rescataditos",
    version="1.0.0",
    docs_url="/docs" if config.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if config.ENVIRONMENT == "development" else None
)

# Inicializar handler de mensajes (maneja sus propias dependencias y respuestas)
#message_handler = MessageHandler()
#whatsapp_service = WhatsAppService()

# ===== WEBHOOK WHATSAPP =====

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """Verificación del webhook de WhatsApp"""
    logger.info(f"Verificación webhook: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == config.VERIFY_TOKEN:
        logger.info("Webhook verificado exitosamente")
        return PlainTextResponse(hub_challenge)
    else:
        logger.error("Token de verificación inválido")
        raise HTTPException(status_code=403, detail="Token de verificación inválido")

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Procesar mensajes entrantes de WhatsApp"""
    try:
        # Obtener datos del webhook
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"Webhook recibido: {json.dumps(data, indent=2)}")
        
        # Validar estructura del webhook
        if "entry" not in data:
            logger.warning("Webhook sin entry, posiblemente notificación de estado")
            return {"status": "ignored"}
        
        # Procesar cada entrada
        for entry in data["entry"]:
            if "changes" not in entry:
                continue
                
            for change in entry["changes"]:
                if change.get("field") != "messages":
                    continue
                
                # Procesar mensajes
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message_data in messages:
                    # Procesar mensaje en paralelo (no bloquea otros mensajes)
                    #asyncio.create_task(process_single_message(message_data, value))
                    print(message_data)
        return {"status": "received"}
        
    except json.JSONDecodeError:
        logger.error("Error decodificando JSON del webhook")
        raise HTTPException(status_code=400, detail="JSON inválido")
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ===== PROCESAMIENTO DE MENSAJES =====

#async def process_single_message(message_data: dict, webhook_value: dict):
#    """Procesa un solo mensaje de WhatsApp de forma asíncrona"""
#    try:
#        # Extraer información básica del webhook
#        message = extract_message_info(message_data, webhook_value)
#        
#        logger.info(f"Procesando mensaje de {message.from_number}: {message.message_type}")
#        
#        # Validar mensaje y enviar respuesta de error si es inválido
#        if not await message_handler.validate_message(message): 
#            logger.warning(f"Mensaje inválido o no soportado: {message.message_type}")
#            validation_msg = "❌ Tipo de mensaje no soportado o datos incompletos"
#            await whatsapp_service.send_message(message.from_number, validation_msg)
#            return
#
#        # Procesar mensaje completo (análisis + resultado + respuesta automática)
#        await message_handler.process_message(message)
#        
#        logger.info(f"Mensaje procesado exitosamente: {message.message_id}")
#        
#    except ValueError as e:
#        # Error de validación o tipo no soportado
#        logger.error(f"Error de validación en mensaje: {e}")
#        # MessageHandler ya envió respuesta de validación
#    except Exception as e:
#        # Error general de procesamiento
#        logger.error(f"Error procesando mensaje individual: {e}")
#        # MessageHandler ya envió respuesta de error
#

# ===== PUNTO DE ENTRADA =====

if __name__ == "__main__":
    # Para desarrollo local
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=config.ENVIRONMENT == "development",
        log_level="info"
    )
