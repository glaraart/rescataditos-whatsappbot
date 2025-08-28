import os
from app.config import settings
import json
import logging
from typing import Dict, Any, Optional
import openai
from app.models.whatsapp import AIAnalysis 
logger = logging.getLogger(__name__)
class AIService:
    """Servicio para análisis de IA usando OpenAI"""
    
    def __init__(self):
        
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        openai.api_key = self.api_key
        
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
    
    async def audio_to_text(self, audio_file: bytes) -> str:
        """Convierte audio a texto usando Whisper de OpenAI"""
        try:
            logger.info("Transcribiendo audio con Whisper...")
            
            # Guardar archivo temporal para Whisper
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_file)
                tmp_file_path = tmp_file.name
            
            # Transcribir con Whisper
            with open(tmp_file_path, "rb") as audio:
                response = await openai.Audio.atranscribe(
                    model="whisper-1",
                    file=audio,
                    language="es"  # Español
                )
            
            # Limpiar archivo temporal
            os.unlink(tmp_file_path)
            
            text = response.text.strip()
            logger.info(f"Audio transcrito: {text[:100]}...")
            
            return text
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            raise Exception(f"Error en transcripción: {e}")
    
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
     