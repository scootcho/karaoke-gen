"""
Admin API routes for rate limit management.

Handles:
- Rate limit statistics and monitoring
- Blocklist management (disposable domains, blocked emails, blocked IPs)
- User override management (whitelist/bypass permissions)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from backend.api.dependencies import require_admin
from backend.services.auth_service import AuthResult
from backend.services.rate_limit_service import get_rate_limit_service, RateLimitService
from backend.services.email_validation_service import get_email_validation_service, EmailValidationService
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/rate-limits", tags=["admin", "rate-limits"])


# =============================================================================
# Response Models
# =============================================================================

class RateLimitStatsResponse(BaseModel):
    """Current rate limit statistics."""
    # Configuration
    jobs_per_day_limit: int
    youtube_uploads_per_day_limit: int
    beta_ip_per_day_limit: int
    rate_limiting_enabled: bool

    # Current usage
    youtube_uploads_today: int
    youtube_uploads_remaining: int

    # Blocklist stats
    disposable_domains_count: int
    blocked_emails_count: int
    blocked_ips_count: int

    # User override stats
    total_overrides: int


class UserRateLimitStatusResponse(BaseModel):
    """Rate limit status for a specific user."""
    email: str
    jobs_today: int
    jobs_limit: int
    jobs_remaining: int
    has_bypass: bool
    custom_limit: Optional[int]
    bypass_reason: Optional[str]


class BlocklistsResponse(BaseModel):
    """All blocklist data."""
    disposable_domains: List[str]
    blocked_emails: List[str]
    blocked_ips: List[str]
    updated_at: Optional[datetime]
    updated_by: Optional[str]


class DomainRequest(BaseModel):
    """Request to add/remove a domain."""
    domain: str


class EmailRequest(BaseModel):
    """Request to add/remove an email."""
    email: str


class IPRequest(BaseModel):
    """Request to add/remove an IP."""
    ip_address: str


class UserOverride(BaseModel):
    """User override configuration."""
    email: str
    bypass_job_limit: bool
    custom_daily_job_limit: Optional[int]
    reason: str
    created_by: str
    created_at: datetime


class UserOverrideRequest(BaseModel):
    """Request to set/update a user override."""
    bypass_job_limit: bool = False
    custom_daily_job_limit: Optional[int] = None
    reason: str


class UserOverridesListResponse(BaseModel):
    """List of all user overrides."""
    overrides: List[UserOverride]
    total: int


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool
    message: str


# =============================================================================
# Statistics Endpoints
# =============================================================================

@router.get("/stats", response_model=RateLimitStatsResponse)
async def get_rate_limit_stats(
    auth_result: AuthResult = Depends(require_admin),
):
    """
    Get current rate limit statistics.

    Returns configuration values, current usage counts, and blocklist stats.
    """
    rate_limit_service = get_rate_limit_service()
    email_validation = get_email_validation_service()

    # Get YouTube uploads today
    youtube_today = rate_limit_service.get_youtube_uploads_today()
    youtube_limit = settings.rate_limit_youtube_uploads_per_day
    youtube_remaining = max(0, youtube_limit - youtube_today) if youtube_limit > 0 else -1

    # Get blocklist stats
    blocklist_stats = email_validation.get_blocklist_stats()

    # Get override count
    overrides = rate_limit_service.get_all_overrides()

    return RateLimitStatsResponse(
        jobs_per_day_limit=settings.rate_limit_jobs_per_day,
        youtube_uploads_per_day_limit=settings.rate_limit_youtube_uploads_per_day,
        beta_ip_per_day_limit=settings.rate_limit_beta_ip_per_day,
        rate_limiting_enabled=settings.enable_rate_limiting,
        youtube_uploads_today=youtube_today,
        youtube_uploads_remaining=youtube_remaining,
        disposable_domains_count=blocklist_stats["disposable_domains_count"],
        blocked_emails_count=blocklist_stats["blocked_emails_count"],
        blocked_ips_count=blocklist_stats["blocked_ips_count"],
        total_overrides=len(overrides),
    )


@router.get("/users/{email}", response_model=UserRateLimitStatusResponse)
async def get_user_rate_limit_status(
    email: str,
    auth_result: AuthResult = Depends(require_admin),
):
    """
    Get rate limit status for a specific user.

    Returns their current usage and any override settings.
    """
    rate_limit_service = get_rate_limit_service()

    jobs_today = rate_limit_service.get_user_job_count_today(email)
    override = rate_limit_service.get_user_override(email)

    if override:
        has_bypass = override.get("bypass_job_limit", False)
        custom_limit = override.get("custom_daily_job_limit")
        bypass_reason = override.get("reason")
        jobs_limit = custom_limit if custom_limit is not None else settings.rate_limit_jobs_per_day
    else:
        has_bypass = False
        custom_limit = None
        bypass_reason = None
        jobs_limit = settings.rate_limit_jobs_per_day

    jobs_remaining = max(0, jobs_limit - jobs_today) if not has_bypass else -1

    return UserRateLimitStatusResponse(
        email=email,
        jobs_today=jobs_today,
        jobs_limit=jobs_limit,
        jobs_remaining=jobs_remaining,
        has_bypass=has_bypass,
        custom_limit=custom_limit,
        bypass_reason=bypass_reason,
    )


# =============================================================================
# Blocklist Management Endpoints
# =============================================================================

@router.get("/blocklists", response_model=BlocklistsResponse)
async def get_blocklists(
    auth_result: AuthResult = Depends(require_admin),
):
    """
    Get all blocklist data.

    Returns disposable domains, blocked emails, and blocked IPs.
    """
    email_validation = get_email_validation_service()

    # Force refresh to get latest data
    config = email_validation.get_blocklist_config(force_refresh=True)

    # Get the raw document for metadata
    from google.cloud import firestore
    from backend.services.firestore_service import get_firestore_client
    from backend.services.email_validation_service import BLOCKLISTS_COLLECTION, BLOCKLIST_CONFIG_DOC

    db = get_firestore_client()
    doc = db.collection(BLOCKLISTS_COLLECTION).document(BLOCKLIST_CONFIG_DOC).get()

    updated_at = None
    updated_by = None
    if doc.exists:
        data = doc.to_dict()
        updated_at = data.get("updated_at")
        updated_by = data.get("updated_by")

    return BlocklistsResponse(
        disposable_domains=sorted(list(config["disposable_domains"])),
        blocked_emails=sorted(list(config["blocked_emails"])),
        blocked_ips=sorted(list(config["blocked_ips"])),
        updated_at=updated_at,
        updated_by=updated_by,
    )


@router.post("/blocklists/disposable-domains", response_model=SuccessResponse)
async def add_disposable_domain(
    request: DomainRequest,
    auth_result: AuthResult = Depends(require_admin),
):
    """Add a domain to the disposable domains blocklist."""
    email_validation = get_email_validation_service()

    domain = request.domain.lower().strip()
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid domain format")

    email_validation.add_disposable_domain(domain, auth_result.user_email)

    return SuccessResponse(
        success=True,
        message=f"Domain '{domain}' added to disposable domains blocklist"
    )


@router.delete("/blocklists/disposable-domains/{domain}", response_model=SuccessResponse)
async def remove_disposable_domain(
    domain: str,
    auth_result: AuthResult = Depends(require_admin),
):
    """Remove a domain from the disposable domains blocklist."""
    email_validation = get_email_validation_service()

    domain = domain.lower().strip()
    if not email_validation.remove_disposable_domain(domain, auth_result.user_email):
        raise HTTPException(status_code=404, detail="Domain not found in blocklist")

    return SuccessResponse(
        success=True,
        message=f"Domain '{domain}' removed from disposable domains blocklist"
    )


@router.post("/blocklists/blocked-emails", response_model=SuccessResponse)
async def add_blocked_email(
    request: EmailRequest,
    auth_result: AuthResult = Depends(require_admin),
):
    """Add an email to the blocked emails list."""
    email_validation = get_email_validation_service()

    email = request.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    email_validation.add_blocked_email(email, auth_result.user_email)

    return SuccessResponse(
        success=True,
        message=f"Email '{email}' added to blocked emails list"
    )


@router.delete("/blocklists/blocked-emails/{email}", response_model=SuccessResponse)
async def remove_blocked_email(
    email: str,
    auth_result: AuthResult = Depends(require_admin),
):
    """Remove an email from the blocked emails list."""
    email_validation = get_email_validation_service()

    email = email.lower().strip()
    if not email_validation.remove_blocked_email(email, auth_result.user_email):
        raise HTTPException(status_code=404, detail="Email not found in blocklist")

    return SuccessResponse(
        success=True,
        message=f"Email '{email}' removed from blocked emails list"
    )


@router.post("/blocklists/blocked-ips", response_model=SuccessResponse)
async def add_blocked_ip(
    request: IPRequest,
    auth_result: AuthResult = Depends(require_admin),
):
    """Add an IP address to the blocked IPs list."""
    email_validation = get_email_validation_service()

    ip_address = request.ip_address.strip()
    if not ip_address:
        raise HTTPException(status_code=400, detail="Invalid IP address")

    email_validation.add_blocked_ip(ip_address, auth_result.user_email)

    return SuccessResponse(
        success=True,
        message=f"IP '{ip_address}' added to blocked IPs list"
    )


@router.delete("/blocklists/blocked-ips/{ip_address}", response_model=SuccessResponse)
async def remove_blocked_ip(
    ip_address: str,
    auth_result: AuthResult = Depends(require_admin),
):
    """Remove an IP address from the blocked IPs list."""
    email_validation = get_email_validation_service()

    ip_address = ip_address.strip()
    if not email_validation.remove_blocked_ip(ip_address, auth_result.user_email):
        raise HTTPException(status_code=404, detail="IP not found in blocklist")

    return SuccessResponse(
        success=True,
        message=f"IP '{ip_address}' removed from blocked IPs list"
    )


# =============================================================================
# User Override Management Endpoints
# =============================================================================

@router.get("/overrides", response_model=UserOverridesListResponse)
async def get_all_overrides(
    auth_result: AuthResult = Depends(require_admin),
):
    """Get all user overrides."""
    rate_limit_service = get_rate_limit_service()

    overrides_data = rate_limit_service.get_all_overrides()

    overrides = [
        UserOverride(
            email=email,
            bypass_job_limit=data.get("bypass_job_limit", False),
            custom_daily_job_limit=data.get("custom_daily_job_limit"),
            reason=data.get("reason", ""),
            created_by=data.get("created_by", "unknown"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
        )
        for email, data in overrides_data.items()
    ]

    return UserOverridesListResponse(
        overrides=overrides,
        total=len(overrides),
    )


@router.put("/overrides/{email}", response_model=SuccessResponse)
async def set_user_override(
    email: str,
    request: UserOverrideRequest,
    auth_result: AuthResult = Depends(require_admin),
):
    """Set or update a user override."""
    rate_limit_service = get_rate_limit_service()

    email = email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    if not request.reason or len(request.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="Reason is required (min 3 characters)")

    rate_limit_service.set_user_override(
        user_email=email,
        bypass_job_limit=request.bypass_job_limit,
        custom_daily_job_limit=request.custom_daily_job_limit,
        reason=request.reason,
        admin_email=auth_result.user_email,
    )

    return SuccessResponse(
        success=True,
        message=f"Override set for user '{email}'"
    )


@router.delete("/overrides/{email}", response_model=SuccessResponse)
async def remove_user_override(
    email: str,
    auth_result: AuthResult = Depends(require_admin),
):
    """Remove a user override."""
    rate_limit_service = get_rate_limit_service()

    email = email.lower().strip()
    if not rate_limit_service.remove_user_override(email, auth_result.user_email):
        raise HTTPException(status_code=404, detail="Override not found for user")

    return SuccessResponse(
        success=True,
        message=f"Override removed for user '{email}'"
    )
