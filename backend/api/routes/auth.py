"""
OAuth credential management API routes.

Provides endpoints for:
1. Checking credential status
2. Device authorization flow for re-authentication
3. Credential validation before job submission
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.services.credential_manager import (
    get_credential_manager,
    CredentialStatus,
    CredentialCheckResult,
)
from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ===========================================================================
# Request/Response Models
# ===========================================================================

class CredentialStatusResponse(BaseModel):
    """Response model for credential status."""
    service: str
    status: str
    message: str
    last_checked: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AllCredentialsStatusResponse(BaseModel):
    """Response model for all credentials status."""
    youtube: CredentialStatusResponse
    gdrive: CredentialStatusResponse
    dropbox: CredentialStatusResponse
    all_valid: bool
    services_needing_auth: list[str]


class DeviceAuthStartRequest(BaseModel):
    """Request to start device authorization flow."""
    client_id: Optional[str] = None  # Optional - reads from Secret Manager if not provided
    client_secret: Optional[str] = None  # Optional - reads from Secret Manager if not provided


class DeviceAuthStartResponse(BaseModel):
    """Response with device authorization info."""
    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int
    instructions: str


class DeviceAuthPollResponse(BaseModel):
    """Response from polling device authorization."""
    status: str  # "pending", "complete", "expired", "error"
    message: Optional[str] = None
    credentials_saved: bool = False


class CredentialValidationRequest(BaseModel):
    """Request to validate credentials for specific services."""
    youtube: bool = False
    gdrive: bool = False
    dropbox: bool = False


class CredentialValidationResponse(BaseModel):
    """Response from credential validation."""
    valid: bool
    invalid_services: list[str]
    message: str


# ===========================================================================
# Endpoints
# ===========================================================================

@router.get("/status", response_model=AllCredentialsStatusResponse)
async def get_credentials_status():
    """
    Get the status of all OAuth credentials.
    
    Returns the validation status for YouTube, Google Drive, and Dropbox
    credentials, including whether they are valid, expired, or need
    re-authorization.
    """
    manager = get_credential_manager()
    results = manager.check_all_credentials()
    
    def to_response(result: CredentialCheckResult) -> CredentialStatusResponse:
        return CredentialStatusResponse(
            service=result.service,
            status=result.status.value,
            message=result.message,
            last_checked=result.last_checked,
            expires_at=result.expires_at
        )
    
    services_needing_auth = [
        name for name, result in results.items()
        if result.status in (CredentialStatus.INVALID, CredentialStatus.EXPIRED, CredentialStatus.NOT_CONFIGURED)
    ]
    
    return AllCredentialsStatusResponse(
        youtube=to_response(results["youtube"]),
        gdrive=to_response(results["gdrive"]),
        dropbox=to_response(results["dropbox"]),
        all_valid=len(services_needing_auth) == 0,
        services_needing_auth=services_needing_auth
    )


@router.get("/status/{service}", response_model=CredentialStatusResponse)
async def get_service_credential_status(service: str):
    """
    Get the status of a specific service's OAuth credentials.
    
    Args:
        service: One of "youtube", "gdrive", "dropbox"
    """
    manager = get_credential_manager()
    
    if service == "youtube":
        result = manager.check_youtube_credentials()
    elif service == "gdrive":
        result = manager.check_gdrive_credentials()
    elif service == "dropbox":
        result = manager.check_dropbox_credentials()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")
    
    return CredentialStatusResponse(
        service=result.service,
        status=result.status.value,
        message=result.message,
        last_checked=result.last_checked,
        expires_at=result.expires_at
    )


@router.post("/validate", response_model=CredentialValidationResponse)
async def validate_credentials(request: CredentialValidationRequest):
    """
    Validate that credentials are available for requested services.
    
    Use this before submitting a job to ensure all required
    credentials are valid.
    """
    manager = get_credential_manager()
    invalid_services = []
    
    if request.youtube:
        result = manager.check_youtube_credentials()
        if result.status != CredentialStatus.VALID:
            invalid_services.append("youtube")
    
    if request.gdrive:
        result = manager.check_gdrive_credentials()
        if result.status != CredentialStatus.VALID:
            invalid_services.append("gdrive")
    
    if request.dropbox:
        result = manager.check_dropbox_credentials()
        if result.status != CredentialStatus.VALID:
            invalid_services.append("dropbox")
    
    if invalid_services:
        return CredentialValidationResponse(
            valid=False,
            invalid_services=invalid_services,
            message=f"The following services need re-authorization: {', '.join(invalid_services)}"
        )
    
    return CredentialValidationResponse(
        valid=True,
        invalid_services=[],
        message="All requested credentials are valid"
    )


# ===========================================================================
# Device Authorization Flow Endpoints
# ===========================================================================

@router.post("/youtube/device", response_model=DeviceAuthStartResponse)
async def start_youtube_device_auth(request: Optional[DeviceAuthStartRequest] = None):
    """
    Start YouTube device authorization flow.
    
    This initiates a device auth flow that allows authorization
    from any device. The user must visit the verification URL
    and enter the user code.
    
    Client credentials are loaded from Secret Manager ('youtube-client-credentials')
    unless explicitly provided in the request body.
    
    After starting, poll /auth/youtube/device/{device_code} to
    check for completion.
    """
    manager = get_credential_manager()
    
    try:
        device_info = manager.start_youtube_device_auth(
            client_id=request.client_id if request else None,
            client_secret=request.client_secret if request else None
        )
        
        return DeviceAuthStartResponse(
            device_code=device_info.device_code,
            user_code=device_info.user_code,
            verification_url=device_info.verification_url,
            expires_in=device_info.expires_in,
            interval=device_info.interval,
            instructions=f"Visit {device_info.verification_url} and enter code: {device_info.user_code}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start YouTube device auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/youtube/device/{device_code}", response_model=DeviceAuthPollResponse)
async def poll_youtube_device_auth(device_code: str):
    """
    Poll for YouTube device authorization completion.
    
    Call this endpoint at the interval specified in the device auth
    start response. Keep polling while status is "pending".
    
    Status values:
    - pending: User has not yet authorized
    - complete: Authorization successful, credentials saved
    - expired: Device code expired, start new flow
    - error: An error occurred
    """
    manager = get_credential_manager()
    
    status, data = manager.poll_device_auth("youtube", device_code)
    
    return DeviceAuthPollResponse(
        status=status,
        message=data.get("message") if data else None,
        credentials_saved=(status == "complete")
    )


@router.post("/gdrive/device", response_model=DeviceAuthStartResponse)
async def start_gdrive_device_auth(request: Optional[DeviceAuthStartRequest] = None):
    """
    Start Google Drive device authorization flow.
    
    Client credentials are loaded from Secret Manager ('gdrive-client-credentials')
    unless explicitly provided in the request body.
    
    After starting, poll /auth/gdrive/device/{device_code} to check for completion.
    """
    manager = get_credential_manager()
    
    try:
        device_info = manager.start_gdrive_device_auth(
            client_id=request.client_id if request else None,
            client_secret=request.client_secret if request else None
        )
        
        return DeviceAuthStartResponse(
            device_code=device_info.device_code,
            user_code=device_info.user_code,
            verification_url=device_info.verification_url,
            expires_in=device_info.expires_in,
            interval=device_info.interval,
            instructions=f"Visit {device_info.verification_url} and enter code: {device_info.user_code}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start Google Drive device auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gdrive/device/{device_code}", response_model=DeviceAuthPollResponse)
async def poll_gdrive_device_auth(device_code: str):
    """
    Poll for Google Drive device authorization completion.
    """
    manager = get_credential_manager()
    
    status, data = manager.poll_device_auth("gdrive", device_code)
    
    return DeviceAuthPollResponse(
        status=status,
        message=data.get("message") if data else None,
        credentials_saved=(status == "complete")
    )


# ===========================================================================
# Alert Testing
# ===========================================================================

@router.post("/test-alert")
async def test_credential_alert(background_tasks: BackgroundTasks):
    """
    Test the credential alert mechanism.
    
    Sends a test alert to Discord if configured.
    """
    settings = get_settings()
    discord_url = settings.get_secret("discord-alert-webhook")
    
    if not discord_url:
        raise HTTPException(
            status_code=400,
            detail="Discord alert webhook not configured"
        )
    
    manager = get_credential_manager()
    
    # Create a fake invalid result for testing
    from backend.services.credential_manager import CredentialCheckResult
    test_results = [
        CredentialCheckResult(
            service="test",
            status=CredentialStatus.INVALID,
            message="This is a test alert",
            last_checked=datetime.utcnow()
        )
    ]
    
    background_tasks.add_task(
        manager.send_credential_alert,
        test_results,
        discord_url
    )
    
    return {"message": "Test alert queued"}
