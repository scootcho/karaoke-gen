"""
User and authentication API routes.

Handles:
- Magic link authentication (send, verify)
- Session management (logout)
- User profile and credits
- Stripe checkout and webhooks
- Admin user management
"""
import logging
from typing import Optional, Tuple
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, EmailStr

from backend.models.user import (
    UserRole,
    UserPublic,
    SendMagicLinkRequest,
    SendMagicLinkResponse,
    VerifyMagicLinkResponse,
    AddCreditsRequest,
    AddCreditsResponse,
    UserListResponse,
)
from backend.services.user_service import get_user_service, UserService
from backend.services.email_service import get_email_service, EmailService
from backend.services.stripe_service import get_stripe_service, StripeService, CREDIT_PACKAGES
from backend.api.dependencies import require_auth, require_admin
from backend.services.auth_service import UserType


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""
    package_id: str
    email: EmailStr


class CreateCheckoutResponse(BaseModel):
    """Response with checkout URL."""
    status: str
    checkout_url: str
    message: str


class CreditPackage(BaseModel):
    """Credit package information."""
    id: str
    credits: int
    price_cents: int
    name: str
    description: str


class CreditPackagesResponse(BaseModel):
    """Response listing available credit packages."""
    packages: list[CreditPackage]


class UserProfileResponse(BaseModel):
    """Response with user profile."""
    user: UserPublic
    has_session: bool


class LogoutResponse(BaseModel):
    """Response after logout."""
    status: str
    message: str


# =============================================================================
# Magic Link Authentication
# =============================================================================

@router.post("/auth/magic-link", response_model=SendMagicLinkResponse)
async def send_magic_link(
    request: SendMagicLinkRequest,
    http_request: Request,
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    """
    Send a magic link email for passwordless authentication.

    The user will receive an email with a link that logs them in.
    Links expire after 15 minutes and can only be used once.
    """
    email = request.email.lower()

    # Get client info for security logging
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    # Create magic link token
    magic_link = user_service.create_magic_link(
        email,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Send email
    sent = email_service.send_magic_link(email, magic_link.token)

    if not sent:
        logger.error(f"Failed to send magic link email to {email}")
        # Don't reveal failure to prevent email enumeration
        # Still return success

    return SendMagicLinkResponse(
        status="success",
        message="If this email is registered, you will receive a sign-in link shortly."
    )


@router.get("/auth/verify", response_model=VerifyMagicLinkResponse)
async def verify_magic_link(
    token: str,
    http_request: Request,
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    """
    Verify a magic link token and create a session.

    Returns a session token that should be stored and used for subsequent requests.
    """
    # Get client info
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    # Verify the magic link
    success, user, message = user_service.verify_magic_link(token)

    if not success or not user:
        raise HTTPException(status_code=401, detail=message)

    # Create session
    session = user_service.create_session(
        user.email,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Check if this is a new user (no previous login)
    if user.total_jobs_created == 0 and not user.last_login_at:
        # Send welcome email
        email_service.send_welcome_email(user.email, user.credits)

    # Return user info
    user_public = UserPublic(
        email=user.email,
        role=user.role,
        credits=user.credits,
        display_name=user.display_name,
        total_jobs_created=user.total_jobs_created,
        total_jobs_completed=user.total_jobs_completed,
    )

    return VerifyMagicLinkResponse(
        status="success",
        session_token=session.token,
        user=user_public,
        message="Successfully signed in"
    )


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(
    authorization: Optional[str] = Header(None),
    user_service: UserService = Depends(get_user_service),
):
    """
    Logout and invalidate the current session.
    """
    if not authorization:
        return LogoutResponse(status="success", message="Already logged out")

    # Extract token from "Bearer <token>"
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    user_service.revoke_session(token)

    return LogoutResponse(status="success", message="Successfully logged out")


# =============================================================================
# User Profile
# =============================================================================

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user(
    authorization: Optional[str] = Header(None),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get the current user's profile.

    Requires a valid session token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Extract token
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    # Validate session
    valid, user, message = user_service.validate_session(token)

    if not valid or not user:
        raise HTTPException(status_code=401, detail=message)

    user_public = UserPublic(
        email=user.email,
        role=user.role,
        credits=user.credits,
        display_name=user.display_name,
        total_jobs_created=user.total_jobs_created,
        total_jobs_completed=user.total_jobs_completed,
    )

    return UserProfileResponse(user=user_public, has_session=True)


# =============================================================================
# Credit Packages & Checkout
# =============================================================================

@router.get("/credits/packages", response_model=CreditPackagesResponse)
async def list_credit_packages():
    """
    List available credit packages for purchase.

    No authentication required - this is public information.
    """
    packages = [
        CreditPackage(
            id=pkg_id,
            credits=pkg["credits"],
            price_cents=pkg["price_cents"],
            name=pkg["name"],
            description=pkg["description"],
        )
        for pkg_id, pkg in CREDIT_PACKAGES.items()
    ]

    return CreditPackagesResponse(packages=packages)


@router.post("/credits/checkout", response_model=CreateCheckoutResponse)
async def create_checkout(
    request: CreateCheckoutRequest,
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Create a Stripe checkout session for purchasing credits.

    Returns a URL to redirect the user to Stripe's hosted checkout page.
    No authentication required - email is provided in the request.
    """
    if not stripe_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment processing is not available")

    success, checkout_url, message = stripe_service.create_checkout_session(
        package_id=request.package_id,
        user_email=request.email,
    )

    if not success or not checkout_url:
        raise HTTPException(status_code=400, detail=message)

    return CreateCheckoutResponse(
        status="success",
        checkout_url=checkout_url,
        message=message,
    )


# =============================================================================
# Stripe Webhooks
# =============================================================================

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    stripe_service: StripeService = Depends(get_stripe_service),
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe about payment status.
    It verifies the webhook signature and processes the event.
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    # Get raw body for signature verification
    payload = await request.body()

    # Verify signature
    valid, event, message = stripe_service.verify_webhook_signature(payload, stripe_signature)

    if not valid:
        logger.warning(f"Invalid Stripe webhook signature: {message}")
        raise HTTPException(status_code=400, detail=message)

    # Handle the event
    event_type = event.get("type")
    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        # Process the completed checkout
        success, user_email, credits, msg = stripe_service.handle_checkout_completed(session)

        if success and user_email and credits > 0:
            # Add credits to user account
            ok, new_balance, credit_msg = user_service.add_credits(
                email=user_email,
                amount=credits,
                reason="stripe_purchase",
                stripe_session_id=session.get("id"),
            )

            if ok:
                # Send confirmation email
                email_service.send_credits_added(user_email, credits, new_balance)
                logger.info(f"Added {credits} credits to {user_email}, new balance: {new_balance}")
            else:
                logger.error(f"Failed to add credits: {credit_msg}")

    elif event_type == "checkout.session.expired":
        logger.info(f"Checkout session expired: {event['data']['object'].get('id')}")

    elif event_type == "payment_intent.payment_failed":
        logger.warning(f"Payment failed: {event['data']['object'].get('id')}")

    # Return 200 to acknowledge receipt (Stripe will retry on non-2xx)
    return {"status": "received", "type": event_type}


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get("/admin/users", response_model=UserListResponse)
async def list_users(
    limit: int = 100,
    include_inactive: bool = False,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    List all users (admin only).
    """
    users = user_service.list_users(limit=limit, include_inactive=include_inactive)

    users_public = [
        UserPublic(
            email=u.email,
            role=u.role,
            credits=u.credits,
            display_name=u.display_name,
            total_jobs_created=u.total_jobs_created,
            total_jobs_completed=u.total_jobs_completed,
        )
        for u in users
    ]

    return UserListResponse(users=users_public, total=len(users_public))


@router.post("/admin/credits", response_model=AddCreditsResponse)
async def add_credits_to_user(
    request: AddCreditsRequest,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    """
    Add credits to a user's account (admin only).

    Use this to grant free credits to users, e.g., for beta testers or promotions.
    """
    admin_token, user_type, _ = auth_data

    # Get admin email from somewhere (could enhance auth to track this)
    admin_email = "admin"  # Placeholder - could be enhanced

    success, new_balance, message = user_service.add_credits(
        email=request.email,
        amount=request.amount,
        reason=request.reason,
        admin_email=admin_email,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Send notification email
    if request.amount > 0:
        email_service.send_credits_added(request.email, request.amount, new_balance)

    return AddCreditsResponse(
        status="success",
        email=request.email,
        credits_added=request.amount,
        new_balance=new_balance,
        message=message,
    )


@router.post("/admin/users/{email}/disable")
async def disable_user(
    email: str,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    Disable a user account (admin only).
    """
    success = user_service.disable_user(email, admin_email="admin")

    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": f"User {email} has been disabled"}


@router.post("/admin/users/{email}/enable")
async def enable_user(
    email: str,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    Enable a user account (admin only).
    """
    success = user_service.enable_user(email, admin_email="admin")

    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": f"User {email} has been enabled"}


@router.post("/admin/users/{email}/role")
async def set_user_role(
    email: str,
    role: UserRole,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    Set a user's role (admin only).
    """
    success = user_service.set_user_role(email, role, admin_email="admin")

    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": f"User {email} role set to {role.value}"}
