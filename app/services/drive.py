# Google Drive API service
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from typing import Optional, Dict, Any
import io
import logging
import mimetypes

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self, credentials_path: str, folder_id: Optional[str] = None):
        self.credentials_path = credentials_path
        self.folder_id = folder_id
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive API"""
        try:
            scope = ["https://www.googleapis.com/auth/drive"]
            
            creds = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scope
            )
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Drive API")
        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {e}")
            raise
    
    def upload_file(self, file_content: bytes, filename: str, 
                   content_type: Optional[str] = None) -> Optional[str]:
        """Upload file to Google Drive"""
        try:
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id] if self.folder_id else []
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(file_content), 
                mimetype=content_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            
            # Make file publicly viewable
            self._make_file_public(file_id)
            
            # Get public link
            public_link = f"https://drive.google.com/file/d/{file_id}/view"
            
            logger.info(f"Successfully uploaded file {filename} with ID: {file_id}")
            return public_link
            
        except Exception as e:
            logger.error(f"Error uploading file {filename}: {e}")
            return None
    
    def _make_file_public(self, file_id: str):
        """Make file publicly viewable"""
        try:
            permission = {
                'role': 'reader',
                'type': 'anyone'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            logger.info(f"Made file {file_id} publicly viewable")
        except Exception as e:
            logger.error(f"Error making file public: {e}")
    
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file from Google Drive"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            
            while done is False:
                status, done = downloader.next_chunk()
            
            logger.info(f"Successfully downloaded file {file_id}")
            return file_content.getvalue()
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file from Google Drive"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Successfully deleted file {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def list_files(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in folder"""
        try:
            folder_to_search = folder_id or self.folder_id
            
            query = f"parents in '{folder_to_search}'" if folder_to_search else None
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, createdTime, size)"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} files")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
