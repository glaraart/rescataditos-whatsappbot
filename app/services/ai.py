import os
import json
import logging
import tempfile
from app.config import settings
from app.models.whatsapp import AIAnalysis 
from openai import AsyncOpenAI
import base64

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
        Eres un asistente que ayuda a unas rescatistas a registrar informacion analizando fotos de animales y/o texto según estos tipos:

        TIPOS DISPONIBLES:
        - nuevo_rescate: Reporte de un animal que fue rescatado
        - cambio_estado: Actualización del estado de un animal
        - visita_vet: Información sobre visita veterinaria
        - gasto: Registro de gastos relacionados con rescate
        - consulta: Pregunta general o información

        IMPORTANTE: Extrae TODA la información disponible en el mensaje y/o en la foto.

        RESPONDE EN JSON con esta estructura exacta:
        {
            "tipo_registro": "nuevo_rescate",
            "animal_nombre": null,
            "informacion_completa": false,
            "campos_faltantes": [],
            "detalles": {
                "tipo_animal": null,
                "edad": no puede estar en null estimar la edad del animal en base a la foto ejemplo 3 meses 8 años,
                "condicion_salud": null,
                "color_pelo": [
                 { "color": "color1", "porcentaje": porcentaje color1 },
                 { "color": "color2", "porcentaje": porcentaje color2 }
                ],
                "ubicacion": "lugar donde fue encontrado",
                "cambio_estado": {
                "ubicacion": 1,
                "estado": 1,
                "persona": null,
                "relacion": 1
                }
            }
        }
        REGLAS GENERALES
        - Extrae TODO lo disponible de texto e imagen.  
        - "informacion_completa" = true SOLO si todos los campos requeridos están presentes y no son null.
 
        EDAD:
        -Estimá la edad del animal en años o meses.
        COLOR_Pelo:
        - Describe como arreglo de 1 a 3 objetos { "color": "<nombre>", "porcentaje": <0-100> } sumando ≈100.
        - Prefiere nombres simples: "gris", "blanco", "negro", "marrón", "atigrado", "bicolor", etc.

        CAMBIO_ESTADO - campos requeridos (se puede incluir en detalles cuando es un nuevo_rescate o solo cuendo es un cambio de estado de un animal ya rescatado):
        - ubicacion: 1=Refugio, 2=Transito, 3=Veterinaria, 4=Hogar_adoptante
        - estado: 1=Perdido, 2=En_Tratamiento, 3=En_Adopción, 5=Adoptado, 6=Fallecido
        - persona: nombre o cuenta de quien adopta/transita
        - relacion: 1=Adoptante, 2=Transitante, 3=Veterinario, 4=Voluntario, 5=Interesado

        VISITA_VET - Campos requeridos:
        - animal_nombre (debe estar en el mensaje)
        - veterinario (nombre/clínica)
        - fecha (cuándo fue)
        - diagnostico (qué encontró)
        - tratamiento (medicamentos/procedimientos)
        - costo (cuánto costó)
        - persona_acompanante (quien lo llevó)

        GASTO - Campos requeridos:
        - monto (cantidad exacta)
        - concepto (en qué se gastó)
        - fecha (cuándo)
        - categoria (veterinario, comida, transporte, etc.)

        CONSULTA - Campos opcionales:
        - tema (sobre qué pregunta)
        - respuesta_sugerida (si puedes dar una respuesta básica)
        
        EJEMPLOS:
        Mensaje: "Encontré un perro en Villa Fiorita"
        → Falta: condicion_salud, edad, color_pelo, cambio_estado completo
        
        Mensaje: "Rex fue adoptado por María"
        → Tipo: cambio_estado, Falta: fecha_adopcion, relacion_especifica
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
                max_tokens=1000,
                response_format={"type":"json_object"}
            )
            # Parsear respuesta JSON - limpiar bloques de código si existen
            content = response.choices[0].message.content
            
         
            analysis_data = json.loads(content)
            print("Análisis de IA:", analysis_data)
            
            # Validar y crear objeto AIAnalysis con los nuevos campos
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"), 
                detalles=analysis_data.get("detalles", {})
            )
            
            # Agregar campos de validación como atributos adicionales
            analysis.informacion_completa = analysis_data.get("informacion_completa")
            analysis.campos_faltantes = analysis_data.get("campos_faltantes", [])
            
            return analysis
            
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
        
    async def analyze_image_and_text(self, image_bytes, text: str = "") -> AIAnalysis:
        """Analiza imagen y texto opcional usando GPT-4 Vision"""
        try: 
            logger.info(f"Analizando imagen y texto: {text[:100]}...")
            content_aux = []
            # Prompt específico para imágenes de rescate
            system_prompt = self.rescue_prompt
            base64_image = base64.b64encode(image_bytes).decode()
            content_aux=[
                {   "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                },
                {"type": "text", "text": f"Mensaje: {text}"}
                ]
            print ("contexto ai" ,content_aux)
            # Resto igual, pero usar 'content' en lugar del objeto hardcodeado
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_aux}  # ← USAR LA LISTA DINÁMICA
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=800
            )
            print("respuesta ai" , response)
            result= response.choices[0].message.content.strip()             
            analysis_data = json.loads(result)
            
            # Crear análisis con información de imagen
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"),
                detalles=analysis_data.get("detalles", {})
            )
            # Agregar campos de validación como atributos adicionales
            analysis.informacion_completa = analysis_data.get("informacion_completa")
            analysis.campos_faltantes = analysis_data.get("campos_faltantes", [])
                    
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de análisis de imagen: {e}")
            return self._create_fallback_analysis(f"Error de parsing JSON")
        except Exception as e:
            logger.error(f"Error analizando imagen: {e}")
            return self._create_fallback_analysis(str(e))
    
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
     