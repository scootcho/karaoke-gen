"""
User model for authentication and credits.

Supports:
- Magic link authentication (email-based)
- Credit system for karaoke generation
- Role-based access control (user/admin)
- Stripe integration for payments
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles for access control."""
    USER = "user"
    ADMIN = "admin"


class CreditTransaction(BaseModel):
    """Record of a credit transaction."""
    id: str
    amount: int  # Positive = add, negative = deduct
    reason: str  # e.g., "purchase", "refund", "admin_grant", "job_creation"
    job_id: Optional[str] = None
    stripe_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # Admin email if granted by admin


class User(BaseModel):
    """
    User model stored in Firestore.

    Users are identified by email address. Authentication is via magic links
    (no passwords). Credits are consumed when creating karaoke jobs.
    """
    email: str  # Primary identifier
    role: UserRole = UserRole.USER
    credits: int = 0

    # Stripe integration
    stripe_customer_id: Optional[str] = None

    # Account state
    is_active: bool = True
    email_verified: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    # Credit history (last 100 transactions)
    credit_transactions: List[CreditTransaction] = Field(default_factory=list)

    # Job tracking
    total_jobs_created: int = 0
    total_jobs_completed: int = 0

    # Optional profile fields for future use
    display_name: Optional[str] = None


class MagicLinkToken(BaseModel):
    """
    Magic link token for passwordless authentication.

    Tokens are short-lived (15 minutes) and single-use.
    Stored in Firestore with automatic TTL.
    """
    token: str  # Secure random token
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    used: bool = False
    used_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class Session(BaseModel):
    """
    User session for authenticated requests.

    Sessions are created after successful magic link verification.
    Sessions expire after 7 days of inactivity or 30 days absolute.
    """
    token: str  # Secure random session token
    user_email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True


# Pydantic models for API requests/responses

class SendMagicLinkRequest(BaseModel):
    """Request to send a magic link email."""
    email: str


class SendMagicLinkResponse(BaseModel):
    """Response after sending magic link."""
    status: str
    message: str


class VerifyMagicLinkRequest(BaseModel):
    """Request to verify a magic link token."""
    token: str


class VerifyMagicLinkResponse(BaseModel):
    """Response after verifying magic link."""
    status: str
    session_token: str
    user: "UserPublic"
    message: str


class UserPublic(BaseModel):
    """Public user information (safe to expose to frontend)."""
    email: str
    role: UserRole
    credits: int
    display_name: Optional[str] = None
    total_jobs_created: int = 0
    total_jobs_completed: int = 0


class AddCreditsRequest(BaseModel):
    """Admin request to add credits to a user."""
    email: str
    amount: int
    reason: str = "admin_grant"


class AddCreditsResponse(BaseModel):
    """Response after adding credits."""
    status: str
    email: str
    credits_added: int
    new_balance: int
    message: str


class UserListResponse(BaseModel):
    """Response for listing users (admin only)."""
    users: List[UserPublic]
    total: int
