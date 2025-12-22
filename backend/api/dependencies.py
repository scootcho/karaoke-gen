"""
FastAPI dependencies for authentication and authorization.
"""
import logging
import secrets
from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple, Callable
from fastapi import Depends, HTTPException, Header, Query, Request, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.services.auth_service import get_auth_service, UserType, AuthService


logger = logging.getLogger(__name__)


def generate_review_token() -> str:
    """Generate a cryptographically secure review token."""
    return secrets.token_urlsafe(32)


def get_review_token_expiry(hours: int = 24) -> datetime:
    """Get expiry time for a review token."""
    return datetime.now(UTC) + timedelta(hours=hours)


# HTTP Bearer security scheme (Authorization: Bearer <token>)
security = HTTPBearer(auto_error=False)


async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="Access token (alternative to Bearer header)")
) -> Optional[str]:
    """
    Extract access token from request.
    
    Supports three methods (in priority order):
    1. X-Admin-Token header: Used by Cloud Tasks (since OIDC overwrites Authorization)
    2. Authorization header: Authorization: Bearer <token>
    3. Query parameter: ?token=<token> (for download links)
    
    Returns:
        Token string or None
    """
    # Check X-Admin-Token header first (used by Cloud Tasks)
    # Cloud Tasks OIDC token overwrites Authorization header, so we use a custom header
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token:
        return admin_token
    
    # Try Authorization header
    if credentials:
        return credentials.credentials
    
    # Try query parameter
    if token:
        return token
    
    return None


async def require_auth(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None)
) -> Tuple[str, UserType, int]:
    """
    Require authentication for an endpoint.
    
    Returns:
        (token, user_type, remaining_uses)
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    # Get token from request
    token_str = await get_token_from_request(request, credentials, token)
    
    if not token_str:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token via Authorization header or ?token= parameter"
        )
    
    # Validate token
    is_valid, user_type, remaining_uses, message = auth_service.validate_token(token_str)
    
    if not is_valid:
        # Log more details for debugging token issues
        auth_header = request.headers.get("Authorization", "")
        logger.warning(
            f"Authentication failed: {message}. "
            f"Token provided: {bool(token_str)}, "
            f"Token length: {len(token_str) if token_str else 0}, "
            f"Auth header present: {bool(auth_header)}, "
            f"Header prefix: {auth_header[:20] if auth_header else 'none'}..."
        )
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {message}"
        )
    
    logger.info(f"Authenticated as {user_type} (remaining: {remaining_uses})")
    
    return token_str, user_type, remaining_uses


async def require_admin(
    auth_data: Tuple[str, UserType, int] = Depends(require_auth)
) -> Tuple[str, UserType, int]:
    """
    Require admin access for an endpoint.
    
    Returns:
        (token, user_type, remaining_uses)
        
    Raises:
        HTTPException: 403 if user is not admin
    """
    token, user_type, remaining_uses = auth_data
    
    if user_type != UserType.ADMIN:
        logger.warning(f"Admin access denied for {user_type} user")
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    
    return token, user_type, remaining_uses


def optional_auth(
    auth_service: AuthService = Depends(get_auth_service),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None)
) -> Optional[Tuple[str, UserType, int]]:
    """
    Optional authentication - doesn't fail if no token provided.
    
    Useful for endpoints that have different behavior for authenticated users.
    
    Returns:
        (token, user_type, remaining_uses) if authenticated, None otherwise
    """
    # Get token
    token_str = None
    if credentials:
        token_str = credentials.credentials
    elif token:
        token_str = token
    
    if not token_str:
        return None
    
    # Validate token
    is_valid, user_type, remaining_uses, message = auth_service.validate_token(token_str)
    
    if not is_valid:
        logger.debug(f"Optional auth failed: {message}")
        return None
    
    return token_str, user_type, remaining_uses


def require_review_auth_factory(job_id_param: str = "job_id"):
    """
    Factory to create a review authentication dependency.
    
    Accepts either:
    1. Full user authentication (admin/user token)
    2. Job-specific review token (only valid for the specific job)
    
    Args:
        job_id_param: Name of the path parameter containing the job ID
    
    Returns:
        Dependency function that validates review access
    """
    async def require_review_auth(
        request: Request,
        job_id: str = Path(...),
        review_token: Optional[str] = Query(None, description="Job-specific review token"),
        auth_service: AuthService = Depends(get_auth_service),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        token: Optional[str] = Query(None, alias="token", description="Full access token")
    ) -> Tuple[str, str]:
        """
        Validate review access for a job.
        
        Returns:
            (job_id, auth_type) where auth_type is "full" or "review_token"
            
        Raises:
            HTTPException: 401 if authentication fails
        """
        # Import here to avoid circular dependency
        from backend.services.job_manager import JobManager
        
        # Try full authentication first
        full_token = None
        if credentials:
            full_token = credentials.credentials
        elif token:
            full_token = token
        
        if full_token:
            is_valid, user_type, remaining_uses, message = auth_service.validate_token(full_token)
            if is_valid:
                logger.info(f"Review access granted via full auth ({user_type}) for job {job_id}")
                return job_id, "full"
        
        # Try review token
        if review_token:
            job_manager = JobManager()
            job = job_manager.get_job(job_id)
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
            # Validate review token matches
            if job.review_token and secrets.compare_digest(job.review_token, review_token):
                # Check expiry if set
                if job.review_token_expires_at:
                    now = datetime.now(UTC)
                    # Handle timezone-naive datetimes from Firestore
                    expiry = job.review_token_expires_at
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=UTC)
                    
                    if now > expiry:
                        logger.warning(f"Review token expired for job {job_id}")
                        raise HTTPException(
                            status_code=401,
                            detail="Review token has expired. Please request a new review link."
                        )
                
                logger.info(f"Review access granted via review_token for job {job_id}")
                return job_id, "review_token"
            else:
                logger.warning(f"Invalid review token for job {job_id}")
        
        # No valid authentication
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide either a full access token or a valid review_token for this job."
        )
    
    return require_review_auth


# Default instance for most review endpoints
require_review_auth = require_review_auth_factory()
