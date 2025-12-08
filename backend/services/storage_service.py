"""
Google Cloud Storage operations for file management.
"""
import logging
import os
import json
from typing import Optional, BinaryIO, Any, Dict
from pathlib import Path
from google.cloud import storage
from datetime import timedelta

from backend.config import settings


logger = logging.getLogger(__name__)


class StorageService:
    """Service for Google Cloud Storage operations."""
    
    def __init__(self):
        """Initialize GCS client."""
        self.client = storage.Client(project=settings.google_cloud_project)
        self.bucket = self.client.bucket(settings.gcs_bucket_name)
    
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """Upload a file to GCS."""
        try:
            blob = self.bucket.blob(destination_path)
            blob.upload_from_filename(local_path)
            logger.info(f"Uploaded {local_path} to gs://{settings.gcs_bucket_name}/{destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error uploading file {local_path}: {e}")
            raise
    
    def upload_fileobj(self, file_obj: BinaryIO, destination_path: str, content_type: Optional[str] = None) -> str:
        """Upload a file object to GCS."""
        try:
            blob = self.bucket.blob(destination_path)
            if content_type:
                blob.content_type = content_type
            blob.upload_from_file(file_obj, rewind=True)
            logger.info(f"Uploaded file object to gs://{settings.gcs_bucket_name}/{destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error uploading file object: {e}")
            raise
    
    def download_file(self, source_path: str, destination_path: str) -> str:
        """Download a file from GCS."""
        try:
            blob = self.bucket.blob(source_path)
            blob.download_to_filename(destination_path)
            logger.info(f"Downloaded gs://{settings.gcs_bucket_name}/{source_path} to {destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error downloading file {source_path}: {e}")
            raise
    
    def generate_signed_url(self, blob_path: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for downloading a file.
        
        In Cloud Run, this uses the IAM signBlob API since we don't have
        a private key available. Requires the service account to have
        roles/iam.serviceAccountTokenCreator on itself.
        """
        import google.auth
        from google.auth.transport import requests
        
        try:
            blob = self.bucket.blob(blob_path)
            
            # Get default credentials and refresh to ensure we have a valid token
            credentials, project = google.auth.default()
            
            # Check if we're using compute credentials (Cloud Run/GCE)
            # These need to use IAM signBlob via service_account_email + access_token
            if hasattr(credentials, 'service_account_email'):
                # Refresh credentials to get a valid access token
                auth_request = requests.Request()
                credentials.refresh(auth_request)
                
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET",
                    service_account_email=credentials.service_account_email,
                    access_token=credentials.token
                )
            else:
                # Local development with service account key or user credentials
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET"
                )
            
            logger.info(f"Generated signed URL for {blob_path}")
            return url
        except Exception as e:
            logger.error(f"Error generating signed URL for {blob_path}: {e}")
            raise
    
    def delete_file(self, blob_path: str) -> None:
        """Delete a file from GCS."""
        try:
            blob = self.bucket.blob(blob_path)
            blob.delete()
            logger.info(f"Deleted gs://{settings.gcs_bucket_name}/{blob_path}")
        except Exception as e:
            logger.error(f"Error deleting file {blob_path}: {e}")
            raise
    
    def list_files(self, prefix: str) -> list:
        """List files in GCS with a given prefix."""
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            raise
    
    def file_exists(self, blob_path: str) -> bool:
        """Check if a file exists in GCS."""
        try:
            blob = self.bucket.blob(blob_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence {blob_path}: {e}")
            raise
    
    def upload_json(self, destination_path: str, data: Dict[str, Any]) -> str:
        """Upload a JSON object to GCS."""
        try:
            blob = self.bucket.blob(destination_path)
            blob.content_type = "application/json"
            blob.upload_from_string(
                json.dumps(data, indent=2, ensure_ascii=False),
                content_type="application/json"
            )
            logger.info(f"Uploaded JSON to gs://{settings.gcs_bucket_name}/{destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error uploading JSON to {destination_path}: {e}")
            raise
    
    def download_json(self, source_path: str) -> Dict[str, Any]:
        """Download and parse a JSON file from GCS."""
        try:
            blob = self.bucket.blob(source_path)
            content = blob.download_as_text()
            data = json.loads(content)
            logger.info(f"Downloaded JSON from gs://{settings.gcs_bucket_name}/{source_path}")
            return data
        except Exception as e:
            logger.error(f"Error downloading JSON from {source_path}: {e}")
            raise

