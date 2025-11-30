import json
import random
from app.handlers.message_handler import MessageHandler
from app.models.analysis import RawContent, HandlerResult, ConsultaDetails
from app.services.ai import AIService


class ConsultaHandler(MessageHandler):
    version = "0.1"
    prompt_file = "consulta_prompt.txt"
    details_class = ConsultaDetails

    def __init__(self, ai_service: AIService = None, db_service=None, whatsapp_service=None, confirmation_manager=None):
        super().__init__(ai_service=ai_service, db_service=db_service, whatsapp_service=whatsapp_service, confirmation_manager=confirmation_manager)
        
        # Mensajes variados para alternar
        self.mensajes_ayuda = [
            (
                "👋 ¡Hola! ¿En qué te puedo ayudar?\n\n"
                "Puedo asistirte con:\n\n"
                "🐾 **Nuevo rescate** - Reportar un animal que encontraste\n"
                "💰 **Gastos** - Registrar gastos relacionados con rescates\n"
                "🏥 **Visita veterinaria** - Informar sobre consultas médicas\n"
                "📝 **Cambio de estado** - Actualizar adopción, tránsito o ubicación\n"
                "❓ **Consultas generales** - Preguntas sobre cuidados y procedimientos\n\n"
                "Simplemente escríbeme lo que necesitas y te ayudaré a registrarlo."
            ),
            (
                "¡Hola! 👋 Estoy aquí para ayudarte.\n\n"
                "Puedes contarme sobre:\n\n"
                "🐶 Un **animal que rescataste** y necesitas registrar\n"
                "💵 **Gastos** que realizaste para el cuidado de animales\n"
                "🩺 Una **visita al veterinario** que quieras reportar\n"
                "🏠 **Cambios** como adopciones, tránsitos o ubicaciones\n"
                "💬 **Dudas** sobre cuidados y procedimientos\n\n"
                "¿Qué necesitas hoy?"
            ),
            (
                "👋 ¿Cómo estás? ¿En qué puedo ayudarte?\n\n"
                "Estoy para:\n\n"
                "🆕 Registrar un **nuevo rescate**\n"
                "💳 Anotar **gastos** del rescate\n"
                "⚕️ Guardar info de **visitas veterinarias**\n"
                "✏️ Actualizar **estados** (adopción, tránsito, etc.)\n"
                "🤔 Responder tus **consultas**\n\n"
                "Cuéntame qué necesitas."
            ),
            (
                "¡Hola! 🌟 ¿Qué puedo hacer por ti?\n\n"
                "Opciones disponibles:\n\n"
                "🐕 Reportar un **rescate nuevo**\n"
                "💰 Registrar **gastos** y compras\n"
                "🏥 Informar **consultas veterinarias**\n"
                "📋 Actualizar **estados de animales**\n"
                "❔ Hacer **preguntas** sobre rescates\n\n"
                "Escribe lo que necesites y lo registramos juntos."
            ),
            (
                "👋 ¡Hola! Estoy aquí para ayudarte con los rescataditos.\n\n"
                "¿Qué necesitas hoy?\n\n"
                "🐾 **Rescate** - Informar sobre un animal encontrado\n"
                "💸 **Gasto** - Registrar dinero invertido\n"
                "🩹 **Veterinaria** - Reportar consultas o tratamientos\n"
                "🔄 **Estado** - Cambios de adopción o ubicación\n"
                "💭 **Consulta** - Preguntas generales\n\n"
                "Solo dime qué deseas registrar."
            )
        ]

    async def handle_message_flow(self, phone: str, raw: RawContent, tipo: str, phone_history: list = None):
        """
        Flujo simplificado para consultas: solo responder con ayuda/sugerencias.
        No requiere análisis, validación ni guardado en BD.
        """
        try:
            # Seleccionar mensaje aleatorio
            mensaje_ayuda = random.choice(self.mensajes_ayuda)
            await self.send_message(phone, mensaje_ayuda)
            
        except Exception as e:
            await self.send_error_response(phone, str(e))
