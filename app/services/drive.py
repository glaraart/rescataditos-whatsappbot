import logging 
import base64
from app.config import settings
import json
from io import BytesIO
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self):
        self.drive_animales = settings.GOOGLE_DRIVE_FOLDER_ANIMALES
        self.drive_gastos = settings.GOOGLE_DRIVE_FOLDER_GASTOS
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
        self.creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            
            # Initialize Drive API service
        self.service = build('drive', 'v3', credentials=self.creds)
    
    async def save_image( self ,rescue_id ,nombre , content_list, folder):

        drive_folder = self.drive_animales  if folder == "ANIMALES" else self.drive_gastos
        for item in content_list:
            if item.get("type") == "image_url":
                url = item["image_url"]["url"]
                base64_image = url.split(",")[1]   # SEPARA EL PREFIJO
                image_bytes = base64.b64decode(base64_image) 
                 
                media = MediaIoBaseUpload(BytesIO(image_bytes), mimetype="image/jpeg")

                file_metadata = {"name": nombre+" "+rescue_id, "parents": [drive_folder]}

                archivo = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()
                file_id = archivo["id"]
                # URL que pedís
                public_url = f"https://drive.google.com/uc?id={file_id}"

                return public_url

