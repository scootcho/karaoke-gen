"""
Authentication service for karaoke backend.

Provides token-based authentication with support for:
- Admin tokens (hardcoded in environment)
- User tokens (stored in Firestore)
- Usage tracking and limits
- Token management API

This is designed to be extensible for future Stripe integration
and admin dashboard functionality.
"""
import logging
import hashlib
import time
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from backend.services.firestore_service import FirestoreService
from backend.config import get_settings


logger = logging.getLogger(__name__)


class UserType(str, Enum):
    """User access levels."""
    ADMIN = "admin"          # Unlimited access, can manage tokens
    UNLIMITED = "unlimited"  # Unlimited karaoke generation
    LIMITED = "limited"      # Limited number of uses
    STRIPE = "stripe"        # Paid access via Stripe (future)


class AuthService:
    """Service for authentication and token management."""
    
    def __init__(self):
        """Initialize auth service."""
        self.firestore = FirestoreService()
        self.settings = get_settings()
        self._init_admin_tokens()
    
    def _init_admin_tokens(self):
        """Load admin tokens from environment variables."""
        # Get admin tokens from secret manager or env vars
        admin_tokens_str = self.settings.admin_tokens or ""
        self.admin_tokens = [t.strip() for t in admin_tokens_str.split(",") if t.strip()]
        
        if self.admin_tokens:
            logger.info(f"Loaded {len(self.admin_tokens)} admin token(s)")
        else:
            logger.warning("No admin tokens configured! Set ADMIN_TOKENS environment variable.")
    
    def validate_token(self, token: str) -> Tuple[bool, UserType, int, str]:
        """
        Validate an access token.
        
        Returns:
            (is_valid, user_type, remaining_uses, message)
            remaining_uses: -1 = unlimited, 0 = exhausted, >0 = remaining count
        """
        if not token:
            return False, UserType.LIMITED, 0, "No token provided"
        
        # Check for admin tokens (highest priority)
        if token in self.admin_tokens:
            logger.info("Admin token validated")
            return True, UserType.ADMIN, -1, "Admin access granted"
        
        # Check stored tokens in Firestore
        token_data = self.firestore.get_token(token)
        
        if not token_data:
            return False, UserType.LIMITED, 0, "Invalid token"
        
        # Check if token is active
        if not token_data.get("active", True):
            return False, UserType(token_data["type"]), 0, "Token has been revoked"
        
        token_type = UserType(token_data["type"])
        max_uses = token_data.get("max_uses", -1)
        
        # UNLIMITED tokens: no usage limits
        if token_type == UserType.UNLIMITED:
            return True, token_type, -1, "Unlimited access granted"
        
        # LIMITED tokens: check usage count
        if token_type == UserType.LIMITED:
            if max_uses <= 0:  # -1 means unlimited
                return True, token_type, -1, "Limited token with unlimited uses"
            
            current_uses = token_data.get("usage_count", 0)
            remaining = max_uses - current_uses
            
            if remaining <= 0:
                return False, token_type, 0, "Token usage limit exceeded"
            
            return True, token_type, remaining, f"Limited token: {remaining} uses remaining"
        
        # STRIPE tokens: check expiration and usage
        if token_type == UserType.STRIPE:
            expires_at = token_data.get("expires_at")
            
            if expires_at:
                # expires_at is stored as timestamp
                if time.time() > expires_at:
                    return False, token_type, 0, "Token has expired"
            
            if max_uses > 0:
                current_uses = token_data.get("usage_count", 0)
                remaining = max_uses - current_uses
                
                if remaining <= 0:
                    return False, token_type, 0, "Token usage limit exceeded"
                
                return True, token_type, remaining, f"Stripe token: {remaining} uses remaining"
            
            return True, token_type, -1, "Stripe access granted"
        
        return False, UserType.LIMITED, 0, "Unknown token type"
    
    def increment_token_usage(self, token: str, job_id: str) -> bool:
        """
        Increment usage count for a token and track the job.
        
        Args:
            token: The access token
            job_id: The job ID being created
            
        Returns:
            True if usage was tracked, False otherwise
        """
        # Validate token first
        is_valid, user_type, remaining_uses, message = self.validate_token(token)
        
        if not is_valid:
            logger.warning(f"Cannot increment usage for invalid token: {message}")
            return False
        
        # Don't track usage for admin or unlimited tokens
        if user_type in [UserType.ADMIN, UserType.UNLIMITED]:
            logger.debug(f"Skipping usage tracking for {user_type} token")
            return True
        
        # For admin tokens (not in Firestore), no tracking needed
        if token in self.admin_tokens:
            return True
        
        # Increment usage in Firestore
        try:
            self.firestore.increment_token_usage(token, job_id)
            logger.info(f"Incremented usage for token (remaining: {remaining_uses - 1})")
            return True
        except Exception as e:
            logger.error(f"Failed to increment token usage: {e}")
            return False
    
    def create_token(
        self,
        token_value: str,
        token_type: UserType,
        max_uses: int = -1,
        expires_at: Optional[float] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new access token.
        
        Args:
            token_value: The actual token string (should be secure random string)
            token_type: Type of access (admin, unlimited, limited, stripe)
            max_uses: Maximum number of uses (-1 = unlimited)
            expires_at: Expiration timestamp (None = no expiration)
            created_by: Admin token that created this token
            
        Returns:
            Token data dictionary
        """
        token_data = {
            "token": token_value,
            "type": token_type.value,
            "max_uses": max_uses,
            "usage_count": 0,
            "active": True,
            "created_at": time.time(),
            "created_by": created_by,
            "expires_at": expires_at,
            "jobs": []
        }
        
        self.firestore.create_token(token_value, token_data)
        logger.info(f"Created new {token_type} token with max_uses={max_uses}")
        
        return token_data
    
    def revoke_token(self, token: str, revoked_by: Optional[str] = None) -> bool:
        """
        Revoke an access token.
        
        Args:
            token: The token to revoke
            revoked_by: Admin token that revoked this token
            
        Returns:
            True if revoked, False if token not found
        """
        try:
            self.firestore.update_token(token, {
                "active": False,
                "revoked_at": time.time(),
                "revoked_by": revoked_by
            })
            logger.info(f"Revoked token")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    def list_tokens(self, include_inactive: bool = False) -> list:
        """
        List all tokens (admin only).
        
        Args:
            include_inactive: Whether to include revoked tokens
            
        Returns:
            List of token data dictionaries (with sensitive data masked)
        """
        try:
            tokens = self.firestore.list_tokens()
            
            # Filter inactive if requested
            if not include_inactive:
                tokens = [t for t in tokens if t.get("active", True)]
            
            # Mask token values for security (show only first 8 chars)
            for token in tokens:
                if "token" in token and len(token["token"]) > 8:
                    token["token"] = token["token"][:8] + "..."
            
            return tokens
        except Exception as e:
            logger.error(f"Failed to list tokens: {e}")
            return []
    
    def get_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a token (for admin dashboard).
        
        Returns:
            Token data or None if not found
        """
        # Check if it's an admin token (not stored in Firestore)
        if token in self.admin_tokens:
            return {
                "token": token[:8] + "...",
                "type": UserType.ADMIN.value,
                "max_uses": -1,
                "usage_count": 0,
                "active": True,
                "source": "environment"
            }
        
        # Get from Firestore
        token_data = self.firestore.get_token(token)
        
        if token_data and "token" in token_data:
            # Mask the full token value
            token_data["token"] = token_data["token"][:8] + "..."
        
        return token_data


# Global instance
_auth_service = None


def get_auth_service() -> AuthService:
    """Get the global auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service

