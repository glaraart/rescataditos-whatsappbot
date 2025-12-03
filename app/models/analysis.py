from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime


class RawContent(BaseModel):
    phone: str
    text: str = ""
    images: List[Dict[str, Any]] = Field(default_factory=list)  # each: {id, base64, caption}
    audio_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    tipos: List[str] = Field(default_factory=list)


# ===== TIPOS ESPECÍFICOS POR TIPO DE MENSAJE =====

class ColorDePelo(BaseModel):
    color: str
    porcentaje: int


class CambioEstadoInfo(BaseModel):
    ubicacion_id: int
    estado_id: int
    persona: Optional[str] = None
    tipo_relacion_id: int


class NuevoRescateDetails(BaseModel):
    nombre: str
    tipo_animal: str
    edad: str
    color_de_pelo: List[ColorDePelo]
    condicion_de_salud_inicial: str
    ubicacion: str
    cambio_estado: CambioEstadoInfo


class CambioEstadoDetails(BaseModel):
    nombre: Optional[str] = None
    animal_id: Optional[int] = None
    ubicacion_id: int
    estado_id: int
    persona: Optional[str] = None
    tipo_relacion_id: int
    fecha: Optional[str] = None


class GastoItem(BaseModel):
    monto: float
    categoria_id: int
    descripcion: str
    nombre_animal: Optional[str] = None


class VeterinariaDetails(BaseModel):
    nombre: Optional[str] = None
    fecha: Optional[str] = None
    veterinario: Optional[str] = None
    diagnostico: Optional[str] = None
    tratamiento: Optional[str] = None
    proxima_cita: Optional[str] = None
    persona_acompanante: Optional[str] = None
    # Campos de gasto veterinario
    proveedor: Optional[str] = None
    responsable: Optional[str] = None
    forma_de_pago: Optional[str] = None
    items: List[GastoItem] = Field(default_factory=list)  # Lista de gastos veterinarios


class GastoDetails(BaseModel):
    nombre: Optional[str] = None
    fecha: Optional[str] = None
    proveedor: Optional[str] = None
    responsable: Optional[str] = None
    forma_de_pago: Optional[str] = None
    items: List[GastoItem]


class ConsultaDetails(BaseModel):
    nombre: Optional[str] = None
    tema: str
    respuesta_sugerida: Optional[str] = None


class TrackingMovimientoDetails(BaseModel):
    tipo: str  # 'salida' or 'regreso'
    destino: str  # 'parque', 'veterinaria', 'compras', 'entrega_adopcion'
    responsable: Optional[str] = None
    animales: List[str]  # Lista de nombres de animales
    fecha: Optional[str] = None
    observaciones: Optional[str] = None


class HandlerResult(BaseModel):
    ok: bool = False
    detalles: Optional[Union[NuevoRescateDetails, GastoDetails, VeterinariaDetails, CambioEstadoDetails, ConsultaDetails, TrackingMovimientoDetails]] = None
    campos_faltantes: List[str] = Field(default_factory=list)


# Typing alias for DB record mapping
DBRecord = Dict[str, Any]
DBRecords = Dict[str, DBRecord]
