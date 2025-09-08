# WhatsApp Pydantic models
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AIAnalysis(BaseModel):
    """Modelo para el análisis de IA de los mensajes"""
    tipo_registro: str = Field(..., description="nuevo_rescate, cambio_estado, visita_vet, gasto, consulta")
    animal_nombre: Optional[str] = Field(None, description="Nombre del animal")
    detalles: Dict[str, Any] = Field(default_factory=dict, description="Detalles específicos")
    informacion_completa: bool = Field(False, description="Si toda la información requerida está presente")
    campos_faltantes: List[str] = Field(default_factory=list, description="Lista de campos que faltan")
