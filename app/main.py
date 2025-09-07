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
from fastapi.responses import PlainTextResponse
from app.config import settings
# ===== HANDLERS =====
from app.handlers.message_handler import MessageHandler 

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
 
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ===== INICIALIZAR FASTAPI =====

app = FastAPI(
    title="Sistema WhatsApp 101 Rescataditos",
    description="API para procesar mensajes de WhatsApp de 101 Rescataditos",
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None
)
 
# ===== WEBHOOK WHATSAPP =====

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """Verificación del webhook de WhatsApp"""
    logger.info(f"Verificación webhook: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
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
        
        # Procesar cada entrada
        for entry in data["entry"]:
            for change in entry["changes"]:
                for message_data in change.get("value", {}).get("messages", []):
                    # Procesar mensaje en paralelo (no bloquea otros mensajes)
                    asyncio.create_task(process_single_message(message_data))
        return {"status": "received"}
        
    except json.JSONDecodeError:
        logger.error(f"Error decodificando JSON del webhook: {json.dumps(data, indent=2)}")
        raise HTTPException(status_code=400, detail="JSON inválido")
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ===== PROCESAMIENTO DE MENSAJES =====
async def process_single_message(message_data: dict):
    """Procesa un solo mensaje de WhatsApp de forma asíncrona"""
        # Procesar mensaje completo (análisis + resultado + respuesta automática)
    message_handler = MessageHandler()    
    await message_handler.process_message(message_data)
 

# ===== PUNTO DE ENTRADA =====

if __name__ == "__main__":
    # Para desarrollo local
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=ENVIRONMENT == "development",
        log_level="info"
    )
