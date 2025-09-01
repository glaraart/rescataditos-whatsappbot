# WhatsApp Pydantic models
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class WhatsAppMessage(BaseModel):
    """WhatsApp message model"""
    id: str
    from_: str = None  # Use from_ to avoid conflict with Python keyword
    timestamp: str
    type: str
    text: Optional[Dict[str, Any]] = None
    image: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None
    document: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None

class WhatsAppContact(BaseModel):
    """WhatsApp contact model"""
    profile: Optional[Dict[str, str]] = None
    wa_id: str

class WhatsAppMetadata(BaseModel):
    """WhatsApp metadata model"""
    display_phone_number: str
    phone_number_id: str

class WhatsAppValue(BaseModel):
    """WhatsApp webhook value model"""
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[Dict[str, Any]]] = None

class WhatsAppChange(BaseModel):
    """WhatsApp webhook change model"""
    value: WhatsAppValue
    field: str

class WhatsAppEntry(BaseModel):
    """WhatsApp webhook entry model"""
    id: str
    changes: List[WhatsAppChange]

class WhatsAppWebhook(BaseModel):
    """WhatsApp webhook payload model"""
    object: str
    entry: List[WhatsAppEntry]

class WhatsAppMessageRequest(BaseModel):
    """Request model for sending WhatsApp messages"""
    messaging_product: str = "whatsapp"
    to: str
    type: str = "text"
    text: Optional[Dict[str, str]] = None
    image: Optional[Dict[str, str]] = None
    audio: Optional[Dict[str, str]] = None
    video: Optional[Dict[str, str]] = None
    document: Optional[Dict[str, str]] = None

class WhatsAppTextMessage(BaseModel):
    """Text message for WhatsApp"""
    body: str
    preview_url: Optional[bool] = False

class WhatsAppMediaMessage(BaseModel):
    """Media message for WhatsApp"""
    id: Optional[str] = None
    link: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None

class WhatsAppLocationMessage(BaseModel):
    """Location message for WhatsApp"""
    longitude: float
    latitude: float
    name: Optional[str] = None
    address: Optional[str] = None

class MessageStatus(BaseModel):
    """Message status model"""
    id: str
    status: str  # sent, delivered, read, failed
    timestamp: str
    recipient_id: str
    errors: Optional[List[Dict[str, Any]]] = None

class WhatsAppWebhookVerification(BaseModel):
    """Webhook verification model"""
    hub_mode: str
    hub_verify_token: str
    hub_challenge: str

class ConversationContext(BaseModel):
    """Conversation context model"""
    user_id: str
    conversation_state: str  # waiting_for_location, waiting_for_details, etc.
    rescue_data: Optional[Dict[str, Any]] = None
    last_message_time: Optional[datetime] = None
    message_count: int = 0

class WhatsAppError(BaseModel):
    """WhatsApp API error model"""
    code: int
    title: str
    message: str
    error_data: Optional[Dict[str, Any]] = None

# ===== MODELOS PARA EL SISTEMA DE RESCATE =====

class WhatsAppMessage(BaseModel):
    """Modelo para mensajes procesados del webhook de WhatsApp"""
    from_number: str = Field(..., description="Número de teléfono")
    message_id: str = Field(..., description="ID del mensaje")
    timestamp: str = Field(..., description="Timestamp del mensaje")
    message_type: str = Field(..., description="text, audio, image")
    content: Optional[str] = Field(None, description="Contenido del mensaje")
    media_url: Optional[str] = Field(None, description="URL del archivo multimedia")
    media_mime_type: Optional[str] = Field(None, description="Tipo MIME del archivo")

class AIAnalysis(BaseModel):
    """Modelo para el análisis de IA de los mensajes"""
    tipo_registro: str = Field(..., description="nuevo_rescate, cambio_estado, visita_vet, gasto, consulta")
    animal_nombre: Optional[str] = Field(None, description="Nombre del animal")
    detalles: Dict[str, Any] = Field(default_factory=dict, description="Detalles específicos")
    informacion_completa: bool = Field(False, description="Si toda la información requerida está presente")
    campos_faltantes: List[str] = Field(default_factory=list, description="Lista de campos que faltan")
