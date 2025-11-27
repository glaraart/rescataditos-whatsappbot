from app.utils.llm_parsing import parse_json_from_text

examples = [
    "Here is the result:\n```json\n{ 'monto': 1200, 'moneda': 'ARS' }\n```",
    'Respuesta: {\n  monto: 2500,\n  \'moneda\': \'ARS\',\n  \'descripcion\': "Compra de vacunas"\n}',
    'Some commentary before {"tipo": "consulta", "text": "¿Hay turnos?"} after',
    'No JSON here',
    'Triple backticks and extra text:\n```\n{"ok": True, \'val\': None,}\n``` More text',
]

for i, ex in enumerate(examples, start=1):
    parsed, err = parse_json_from_text(ex)
    print(f"Example {i}: err={err}; parsed={parsed}")
