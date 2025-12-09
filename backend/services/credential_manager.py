"""
OAuth Credential Manager for validating and refreshing credentials.

This service provides:
1. Credential validation for YouTube, Dropbox, and Google Drive
2. Device Authorization Flow for re-authentication
3. Proactive monitoring with alerts when credentials expire
"""
import json
import logging
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from google.oauth2.credentials import Credentials as GoogleCredentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from backend.config import get_settings

logger = logging.getLogger(__name__)


class CredentialStatus(str, Enum):
    """Status of OAuth credentials."""
    VALID = "valid"
    EXPIRED = "expired"  # Token expired but refresh may work
    INVALID = "invalid"  # Refresh failed, re-auth needed
    NOT_CONFIGURED = "not_configured"  # No credentials stored
    ERROR = "error"  # Unknown error during validation


@dataclass
class CredentialCheckResult:
    """Result of a credential validation check."""
    service: str
    status: CredentialStatus
    message: str
    last_checked: datetime
    expires_at: Optional[datetime] = None


@dataclass  
class DeviceAuthInfo:
    """Information for device authorization flow."""
    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int
    started_at: datetime


class CredentialManager:
    """
    Manages OAuth credentials for all external services.
    
    Provides validation, refresh, and device authorization flow for:
    - YouTube (Google OAuth)
    - Google Drive (Google OAuth)
    - Dropbox
    """
    
    # Secret names in Secret Manager
    YOUTUBE_SECRET = "youtube-oauth-credentials"
    GDRIVE_SECRET = "gdrive-oauth-credentials"
    DROPBOX_SECRET = "dropbox-oauth-credentials"
    
    # Google OAuth endpoints
    GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
    GOOGLE_DEVICE_AUTH_URI = "https://oauth2.googleapis.com/device/code"
    
    # Dropbox OAuth endpoints
    DROPBOX_TOKEN_URI = "https://api.dropboxapi.com/oauth2/token"
    
    # Scopes for each service
    YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]
    GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    
    def __init__(self):
        self.settings = get_settings()
        self._pending_device_auths: Dict[str, DeviceAuthInfo] = {}
    
    # =========================================================================
    # Credential Validation
    # =========================================================================
    
    def check_all_credentials(self) -> Dict[str, CredentialCheckResult]:
        """
        Check validity of all OAuth credentials.
        
        Returns:
            Dictionary mapping service name to check result
        """
        results = {}
        
        results["youtube"] = self.check_youtube_credentials()
        results["gdrive"] = self.check_gdrive_credentials()
        results["dropbox"] = self.check_dropbox_credentials()
        
        return results
    
    def check_youtube_credentials(self) -> CredentialCheckResult:
        """Check if YouTube credentials are valid and can be refreshed."""
        return self._check_google_credentials(
            secret_name=self.YOUTUBE_SECRET,
            service_name="youtube",
            scopes=self.YOUTUBE_SCOPES,
            test_api_call=self._test_youtube_api
        )
    
    def check_gdrive_credentials(self) -> CredentialCheckResult:
        """Check if Google Drive credentials are valid and can be refreshed."""
        return self._check_google_credentials(
            secret_name=self.GDRIVE_SECRET,
            service_name="gdrive",
            scopes=self.GDRIVE_SCOPES,
            test_api_call=self._test_gdrive_api
        )
    
    def check_dropbox_credentials(self) -> CredentialCheckResult:
        """Check if Dropbox credentials are valid."""
        try:
            creds_json = self.settings.get_secret(self.DROPBOX_SECRET)
            
            if not creds_json:
                return CredentialCheckResult(
                    service="dropbox",
                    status=CredentialStatus.NOT_CONFIGURED,
                    message="Dropbox credentials not configured",
                    last_checked=datetime.utcnow()
                )
            
            creds = json.loads(creds_json)
            
            if not creds.get("access_token"):
                return CredentialCheckResult(
                    service="dropbox",
                    status=CredentialStatus.INVALID,
                    message="Dropbox credentials missing access_token",
                    last_checked=datetime.utcnow()
                )
            
            # Test the credentials with a simple API call
            if self._test_dropbox_api(creds):
                return CredentialCheckResult(
                    service="dropbox",
                    status=CredentialStatus.VALID,
                    message="Dropbox credentials are valid",
                    last_checked=datetime.utcnow()
                )
            else:
                # Try to refresh if we have refresh token
                if creds.get("refresh_token") and creds.get("app_key") and creds.get("app_secret"):
                    if self._refresh_dropbox_token(creds):
                        return CredentialCheckResult(
                            service="dropbox",
                            status=CredentialStatus.VALID,
                            message="Dropbox credentials refreshed successfully",
                            last_checked=datetime.utcnow()
                        )
                
                return CredentialCheckResult(
                    service="dropbox",
                    status=CredentialStatus.INVALID,
                    message="Dropbox credentials invalid and refresh failed",
                    last_checked=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error checking Dropbox credentials: {e}")
            return CredentialCheckResult(
                service="dropbox",
                status=CredentialStatus.ERROR,
                message=f"Error checking credentials: {str(e)}",
                last_checked=datetime.utcnow()
            )
    
    def _check_google_credentials(
        self,
        secret_name: str,
        service_name: str,
        scopes: list,
        test_api_call: callable
    ) -> CredentialCheckResult:
        """Generic Google OAuth credential check."""
        try:
            creds_json = self.settings.get_secret(secret_name)
            
            if not creds_json:
                return CredentialCheckResult(
                    service=service_name,
                    status=CredentialStatus.NOT_CONFIGURED,
                    message=f"{service_name} credentials not configured",
                    last_checked=datetime.utcnow()
                )
            
            creds_data = json.loads(creds_json)
            
            # Check for required fields
            required = ["refresh_token", "client_id", "client_secret"]
            missing = [f for f in required if not creds_data.get(f)]
            if missing:
                return CredentialCheckResult(
                    service=service_name,
                    status=CredentialStatus.INVALID,
                    message=f"Missing required fields: {missing}",
                    last_checked=datetime.utcnow()
                )
            
            # Create credentials object
            credentials = GoogleCredentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri", self.GOOGLE_TOKEN_URI),
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret"),
                scopes=creds_data.get("scopes", scopes)
            )
            
            # Try to refresh if expired
            if credentials.expired or not credentials.token:
                try:
                    credentials.refresh(GoogleAuthRequest())
                    # Update stored credentials with new token
                    self._update_google_credentials(secret_name, creds_data, credentials)
                except Exception as e:
                    logger.error(f"Failed to refresh {service_name} credentials: {e}")
                    return CredentialCheckResult(
                        service=service_name,
                        status=CredentialStatus.INVALID,
                        message=f"Token refresh failed: {str(e)}",
                        last_checked=datetime.utcnow()
                    )
            
            # Test with API call
            if test_api_call(credentials):
                return CredentialCheckResult(
                    service=service_name,
                    status=CredentialStatus.VALID,
                    message=f"{service_name} credentials are valid",
                    last_checked=datetime.utcnow(),
                    expires_at=credentials.expiry
                )
            else:
                return CredentialCheckResult(
                    service=service_name,
                    status=CredentialStatus.INVALID,
                    message=f"{service_name} API test failed",
                    last_checked=datetime.utcnow()
                )
                
        except json.JSONDecodeError as e:
            return CredentialCheckResult(
                service=service_name,
                status=CredentialStatus.INVALID,
                message=f"Invalid JSON in credentials: {str(e)}",
                last_checked=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Error checking {service_name} credentials: {e}")
            return CredentialCheckResult(
                service=service_name,
                status=CredentialStatus.ERROR,
                message=f"Error: {str(e)}",
                last_checked=datetime.utcnow()
            )
    
    def _update_google_credentials(
        self,
        secret_name: str,
        original_data: dict,
        credentials: GoogleCredentials
    ) -> bool:
        """Update stored Google credentials with refreshed token."""
        try:
            from google.cloud import secretmanager
            
            updated_data = original_data.copy()
            updated_data["token"] = credentials.token
            if credentials.expiry:
                updated_data["expiry"] = credentials.expiry.isoformat()
            
            # Add new secret version
            client = secretmanager.SecretManagerServiceClient()
            project_id = self.settings.google_cloud_project
            secret_path = f"projects/{project_id}/secrets/{secret_name}"
            
            client.add_secret_version(
                parent=secret_path,
                payload={"data": json.dumps(updated_data).encode("utf-8")}
            )
            
            logger.info(f"Updated {secret_name} with refreshed token")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update {secret_name}: {e}")
            return False
    
    # =========================================================================
    # API Test Methods
    # =========================================================================
    
    def _test_youtube_api(self, credentials: GoogleCredentials) -> bool:
        """Test YouTube credentials with a simple API call."""
        try:
            from googleapiclient.discovery import build
            
            youtube = build("youtube", "v3", credentials=credentials)
            # Just get channel info - minimal API call
            request = youtube.channels().list(part="id", mine=True)
            response = request.execute()
            
            return "items" in response
            
        except Exception as e:
            logger.error(f"YouTube API test failed: {e}")
            return False
    
    def _test_gdrive_api(self, credentials: GoogleCredentials) -> bool:
        """Test Google Drive credentials with a simple API call."""
        try:
            from googleapiclient.discovery import build
            
            drive = build("drive", "v3", credentials=credentials)
            # Just get about info - minimal API call
            request = drive.about().get(fields="user")
            response = request.execute()
            
            return "user" in response
            
        except Exception as e:
            logger.error(f"Google Drive API test failed: {e}")
            return False
    
    def _test_dropbox_api(self, creds: dict) -> bool:
        """Test Dropbox credentials with a simple API call."""
        try:
            import dropbox
            
            dbx = dropbox.Dropbox(creds["access_token"])
            # Just get account info - minimal API call
            dbx.users_get_current_account()
            return True
            
        except Exception as e:
            logger.error(f"Dropbox API test failed: {e}")
            return False
    
    def _refresh_dropbox_token(self, creds: dict) -> bool:
        """Try to refresh Dropbox token."""
        try:
            import requests
            
            response = requests.post(
                self.DROPBOX_TOKEN_URI,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": creds["refresh_token"],
                    "client_id": creds["app_key"],
                    "client_secret": creds["app_secret"],
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                creds["access_token"] = token_data["access_token"]
                
                # Update in Secret Manager
                self._update_dropbox_credentials(creds)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Dropbox token refresh failed: {e}")
            return False
    
    def _update_dropbox_credentials(self, creds: dict) -> bool:
        """Update stored Dropbox credentials."""
        try:
            from google.cloud import secretmanager
            
            client = secretmanager.SecretManagerServiceClient()
            project_id = self.settings.google_cloud_project
            secret_path = f"projects/{project_id}/secrets/{self.DROPBOX_SECRET}"
            
            client.add_secret_version(
                parent=secret_path,
                payload={"data": json.dumps(creds).encode("utf-8")}
            )
            
            logger.info("Updated Dropbox credentials with refreshed token")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Dropbox credentials: {e}")
            return False
    
    # =========================================================================
    # Device Authorization Flow
    # =========================================================================
    
    def start_youtube_device_auth(self, client_id: str, client_secret: str) -> DeviceAuthInfo:
        """
        Start YouTube device authorization flow.
        
        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret (stored for token exchange)
            
        Returns:
            DeviceAuthInfo with user code and verification URL
        """
        return self._start_google_device_auth(
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.YOUTUBE_SCOPES,
            service_name="youtube"
        )
    
    def start_gdrive_device_auth(self, client_id: str, client_secret: str) -> DeviceAuthInfo:
        """
        Start Google Drive device authorization flow.
        
        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            
        Returns:
            DeviceAuthInfo with user code and verification URL
        """
        return self._start_google_device_auth(
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.GDRIVE_SCOPES,
            service_name="gdrive"
        )
    
    def _start_google_device_auth(
        self,
        client_id: str,
        client_secret: str,
        scopes: list,
        service_name: str
    ) -> DeviceAuthInfo:
        """Start Google device authorization flow."""
        import requests
        
        response = requests.post(
            self.GOOGLE_DEVICE_AUTH_URI,
            data={
                "client_id": client_id,
                "scope": " ".join(scopes),
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Device auth request failed: {response.text}")
        
        logger.info(f"Device auth response: {response.text}")
        
        data = response.json()
        
        # Google uses 'verification_uri' but some docs show 'verification_url'
        verification_url = data.get("verification_uri") or data.get("verification_url")
        
        device_info = DeviceAuthInfo(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_url=verification_url,
            expires_in=data["expires_in"],
            interval=data.get("interval", 5),
            started_at=datetime.utcnow()
        )
        
        # Store for polling, include client secret for token exchange
        self._pending_device_auths[f"{service_name}:{data['device_code']}"] = {
            "info": device_info,
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": scopes,
            "service_name": service_name
        }
        
        return device_info
    
    def poll_device_auth(self, service_name: str, device_code: str) -> Tuple[str, Optional[dict]]:
        """
        Poll for device authorization completion.
        
        Args:
            service_name: "youtube" or "gdrive"
            device_code: The device code from start_*_device_auth
            
        Returns:
            Tuple of (status, token_data)
            status: "pending", "complete", "expired", "error"
            token_data: Token data if complete, None otherwise
        """
        import requests
        
        key = f"{service_name}:{device_code}"
        if key not in self._pending_device_auths:
            return ("error", {"message": "Unknown device code"})
        
        auth_data = self._pending_device_auths[key]
        device_info = auth_data["info"]
        
        # Check if expired
        elapsed = (datetime.utcnow() - device_info.started_at).total_seconds()
        if elapsed > device_info.expires_in:
            del self._pending_device_auths[key]
            return ("expired", None)
        
        # Poll Google token endpoint
        response = requests.post(
            self.GOOGLE_TOKEN_URI,
            data={
                "client_id": auth_data["client_id"],
                "client_secret": auth_data["client_secret"],
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }
        )
        
        data = response.json()
        
        if response.status_code == 200:
            # Success! Store the credentials
            token_data = {
                "token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "token_uri": self.GOOGLE_TOKEN_URI,
                "client_id": auth_data["client_id"],
                "client_secret": auth_data["client_secret"],
                "scopes": auth_data["scopes"],
            }
            
            # Save to Secret Manager
            secret_name = self.YOUTUBE_SECRET if service_name == "youtube" else self.GDRIVE_SECRET
            self._save_credentials_to_secret(secret_name, token_data)
            
            # Cleanup
            del self._pending_device_auths[key]
            
            return ("complete", token_data)
        
        elif "error" in data:
            error = data["error"]
            if error == "authorization_pending":
                return ("pending", None)
            elif error == "slow_down":
                # Increase polling interval
                device_info.interval += 5
                return ("pending", None)
            elif error == "expired_token":
                del self._pending_device_auths[key]
                return ("expired", None)
            elif error == "access_denied":
                del self._pending_device_auths[key]
                return ("error", {"message": "User denied access"})
            else:
                return ("error", {"message": data.get("error_description", error)})
        
        return ("error", {"message": "Unknown response from token endpoint"})
    
    def _save_credentials_to_secret(self, secret_name: str, token_data: dict) -> bool:
        """Save credentials to Secret Manager."""
        try:
            from google.cloud import secretmanager
            
            client = secretmanager.SecretManagerServiceClient()
            project_id = self.settings.google_cloud_project
            secret_path = f"projects/{project_id}/secrets/{secret_name}"
            
            client.add_secret_version(
                parent=secret_path,
                payload={"data": json.dumps(token_data).encode("utf-8")}
            )
            
            logger.info(f"Saved new credentials to {secret_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save credentials to {secret_name}: {e}")
            return False
    
    # =========================================================================
    # Alerts
    # =========================================================================
    
    def send_credential_alert(
        self,
        invalid_services: list[CredentialCheckResult],
        discord_webhook_url: Optional[str] = None
    ) -> bool:
        """
        Send alert about invalid credentials.
        
        Args:
            invalid_services: List of services with invalid credentials
            discord_webhook_url: Discord webhook URL for notifications
            
        Returns:
            True if alert was sent successfully
        """
        if not discord_webhook_url:
            logger.warning("No Discord webhook URL configured for alerts")
            return False
        
        try:
            import requests
            
            services_list = "\n".join([
                f"• **{r.service}**: {r.message}"
                for r in invalid_services
            ])
            
            # Get the API base URL for re-auth links
            api_url = self.settings.api_base_url if hasattr(self.settings, 'api_base_url') else "https://your-api-url"
            
            message = {
                "embeds": [{
                    "title": "⚠️ OAuth Credentials Need Attention",
                    "description": f"The following service credentials need re-authorization:\n\n{services_list}",
                    "color": 16744256,  # Orange
                    "fields": [
                        {
                            "name": "Re-authorize",
                            "value": f"Visit `{api_url}/api/auth/status` to start re-authorization flow",
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": "karaoke-gen backend"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            response = requests.post(discord_webhook_url, json=message)
            return response.status_code in (200, 204)
            
        except Exception as e:
            logger.error(f"Failed to send credential alert: {e}")
            return False


# Singleton instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get the singleton credential manager instance."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager
