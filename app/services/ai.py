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
Debes clasificar el mensaje en uno de estos tipos y extraer toda la información disponible en la imagen y en el texto.

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
   - categoria_id (1=Veterinario, 2=Alimento, 3=Piedritas, 4=Limpieza, 5=Medicamentos, 6=Transporte, 7=Otros)
   Campos opcionales:
   - descripcion (en que se gastó, detalles adicionales si hay)
   - proveedor (establecimiento u otro)
   - nombre (del animal, solo si se especifica)
   - responsable (quien pagó el gasto)	
   - forma_de_pago

5. CONSULTA - Pregunta general
   Campos opcionales en detalles:
   - tema (sobre qué pregunta)
   - respuesta_sugerida (si puedes dar respuesta básica)

REGLAS ESPECÍFICAS POR CAMPO:

NOMBRE:
- Siempre es el nombre del animal
- Si no se menciona en texto ni aparece en imagen, usar null
- Para GASTO es opcional (null si no se especifica)

EDAD:
- PRIORIDAD 1: Si el texto menciona edad en días, convertir a formato "X meses" o "X años"
  Ejemplos: "50 días" → "2 meses", "400 días" → "1 año"
- PRIORIDAD 2: Si hay foto, estimar edad basándote en tamaño, proporciones, dentición visible
- PRIORIDAD 3: Si hay descripción (cachorro/adulto/senior), usar estimación general
- Si no hay ninguna información, explicar por qué no puedes estimar en el campo
- Solo marcar como faltante si literalmente no tienes foto NI descripción NI mención

UBICACION: 
- PRIORIDAD 1: Ubicación explícita del rescate
- PRIORIDAD 2: Cualquier mención geográfica en contexto del rescate (ej. "las mamas de Ezeiza" → "Ezeiza")
- PRIORIDAD 3: Referencias indirectas (ej. "barrio del rescatista")
- Solo marcar como faltante si no hay ninguna referencia geográfica en absoluto

CONDICION_DE_SALUD_INICIAL: 
- COMBINAR toda la información disponible de múltiples fuentes:
  * Información médica explícita (vacunas, desparasitación, tratamientos)
  * Contexto del rescate (ej. "madre desnutrida" afecta a cachorros)
  * Observación de la foto (heridas visibles, estado del pelaje, expresión)
  * Menciones de síntomas o comportamientos
- Crear una descripción completa e integrada
- Solo marcar como faltante si no hay foto NI ninguna mención de salud

COLOR_DE_PELO:
- Array de 1-3 objetos: {"color": "nombre", "porcentaje": número}
- Porcentajes deben sumar ≈100
- Nombres simples: "negro", "blanco", "gris", "marrón", "beige", "crema", "atigrado", etc.
- PRIORIDAD 1: Si hay foto, analizar y completar siempre
- PRIORIDAD 2: Descripción en texto
- Solo marcar como faltante si no hay foto NI descripción

CAMBIO_ESTADO:
    UBICACION_ID:
    - Analizar el texto para determinar ubicación actual
    - Si alguien "rescató y se ocupa del animal" → inferir ubicacion_id: 2 (Tránsito)
    - Si menciona "refugio" → 1
    - Si menciona "veterinaria" o "clínica" → 3
    - Si menciona "adoptante" o "nuevo hogar" → 4
    
    ESTADO_ID:
    - Si hay llamada a adopción ("en adopción", "busca hogar") → 3 (En_Adopción)
    - Si menciona tratamiento veterinario activo → 2 (En_Tratamiento)
    - Si dice "adoptado" → 5 (Adoptado)
    - Analizar contexto completo del mensaje
    
    TIPO_RELACION_ID: 
    - Analizar la relación de la persona mencionada:
      * Rescató y busca adoptante → 2 (Transitante)
      * Adoptó al animal → 1 (Adoptante)
      * Es veterinario/a → 3 (Veterinario)
      * Es voluntario/rescatista → 4 (Voluntario)
      * Pregunta por adopción → 5 (Interesado)
    
    PERSONA:
    - Incluir nombre completo si se menciona (ej. "Elena y su familia")
    - Si solo hay cuenta de red social, usar esa
    - Si hay múltiples personas, incluirlas todas

INFORMACIÓN_COMPLETA Y CAMPOS_FALTANTES - REGLAS CRÍTICAS:

DEFINICIÓN DE "CAMPO FALTANTE":
- Un campo es faltante SOLO si quedó en null o vacío después de intentar TODAS estas fuentes:
  1. Información EXPLÍCITA en el texto
  2. Información VISIBLE en la imagen
  3. Inferencias LÓGICAS del contexto
  4. Estimaciones RAZONABLES basadas en datos parciales

CRITERIO DE COMPLETADO:
- Si completaste un campo por CUALQUIERA de los 4 métodos anteriores → NO es faltante
- campos_faltantes = solo aquellos que literalmente quedaron en null
- informacion_completa: true cuando TODOS los campos obligatorios tienen algún valor
- informacion_completa: false solo cuando al menos un campo obligatorio quedó en null

EJEMPLOS DE COMPLETADO VÁLIDO:
- Edad: "50 días" en texto → convertir a "2 meses" → CAMPO COMPLETO
- Color: foto disponible → analizar visualmente → CAMPO COMPLETO  
- Ubicación: "de Ezeiza" en contexto → usar "Ezeiza" → CAMPO COMPLETO
- Salud: "desparasitado" + "madre desnutrida" → combinar → CAMPO COMPLETO
- Persona: "Elena y su familia" → usar texto completo → CAMPO COMPLETO

IMPORTANTE: El objetivo es MAXIMIZAR la información extraída. 
Solo marcar campos como faltantes cuando literalmente no existe forma de obtener ese dato.

TIPO_REGISTRO:
- Si no puedes determinar el tipo con certeza, usar null
- Analizar contexto completo antes de decidir
- Indicadores clave:
  * "Rescatamos", "encontramos", fotos de cachorros → NUEVO_RESCATE
  * "Fue adoptado", "está en tránsito ahora" → CAMBIO_ESTADO
  * "Fue al veterinario", "le diagnosticaron" → VISITA_VET
  * "Gastamos", "compramos", montos → GASTO
  * "¿Cómo hago para...?", preguntas → CONSULTA

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
        "condicion_de_salud_inicial": "Herida en pata trasera, desparasitado, estado general bueno",
        "ubicacion": "Villa Fiorito",
        "cambio_estado": {
            "ubicacion_id": 2,
            "estado_id": 2,
            "persona": "María Rescatista",
            "tipo_relacion_id": 4
        }
    }
}

Ejemplo 2 - Nuevo rescate con conversión de edad:
{
    "tipo_registro": "nuevo_rescate",
    "nombre": "Luna",
    "informacion_completa": true,
    "campos_faltantes": [],
    "detalles": {
        "tipo_animal": "gato",
        "edad": "2 meses",
        "color_de_pelo": [
            {"color": "gris", "porcentaje": 100}
        ],
        "condicion_de_salud_inicial": "Cachorro de 45 días, desparasitado, buena condición general visible en foto",
        "ubicacion": "Flores",
        "cambio_estado": {
            "ubicacion_id": 2,
            "estado_id": 3,
            "persona": "Carlos y familia",
            "tipo_relacion_id": 2
        }
    }
}

Ejemplo 3 - Gasto con información incompleta (caso real de faltantes):
{
    "tipo_registro": "gasto",
    "nombre": null,
    "informacion_completa": false,
    "campos_faltantes": ["fecha", "categoria_id"],
    "detalles": {
        "monto": 1500,
        "descripcion": "medicamentos",
        "fecha": null,
        "categoria_id": null
    }
}

Ejemplo 4 - Cambio de estado completo:
{
    "tipo_registro": "cambio_estado",
    "nombre": "Parche",
    "informacion_completa": true,
    "campos_faltantes": [],
    "detalles": { 
        "ubicacion_id": 4,
        "estado_id": 5,
        "persona": "Familia Rodríguez",
        "tipo_relacion_id": 1
    }
}

INSTRUCCIONES FINALES:
1. Analiza TODO el contenido disponible (texto + imagen) completamente
2. Extrae TODA la información posible usando los 4 métodos de completado
3. Convierte formatos cuando sea necesario (días → meses, descripciones → IDs)
4. Combina información de múltiples fuentes para campos completos
5. Solo marca como faltante lo que literalmente no pudiste obtener de ninguna forma
6. Responde SOLO con el JSON, sin explicaciones adicionales fuera del JSON
7. Mantén la estructura exacta especificada
8. Si hay dudas sobre el tipo, analiza el contexto completo antes de decidir
"""

    async def analyze_multimodal(self, content_list: list) -> AIAnalysis:
        """Analiza contenido multimodal (texto, imagen, audio) usando GPT-4"""
        try:
            # Log del contenido que se va a analizar 
            logger.info(f"Analizando contenido con IA")
            
            response = await self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {"role": "system", "content": self.rescue_prompt},
                    {"role": "user", "content": content_list}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
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
     