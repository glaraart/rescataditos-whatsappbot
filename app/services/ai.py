import os
import json
import logging
import tempfile
from app.config import settings
from app.models.whatsapp import AIAnalysis 
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
class AIService:
    """Servicio para análisis de IA usando OpenAI"""
    
    def __init__(self):
        
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
            "nombre_animal": "nombre del animal si se menciona",
            "detalles": { 
                "tipo_animal": "perro",
                "edad": "2 años",
                "condicion_salud": "describir cómo fue recibido",
                "color_pelo": [
                    { "color": "blanco", "porcentaje": 70 },
                    { "color": "negro", "porcentaje": 30 }
                ],
                "ubicacion": "lugar del rescate por ejemplo Villa Fiorito"
            },
            "cambio_estado": { 
                "ubicacion": 1 Refugio,2 Transito,3 Veterinaria,4 Hogar_adoptante,
                "estado": 1 Perdido,2 En Tratamiento,3 En Adopción,5 Adoptado,6 Fallecido,
                "persona": "nombre de la persona o cuenta de ig que transita o que adopta",
                "relacion": 1 Adoptante,2 Transitante,3 Veterinario,4 Voluntario,5 Interesado
            }

        }
        Si es nuevo_rescate colocar detalles y cambio_estado.
        Si es cambio_estado colocar: solo cambio_estado.
        Para visita_vet en detalles colocar: persona que lo lleva al veterinario
        Para gasto incluye: monto, concepto, fecha
        Para consulta incluye: tema, respuesta_sugerida
        """
    
    async def analyze_text(self, text: str) -> AIAnalysis:
        """Analiza texto usando OpenAI y retorna análisis estructurado"""
        try:
            logger.info(f"Analizando texto: {text[:100]}...")
            
            response = await self.client.chat.completions.create(
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
            print ("analisis" , analysis_data)
            # Validar y crear objeto AIAnalysis
            return AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"), 
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
                        
            # Verificar si parece ser un archivo válido
            if len(audio_file) < 100:
                raise Exception(f"Archivo de audio muy pequeño: {len(audio_file)} bytes")
            
            # Guardar archivo temporal para Whisper
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_file)
                tmp_file_path = tmp_file.name
                    
            # Transcribir con Whisper usando la nueva API
            with open(tmp_file_path, "rb") as audio:
                response = await self.client.audio.transcriptions.create(
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
            
            response = await self.client.chat.completions.create(
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
     