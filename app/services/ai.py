import os
import json
import logging
import tempfile
import re
from typing import Optional
from app.config import settings
from app.models.whatsapp import AIAnalysis
from app.models.analysis import RawContent, ClassificationResult
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AIService:
    """Servicio para análisis de IA usando OpenAI"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        self.client = AsyncOpenAI(api_key=self.api_key)

        # Prompt base para análisis de rescate
        self.rescue_prompt = (
            "Eres un asistente que ayuda a rescatistas de animales.\n"
            "Debes clasificar el mensaje en uno de estos tipos y extraer toda la información disponible en la imagen y en el texto.\n"
            "Responde SOLO con JSON siguiendo las reglas especificadas."
        )

        # directory for prompt templates
        self.prompts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "prompts"))

        # Simple rules for fast classification
        self.rules = [
            ("gasto", [r"\bmonto\b", r"\bpesos\b", r"\$", r"pagamos", r"factura", r"compramos"]),
            ("visita_vet", [r"veterinari", r"veterinario", r"diagnost", r"tratamiento", r"consulta vet"]),
            ("nuevo_rescate", [r"rescat", r"encontr[aeo]", r"cachorr", r"encontramos", r"hallad"]),
            ("cambio_estado", [r"adoptad", r"adopci[oó]n", r"adoptar", r"fallec", r"en tr[áa]nsito", r"transit"]),
        ]

    def _apply_rules(self, text: str) -> Optional[str]:
        """Return a predicted tipo using keyword rules, or None"""
        t = text.lower() if text else ""
        scores = {}
        for label, patterns in self.rules:
            for p in patterns:
                if re.search(p, t):
                    scores[label] = scores.get(label, 0) + 1
        if not scores:
            return None
        return max(scores.items(), key=lambda x: x[1])[0]

    async def classify(self, raw: RawContent) -> ClassificationResult:
        """
        Classify raw content using rules first, then LLM as fallback.
        Considers text AND images for better classification.
        Returns a ClassificationResult with tipo, score, and reasons.
        """
        # 1. try fast rules on text first
        label = self._apply_rules(raw.text)
        if label:
            return ClassificationResult(tipo=label, score=0.8, reasons=["rules"])

        # 2. fallback to LLM classifier prompt with multimodal content (single call)
        try:
            # Load classifier prompt
            template_path = os.path.join(self.prompts_dir, "classifier_prompt.txt")
            with open(template_path, "r", encoding="utf-8") as f:
                classifier_prompt = f.read()
            
            # Build user message with text and images
            user_content = [{"type": "text", "text": raw.text or ""}]
            
            # Add images if available
            if raw.images:
                for img in raw.images:
                    if isinstance(img, dict) and "image_url" in img:
                        user_content.append({
                            "type": "image_url",
                            "image_url": img["image_url"]
                        })
            
            # Single call to LLM with classifier prompt
            response = await self.client.chat.completions.create(
                model="gpt-5.1",  # Using gpt-5.1 for vision + text support
                messages=[
                    {"role": "system", "content": classifier_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=50,
                temperature=0.0,
            )
            
            label = response.choices[0].message.content.strip().lower()
            if label == "null":
                return ClassificationResult(tipo=None, score=0.0, reasons=["llm_null"])
            return ClassificationResult(tipo=label, score=0.6, reasons=["llm_multimodal"])
            
        except Exception as e:
            logger.error(f"Error in classification: {e}")
            return ClassificationResult(tipo=None, score=0.0, reasons=["llm_error"])

    async def audio_to_text(self, audio_file: bytes) -> str:
        """Convierte audio a texto usando Whisper de OpenAI"""
        try:
            logger.info("Transcribiendo audio con Whisper...")

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_file)
                tmp_file_path = tmp_file.name

            with open(tmp_file_path, "rb") as audio:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    language="es",
                )

            os.unlink(tmp_file_path)

            text = response.text.strip()
            logger.info(f"Audio transcrito: {text[:100]}...")

            return text

        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            raise Exception(f"Error en transcripción: {e}")

    async def run_prompt(self, template_name: str, context: dict, images: list = None) -> str:
        """Carga una plantilla de prompt desde app/prompts/ y ejecuta con soporte multimodal.
        
        Args:
            template_name: Nombre del archivo de prompt
            context: Dict con variables para el template (ej: {"text": "..."})
            images: Lista de imágenes en formato [{"type": "image_url", "image_url": {...}}]
        
        Devuelve el texto crudo de la respuesta del modelo.
        """
        template_path = os.path.join(self.prompts_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Prompt template not found: {template_name}")

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        prompt_text = template.format(**context)

        try:
            # Build user content with text + images
            user_content = [{"type": "text", "text": prompt_text}]
            
            # Add images if provided
            if images:
                user_content.extend(images)
            
            response = await self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[{"role": "user", "content": user_content}],
                temperature=0.0,
            )

            result = response.choices[0].message.content.strip()
            return result

        except Exception as e:
            logger.error(f"Error running prompt {template_name}: {e}")
            raise

    def _create_fallback_analysis(self, original_content: str, error_message: str) -> AIAnalysis:
        """Crea análisis de respaldo cuando falla el procesamiento principal"""
        return AIAnalysis(
            tipo_registro="consulta",
            animal_nombre=None,
            confianza=0.0,
            detalles={
                "error": error_message,
                "contenido_original": original_content[:200],
                "procesamiento": "fallback",
            },
        )
