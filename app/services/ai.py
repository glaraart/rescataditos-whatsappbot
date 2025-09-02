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
        Eres un asistente que ayuda a unas rescatistas a registrar informacion desde fotos y/o texto según estos tipos:

        TIPOS DISPONIBLES:
        - nuevo_rescate: Reporte de un animal que fue rescatado
        - cambio_estado: Actualización del estado de un animal
        - visita_vet: Información sobre visita veterinaria
        - gasto: Registro de gastos relacionados con rescate
        - consulta: Pregunta general o información

        IMPORTANTE: Extrae TODA la información disponible en el mensaje. Si un campo no se menciona o no está claro, coloca null en lugar de inventar información.

        RESPONDE EN JSON con esta estructura exacta:
        {
            "tipo_registro": "nuevo_rescate", 
            "animal_nombre": "nombre del animal si se menciona o null",
            "informacion_completa": false,
            "campos_faltantes": ["lista de campos que faltan o están vacíos"],
            "detalles": { 
                "tipo_animal": "perro o null si no se especifica",
                "edad": "2 años o null si no se menciona",
                "condicion_salud": "describir cómo fue recibido o null",
                "color_pelo": [
                    { "color": "blanco", "porcentaje": 70 },
                    { "color": "negro", "porcentaje": 30 }
                ] o null si no se describe,
                "ubicacion": "lugar del rescate específico o null",
                "cambio_estado": { 
                    "ubicacion": 1,
                    "estado": 2,
                    "persona": "nombre de la persona o null",
                    "relacion": 1
                } o null según corresponda
            }
        }

        REGLAS ESPECÍFICAS POR TIPO:

        NUEVO_RESCATE - Campos requeridos:
        - tipo_animal (perro, gato, etc.)
        - ubicacion (dirección específica)
        - condicion_salud (herido, enfermo, sano, etc.)
        - cambio_estado con ubicacion=1 (Refugio) y estado=1 (Perdido) como mínimo
        
        CAMBIO_ESTADO - Solo incluir cambio_estado en detalles:
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

        VALIDACIÓN:
        - Marca "informacion_completa": true solo si TODOS los campos requeridos tienen valores válidos (no null)
        - En "campos_faltantes" lista exactamente qué información específica falta
        - NO inventes información que no esté en el mensaje
        - Sé específico: en lugar de "ubicacion" pon "ubicacion_especifica_del_rescate"

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
                max_tokens=1000
            )
            # Parsear respuesta JSON - limpiar bloques de código si existen
            content = response.choices[0].message.content
            
            # Limpiar backticks y bloques de código
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remover ```json
            elif content.startswith("```"):
                content = content[3:]   # Remover ```
            if content.endswith("```"):
                content = content[:-3]  # Remover ``` del final
            content = content.strip()
            
            analysis_data = json.loads(content)
            print("Análisis de IA:", analysis_data)
            
            # Validar y crear objeto AIAnalysis con los nuevos campos
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"), 
                detalles=analysis_data.get("detalles", {})
            )
            
            # Agregar campos de validación como atributos adicionales
            analysis.informacion_completa = analysis_data.get("informacion_completa", False)
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
            logger.info(f"Analizando texto: {text[:100]}...")
            content_aux = []
            # Prompt específico para imágenes de rescate
            system_prompt = self.rescue_prompt
            base64_image = base64.b64encode(image_bytes).decode()
            content_aux.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
            
            # Resto igual, pero usar 'content' en lugar del objeto hardcodeado
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_aux}  # ← USAR LA LISTA DINÁMICA
                ],
                max_tokens=800  # Aumentar para múltiples imágenes
            )
            result= response.choices[0].message.content.strip() 
             
            
            # Limpiar backticks y bloques de código
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]  # Remover ```json
            elif result.startswith("```"):
                result = result[3:]   # Remover ```
            if result.endswith("```"):
                result= result[:-3]  # Remover ``` del final
            result = result.strip()
            
            analysis_data = json.loads(result)
            
            # Crear análisis con información de imagen
            analysis = AIAnalysis(
                tipo_registro=analysis_data.get("tipo_registro", "consulta"),
                animal_nombre=analysis_data.get("animal_nombre"),
                detalles=analysis_data.get("detalles", {})
            )
            
            # Agregar metadata de imagen
            analysis.detalles["imagen_analizada"] = True
            analysis.detalles["imagen_url"] = image_bytes
            if text:
                analysis.detalles["texto_adicional"] = text
            
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
     