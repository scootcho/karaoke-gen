"""
FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import Optional, Tuple
from fastapi import Depends, HTTPException, Header, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.services.auth_service import get_auth_service, UserType, AuthService


logger = logging.getLogger(__name__)


# HTTP Bearer security scheme (Authorization: Bearer <token>)
security = HTTPBearer(auto_error=False)


async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="Access token (alternative to Bearer header)")
) -> Optional[str]:
    """
    Extract access token from request.
    
    Supports two methods:
    1. Authorization header: Authorization: Bearer <token>
    2. Query parameter: ?token=<token> (for download links)
    
    Returns:
        Token string or None
    """
    # Try Authorization header first
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
