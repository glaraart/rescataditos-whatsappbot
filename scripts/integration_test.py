import asyncio
import os
import json
from app.models.analysis import RawContent
from app.services.ai import AIService


class FakeAIService(AIService):
    def __init__(self):
        # don't call super (no API key needed)
        pass

    async def run_prompt(self, template_name: str, context: dict) -> str:
        text = context.get("text", "")
        if template_name == "classifier_prompt.txt":
            # crude rule: if contains 'gaste' or '$' -> gasto
            if "$" in text or "gaste" in text.lower():
                return "gasto"
            if "adopt" in text.lower() or "adoptado" in text.lower():
                return "cambio_estado"
            if "veterin" in text.lower() or "diagnost" in text.lower():
                return "visita_vet"
            if text.strip().endswith("?"):
                return "consulta"
            return "null"
        if template_name == "gasto_prompt.txt":
            # return a JSON string matching gasto schema
            return json.dumps({
                "monto": 1500,
                "fecha": "2025-11-20",
                "categoria_id": 5,
                "descripcion": "vacunas",
                "proveedor": "VetCare",
                "nombre": "Luna"
            }, ensure_ascii=False)
        if template_name == "nuevo_rescate_prompt.txt":
            return json.dumps({
                "nombre": "Luna",
                "tipo_animal": "perro",
                "edad": "6 meses",
                "color_de_pelo": [{"color": "marrón", "porcentaje": 100}],
                "condicion_de_salud_inicial": "buena",
                "ubicacion": "Flores"
            }, ensure_ascii=False)
        return "null"

async def run():
    # Build a sample RawContent resembling a gasto message
    raw = RawContent(
        text="Gaste $1500 en vacunas para Luna el 2025-11-20, proveedor: VetCare",
        images=[],
        audio_text=None,
        phone="+5491123456789",
        from_number="+5491123456789",
        whatsapp_message_id="msg-test-1"
    )

    fake_ai = FakeAIService()
    # Run several test inputs to cover handlers
    tests = [
        RawContent(text="Gaste $1500 en vacunas para Luna el 2025-11-20, proveedor: VetCare", images=[], audio_text=None, phone="+5491123456789", from_number="+5491123456789", whatsapp_message_id="msg-test-1"),
        RawContent(text="Parche fue adoptado por la familia Martinez", images=[], audio_text=None, phone="+5491123456789", from_number="+5491123456789", whatsapp_message_id="msg-test-2"),
        RawContent(text="Lo llevé al veterinario, diagnosticaron garrapatas y le dieron un tratamiento", images=[], audio_text=None, phone="+5491123456789", from_number="+5491123456789", whatsapp_message_id="msg-test-3"),
        RawContent(text="¿Cómo hago para esterilizar a mi gata?", images=[], audio_text=None, phone="+5491123456789", from_number="+5491123456789", whatsapp_message_id="msg-test-4"),
    ]

    for i, raw in enumerate(tests, start=1):
        try:
            cls = await asyncio.wait_for(fake_ai.classify(raw), timeout=5)
            print(f"Test {i} classifier:", cls.tipo)
        except Exception as e:
            print(f"Test {i} classifier failed:", e)
    
    try:
        result = await asyncio.wait_for(fake_ai.classify(raw), timeout=15)
        print("Classification result:")
        if result is None or result.tipo is None:
            print("No type classified")
        else:
            print(f"Classified as: {result.tipo}")
    except Exception as e:
        print("Classification run failed:", e)

if __name__ == '__main__':
    asyncio.run(run())
