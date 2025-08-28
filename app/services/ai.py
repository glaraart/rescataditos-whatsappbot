import os
from app.config import settings
import json
import logging
import openai
from app.models.whatsapp import AIAnalysis 
from openai import AsyncOpenAI
import asyncio, os, tempfile

logger = logging.getLogger(__name__)
class AIService:
    """Servicio para análisis de IA usando OpenAI"""
    
    def __init__(self):
        
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        
        openai.api_key = self.api_key
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Prompt base para análisis de rescate
        self.rescue_prompt = """
        Analiza el siguiente mensaje y clasifícalo según estos tipos:

        TIPOS DISPONIBLES:
        - nuevo_rescate: Reporte de un animal que fue rescatado
        - cambio_estado: Actualización del estado de un animal
        - visita_vet: Información sobre visita veterinaria
        - gasto: Registro de gastos relacionados con rescate
        - consulta: Pregunta general o información

        RESPONDE EN JSON con esta estructura exacta:
        {
            "tipo_registro": "nuevo_rescate",
            "animal_nombre": "nombre del animal si se menciona",
            "confianza": 0.85,
            "detalles": {
                "ubicacion": "lugar del rescate",
                "estado_animal": "descripción del estado",
                "urgencia": "alta/media/baja",
                "contacto": "información de contacto si existe"
            }
        }

        Para cambio_estado incluye: nuevo_estado, fecha
        Para visita_vet incluye: veterinario, fecha, diagnostico, tratamiento
        Para gasto incluye: monto, concepto, fecha
        Para consulta incluye: tema, respuesta_sugerida
        """
    
    async def analyze_text(self, text: str) -> AIAnalysis:
        """Analiza texto usando OpenAI y retorna análisis estructurado"""
        try:
            logger.info(f"Analizando texto: {text[:100]}...")
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.rescue_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parsear respuesta JSON
            content = response.choices[0].message.content
            analysis_data = json.loads(content)
            
            # Validar y crear objeto AIAnalysis
            return AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"),
                confianza=float(analysis_data.get("confianza", 0.5)),
                detalles=analysis_data.get("detalles", {})
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de OpenAI: {e}")
            return self._create_fallback_analysis(text, "Error de parsing JSON")
        except Exception as e:
            logger.error(f"Error en análisis de texto: {e}")
            return self._create_fallback_analysis(text, str(e))
    
    async def ogg_opus_to_wav_bytes(self, ogg_bytes: bytes) -> bytes:
        """Convierte OGG/Opus a WAV (16kHz, mono) en memoria."""
        def _convert():
            audio = AudioSegment.from_file(io.BytesIO(ogg_bytes), format="ogg")
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            out = io.BytesIO()
            audio.export(out, format="wav")
            return out.getvalue()

        # Pydub/ffmpeg es bloqueante; ejecútalo fuera del event loop
        return await asyncio.to_thread(_convert)

    async def audio_to_text(self, audio_bytes: bytes, *, assume_ogg=True, language="es", use_model="gpt-4o-mini-transcribe") -> str:
        """
        Transcribe audio usando el endpoint CORRECTO de transcripción.
        - Si assume_ogg=True, convierte a WAV antes de enviar.
        """
        # 1) Normaliza a WAV si viene de WhatsApp (OGG/Opus)
        wav_bytes = await self.ogg_opus_to_wav_bytes(audio_bytes) if assume_ogg else audio_bytes

        # 2) Abrir un file-like con nombre y extensión correctos (ayuda al SDK a setear el mime)
        wav_buffer = io.BytesIO(wav_bytes)
        wav_buffer.name = "audio.wav"  # <- importante: filename “realista”

        # 3) Llamar al endpoint de TRANSCRIPCIÓN (NO al de chat)
        resp = await client.audio.transcriptions.create(
            model=use_model,            # "gpt-4o-mini-transcribe" o "whisper-1"
            file=wav_buffer,            # file-like con nombre
            language=language,
            response_format="text"      # devuelve string directo
        )
        # Si pides "text", resp ya es str
        return resp.strip() if isinstance(resp, str) else getattr(resp, "text", "").strip()
    
    async def analyze_image_and_text(self, image_url: str, text: str = "") -> AIAnalysis:
        """Analiza imagen y texto opcional usando GPT-4 Vision"""
        try:
            logger.info(f"Analizando imagen: {image_url}")
            
            # Prompt específico para imágenes de rescate
            image_prompt = f"""
            {self.rescue_prompt}
            
            ANALIZA LA IMAGEN junto con el texto adicional (si existe): "{text}"
            
            Busca en la imagen:
            - Animales que necesiten rescate
            - Estado de salud visible
            - Ubicación o contexto
            - Urgencia de la situación
            
            Combina la información visual con el texto para dar el análisis más preciso.
            """
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": image_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parsear respuesta JSON
            content = response.choices[0].message.content
            analysis_data = json.loads(content)
            
            # Crear análisis con información de imagen
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"),
                confianza=float(analysis_data.get("confianza", 0.5)),
                detalles=analysis_data.get("detalles", {})
            )
            
            # Agregar metadata de imagen
            analysis.detalles["imagen_analizada"] = True
            analysis.detalles["imagen_url"] = image_url
            if text:
                analysis.detalles["texto_adicional"] = text
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de análisis de imagen: {e}")
            return self._create_fallback_analysis(f"Imagen: {image_url} + Texto: {text}", "Error de parsing JSON")
        except Exception as e:
            logger.error(f"Error analizando imagen: {e}")
            return self._create_fallback_analysis(f"Imagen: {image_url} + Texto: {text}", str(e))
    
    def _create_fallback_analysis(self, original_content: str, error_message: str) -> AIAnalysis:
        """Crea análisis de respaldo cuando falla el procesamiento principal"""
        return AIAnalysis(
            tipo_registro="consulta",
            animal_nombre=None,
            confianza=0.0,
            detalles={
                "error": error_message,
                "contenido_original": original_content[:200],
                "procesamiento": "fallback"
            }
        )
     