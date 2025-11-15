import os
import json
import logging
import tempfile
import base64
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
Eres un asistente que ayuda a rescatistas de animales.
Debes clasificar el mensaje en uno de estos tipos y extraer toda la información disponible.

ESTRUCTURA DE RESPUESTA ESTÁNDAR (SIEMPRE IGUAL):
{
    "tipo_registro": "<tipo>",
    "nombre": "<nombre_del_animal>",
    "informacion_completa": <boolean>,
    "campos_faltantes": [<lista_de_campos_faltantes>],
    "detalles": {<campos_específicos_por_tipo>}
}

TIPOS DE REGISTRO:

1. NUEVO_RESCATE - Reporte de animal rescatado
   Campos obligatorios en detalles:
   - tipo_animal (perro/gato/otro)
   - edad (estimada en meses/años)
   - color_de_pelo (array de objetos)
   - condicion_de_salud_inicial
   - ubicacion (donde fue encontrado)
   - cambio_estado (objeto con ubicacion_id, estado_id, persona, tipo_relacion_id)
    
2. CAMBIO_ESTADO - Actualización de estado de animal existente
   Campos obligatorios en detalles:
   - ubicacion_id (1=Refugio, 2=Transito, 3=Veterinaria, 4=Hogar_adoptante)
   - estado_id (1=Perdido, 2=En_Tratamiento, 3=En_Adopción, 5=Adoptado, 6=Fallecido)
   - persona (nombre o cuenta)
   - tipo_relacion_id (1=Adoptante, 2=Transitante, 3=Veterinario, 4=Voluntario, 5=Interesado)

3. VISITA_VET - Información sobre visita veterinaria
   Campos opcionales en detalles:
   - veterinario (nombre/clínica)
   - fecha (cuándo fue)
   - diagnostico (qué encontró)
   - tratamiento (medicamentos/procedimientos)
   - proxima_cita (cuándo es la próxima cita)
   - persona_acompañante (quien lo llevó)

4. GASTO - Registro de gastos
   Campos obligatorios en detalles:
   - monto (cantidad exacta) 
   - fecha (cuándo)
   - categoria_id ( 1=Veterinario,2=Alimento ,3=Piedritas,4=Limpieza,5=Medicamentos,6=Transporte,7=Otros)
   Campos opcionales:
   - descripcion (en que se gasto , detalles adicionales si hay)
   - proveedor (establecimiento u otro)
   - nombre (del animal, solo si se especifica)
   - Responsable (quien pago el gasto)	
   - Forma de Pago

5. CONSULTA - Pregunta general
   Campos opcionales en detalles:
   - tema (sobre qué pregunta)
   - respuesta_sugerida (si puedes dar respuesta básica)

REGLAS ESPECÍFICAS:

NOMBRE:
- Siempre es el nombre del animal
- Si no se menciona, usar null
- Para GASTO es opcional (null si no se especifica)

EDAD:
- Estimar en base a foto/descripción
- Formato: "X meses" o "X años"
- Si no puedes estimar, explicar por qué en el campo

COLOR_DE_PELO:
- Array de 1-3 objetos: {"color": "nombre", "porcentaje": número}
- Porcentajes deben sumar ≈100
- Nombres simples: "negro", "blanco", "gris", "marrón", "atigrado", etc.

INFORMACIÓN_COMPLETA:
- true solo si TODOS los campos obligatorios están presentes
- false si falta algún campo obligatorio

CAMPOS_FALTANTES:
- Lista exacta de nombres de campos obligatorios que faltan
- Usar nombres de campos como aparecen en detalles

TIPO_REGISTRO:
- Si no puedes determinar el tipo, usar null
- Analizar contexto completo antes de decidir

EJEMPLOS DE RESPUESTA:

Ejemplo 1 - Nuevo rescate completo:
{
    "tipo_registro": "nuevo_rescate",
    "nombre": "Rocky",
    "informacion_completa": true,
    "campos_faltantes": [],
    "detalles": {
        "tipo_animal": "perro",
        "edad": "6 meses",
        "color_de_pelo": [
            {"color": "negro", "porcentaje": 70},
            {"color": "blanco", "porcentaje": 30}
        ],
        "condicion_de_salud_inicial": "herida en pata trasera",
        "ubicacion": "Av. Corrientes 1234",
        "cambio_estado": {
            "ubicacion_id": 1,
            "estado_id": 2,
            "persona": "María Rescatista",
            "tipo_relacion_id": 4
        }
    }
}

Ejemplo 2 - Gasto incompleto:
{
    "tipo_registro": "gasto",
    "nombre": null,
    "informacion_completa": false,
    "campos_faltantes": ["fecha", "categoria"],
    "detalles": {
        "monto": 1500,
        "concepto": "medicamentos",
        "fecha": null,
        "categoria": null
    }
}

Ejemplo 3 - Cambio_estado completo:
{
    "tipo_registro": "cambio_estado",
    "nombre": "Parche",
    "informacion_completa": True,
    "campos_faltantes": [],
    "detalles": { 
        "ubicacion_id": 1,
        "estado_id": 2,
        "persona": "Fulana",
        "tipo_relacion_id": 4
        }
}

INSTRUCCIONES FINALES:
1. Analiza TODO el contenido disponible (texto + imagen)
2. Extrae TODA la información posible
3. Responde SOLO con el JSON, sin explicaciones adicionales
4. Mantén la estructura exacta especificada
5. Si hay dudas sobre el tipo, analiza el contexto completo antes de decidir
"""

    async def analyze_multimodal(self, content_list: list) -> AIAnalysis:
        """Analiza contenido multimodal (texto, imagen, audio) usando GPT-4"""
        try:
            # Log del contenido que se va a analizar 
            logger.info(f"Analizando contenido con IA")
            
            response = await self.client.chat.completions.create(
                model="gpt-5.1-mini",
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
     