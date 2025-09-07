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
            "nombre": null,
            "informacion_completa": false,
            "campos_faltantes": [],
            "detalles": {
                "tipo_animal": null,
                "edad": no puede estar en null estimar la edad del animal en base a la foto ejemplo 3 meses 8 años(no tiene q ser exacta si no un estimado en base a la foto, si no lo podes estimar explicar porque ?),
                "condicion_de_salud_inicial": null,
                "color_de_pelo": [
                 { "color": "color1", "porcentaje": porcentaje color1 },
                 { "color": "color2", "porcentaje": porcentaje color2 }
                ],
                "ubicacion": "lugar donde fue encontrado",
                "cambio_estado": {
                "ubicacion_id": 1,
                "estado_id": 1,
                "persona": null,
                "tipo_relacion_id": 1
                }
            }
        }
        REGLAS GENERALES
        - Extrae TODO lo disponible de texto e imagen.  
        - "informacion_completa" = true si pudiste completar todos los campos del json.
        -"campos_faltantes": el nombre de los campos del json q no pudiste completar con la informacion de la imagen y texto,
 
        EDAD:
        -Estimá la edad del animal en años o meses no tiene q ser exacta si no un estimado en base a la foto, si no lo podes estimar explicar porque ? 
        COLOR_Pelo:
        - Describe como arreglo de 1 a 3 objetos { "color": "<nombre>", "porcentaje": <0-100> } sumando ≈100.
        - Prefiere nombres simples: "gris", "blanco", "negro", "marrón", "atigrado", "bicolor", etc.

        CAMBIO_ESTADO - campos requeridos (se puede incluir en detalles cuando es un nuevo_rescate o solo cuendo es un cambio de estado de un animal ya rescatado):
        - ubicacion_id: 1=Refugio, 2=Transito, 3=Veterinaria, 4=Hogar_adoptante
        - estado_id: 1=Perdido, 2=En_Tratamiento, 3=En_Adopción, 5=Adoptado, 6=Fallecido
        - persona: nombre o cuenta de quien adopta/transita
        - tipo_relacion_id: 1=Adoptante, 2=Transitante, 3=Veterinario, 4=Voluntario, 5=Interesado

        VISITA_VET - Campos requeridos:
        - nombre (debe estar en el mensaje)
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
        """    

    async def analyze_multimodal(self, content_list: list) -> AIAnalysis:
        """Analiza contenido multimodal (texto, imagen, audio) usando GPT-4"""
        try:
            # Log del contenido que se va a analizar 
            logger.info(f"Analizando contenido con IA")
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.rescue_prompt},
                    {"role": "user", "content": content_list}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content.strip()
            analysis_data = json.loads(result)
                        
            # Crear análisis con los datos recibidos
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("nombre"),
                detalles=analysis_data.get("detalles", {})
            )
            
            # Agregar campos de validación
            analysis.informacion_completa = analysis_data.get("informacion_completa")
            analysis.campos_faltantes = analysis_data.get("campos_faltantes", [])
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON: {e}")
            return self._create_fallback_analysis("contenido multimodal", "Error de parsing JSON")
        except Exception as e:
            logger.error(f"Error en análisis multimodal: {e}")
            return self._create_fallback_analysis("contenido multimodal", str(e))
    
    async def audio_to_text(self, audio_file: bytes) -> str:
        """Convierte audio a texto usando Whisper de OpenAI"""
        try:
            logger.info(f"Transcribiendo audio con Whisper... {audio_file}")
                         
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
     