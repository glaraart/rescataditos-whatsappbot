# Rescue models
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AnimalType(str, Enum):
    """Animal types"""
    DOG = "perro"
    CAT = "gato"
    BIRD = "ave"
    RABBIT = "conejo"
    OTHER = "otro"
    UNKNOWN = "desconocido"

class RescueStatus(str, Enum):
    """Rescue status options"""
    PENDING = "pendiente"
    ASSIGNED = "asignado"
    IN_PROGRESS = "en_progreso"
    COMPLETED = "completado"
    CANCELLED = "cancelado"

class UrgencyLevel(str, Enum):
    """Urgency levels"""
    LOW = "baja"
    MEDIUM = "media"
    HIGH = "alta"
    CRITICAL = "critica"

class AnimalCondition(str, Enum):
    """Animal condition options"""
    HEALTHY = "saludable"
    INJURED = "herido"
    SICK = "enfermo"
    LOST = "perdido"
    ABANDONED = "abandonado"
    ABUSED = "maltratado"
    UNKNOWN = "desconocido"

class RescueLocation(BaseModel):
    """Location information for rescue"""
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    landmarks: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = "CDMX"
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError('Longitude must be between -180 and 180')
        return v

class RescueReporter(BaseModel):
    """Person reporting the rescue"""
    phone_number: str
    name: Optional[str] = None
    is_owner: bool = False
    contact_preference: str = "whatsapp"
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Basic phone number validation
        if not v.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError('Invalid phone number format')
        return v

class AnimalInfo(BaseModel):
    """Information about the animal"""
    type: AnimalType = AnimalType.UNKNOWN
    breed: Optional[str] = None
    size: Optional[str] = None  # pequeño, mediano, grande
    color: Optional[str] = None
    age_estimate: Optional[str] = None  # cachorro, adulto, senior
    gender: Optional[str] = None  # macho, hembra, desconocido
    condition: AnimalCondition = AnimalCondition.UNKNOWN
    description: Optional[str] = None
    has_collar: Optional[bool] = None
    is_microchipped: Optional[bool] = None

class RescueMedia(BaseModel):
    """Media files associated with rescue"""
    image_urls: List[str] = []
    video_urls: List[str] = []
    audio_urls: List[str] = []
    document_urls: List[str] = []

class VolunteerInfo(BaseModel):
    """Volunteer assigned to rescue"""
    volunteer_id: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    assigned_at: Optional[datetime] = None
    notes: Optional[str] = None

class RescueRecord(BaseModel):
    """Main rescue record model"""
    id: Optional[str] = None
    timestamp: datetime = datetime.now()
    reporter: RescueReporter
    location: RescueLocation
    animal: AnimalInfo
    status: RescueStatus = RescueStatus.PENDING
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    description: Optional[str] = None
    media: RescueMedia = RescueMedia()
    volunteer: Optional[VolunteerInfo] = None
    notes: List[str] = []
    created_at: datetime = datetime.now()
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def add_note(self, note: str):
        """Add a note to the rescue record"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.notes.append(f"[{timestamp}] {note}")
        self.updated_at = datetime.now()

class RescueUpdate(BaseModel):
    """Model for updating rescue records"""
    status: Optional[RescueStatus] = None
    urgency: Optional[UrgencyLevel] = None
    volunteer_id: Optional[str] = None
    notes: Optional[str] = None
    location_update: Optional[RescueLocation] = None
    animal_update: Optional[AnimalInfo] = None

class RescueSearchCriteria(BaseModel):
    """Search criteria for rescue records"""
    status: Optional[RescueStatus] = None
    urgency: Optional[UrgencyLevel] = None
    animal_type: Optional[AnimalType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    location_keyword: Optional[str] = None
    volunteer_id: Optional[str] = None

class RescueStats(BaseModel):
    """Rescue statistics model"""
    total_rescues: int = 0
    pending_rescues: int = 0
    completed_rescues: int = 0
    cancelled_rescues: int = 0
    by_animal_type: Dict[str, int] = {}
    by_urgency: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    average_response_time: Optional[float] = None

class RescueAnalytics(BaseModel):
    """Analytics for rescue operations"""
    period: str  # daily, weekly, monthly
    start_date: datetime
    end_date: datetime
    stats: RescueStats
    trends: Dict[str, Any] = {}
    recommendations: List[str] = []
