"""
User service for authentication, credits, and user management.

Handles:
- Magic link authentication (send, verify)
- Session management
- Credit operations (add, deduct, refund)
- User CRUD operations
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from backend.config import get_settings
from backend.models.user import (
    User,
    UserRole,
    UserPublic,
    MagicLinkToken,
    Session,
    CreditTransaction,
)


logger = logging.getLogger(__name__)


# Collection names
USERS_COLLECTION = "users"
MAGIC_LINKS_COLLECTION = "magic_links"
SESSIONS_COLLECTION = "sessions"

# Token/session configuration
MAGIC_LINK_EXPIRY_MINUTES = 15
SESSION_EXPIRY_DAYS = 7
SESSION_ABSOLUTE_EXPIRY_DAYS = 30
MAX_CREDIT_TRANSACTIONS = 100  # Keep last N transactions


class UserService:
    """Service for user management and authentication."""

    def __init__(self):
        """Initialize user service with Firestore client."""
        self.settings = get_settings()
        self.db = firestore.Client(project=self.settings.google_cloud_project)

    # =========================================================================
    # User CRUD Operations
    # =========================================================================

    def get_user(self, email: str) -> Optional[User]:
        """Get a user by email."""
        try:
            doc_ref = self.db.collection(USERS_COLLECTION).document(email.lower())
            doc = doc_ref.get()

            if not doc.exists:
                return None

            return User(**doc.to_dict())
        except Exception as e:
            logger.error(f"Error getting user {email}: {e}")
            return None

    def get_or_create_user(self, email: str) -> User:
        """Get existing user or create a new one."""
        email = email.lower()
        user = self.get_user(email)

        if user:
            return user

        # Create new user
        user = User(email=email)
        self._save_user(user)
        logger.info(f"Created new user: {email}")
        return user

    def _save_user(self, user: User) -> None:
        """Save user to Firestore."""
        try:
            user.updated_at = datetime.utcnow()
            doc_ref = self.db.collection(USERS_COLLECTION).document(user.email.lower())
            doc_ref.set(user.model_dump(mode='json'))
        except Exception as e:
            logger.error(f"Error saving user {user.email}: {e}")
            raise

    def update_user(self, email: str, **updates) -> Optional[User]:
        """Update user fields."""
        try:
            updates['updated_at'] = datetime.utcnow()
            doc_ref = self.db.collection(USERS_COLLECTION).document(email.lower())
            doc_ref.update(updates)
            return self.get_user(email)
        except Exception as e:
            logger.error(f"Error updating user {email}: {e}")
            return None

    def list_users(self, limit: int = 100, include_inactive: bool = False) -> List[User]:
        """List all users (admin only)."""
        try:
            query = self.db.collection(USERS_COLLECTION)

            if not include_inactive:
                query = query.where(filter=FieldFilter('is_active', '==', True))

            query = query.order_by('created_at', direction=firestore.Query.DESCENDING)
            query = query.limit(limit)

            docs = query.stream()
            return [User(**doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    def get_user_public(self, email: str) -> Optional[UserPublic]:
        """Get public user info."""
        user = self.get_user(email)
        if not user:
            return None

        return UserPublic(
            email=user.email,
            role=user.role,
            credits=user.credits,
            display_name=user.display_name,
            total_jobs_created=user.total_jobs_created,
            total_jobs_completed=user.total_jobs_completed,
        )

    # =========================================================================
    # Magic Link Authentication
    # =========================================================================

    def create_magic_link(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MagicLinkToken:
        """
        Create a magic link token for email authentication.

        Returns the token object. The actual sending of the email
        should be handled by the caller (or an email service).
        """
        email = email.lower()

        # Ensure user exists
        self.get_or_create_user(email)

        # Generate secure token
        token = secrets.token_urlsafe(32)

        magic_link = MagicLinkToken(
            token=token,
            email=email,
            expires_at=datetime.utcnow() + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Save to Firestore
        doc_ref = self.db.collection(MAGIC_LINKS_COLLECTION).document(token)
        doc_ref.set(magic_link.model_dump(mode='json'))

        logger.info(f"Created magic link for {email}")
        return magic_link

    def verify_magic_link(self, token: str) -> Tuple[bool, Optional[User], str]:
        """
        Verify a magic link token using a Firestore transaction to prevent race conditions.

        Returns:
            (success, user, message)
        """
        try:
            doc_ref = self.db.collection(MAGIC_LINKS_COLLECTION).document(token)

            @firestore.transactional
            def verify_in_transaction(transaction):
                """Atomically verify and mark magic link as used."""
                doc = doc_ref.get(transaction=transaction)

                if not doc.exists:
                    return False, None, "Invalid or expired link"

                magic_link = MagicLinkToken(**doc.to_dict())

                # Check if already used
                if magic_link.used:
                    return False, None, "This link has already been used"

                # Check expiry
                if datetime.utcnow() > magic_link.expires_at:
                    return False, None, "This link has expired"

                # Mark as used atomically within transaction
                transaction.update(doc_ref, {
                    'used': True,
                    'used_at': datetime.utcnow()
                })

                return True, magic_link.email, "Success"

            # Execute the transaction
            transaction = self.db.transaction()
            success, email_or_error, message = verify_in_transaction(transaction)

            if not success:
                return False, None, message

            # Get user and mark email as verified (outside transaction)
            user = self.get_user(email_or_error)
            if user:
                self.update_user(
                    email_or_error,
                    email_verified=True,
                    last_login_at=datetime.utcnow()
                )
                user = self.get_user(email_or_error)  # Refresh

            logger.info(f"Magic link verified for {email_or_error}")
            return True, user, "Successfully authenticated"

        except Exception as e:
            logger.exception(f"Error verifying magic link: {e}")
            return False, None, "An error occurred during verification"

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        user_email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """Create a new session for an authenticated user."""
        token = secrets.token_urlsafe(32)

        session = Session(
            token=token,
            user_email=user_email.lower(),
            expires_at=datetime.utcnow() + timedelta(days=SESSION_ABSOLUTE_EXPIRY_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        doc_ref = self.db.collection(SESSIONS_COLLECTION).document(token)
        doc_ref.set(session.model_dump(mode='json'))

        logger.info(f"Created session for {user_email}")
        return session

    def validate_session(self, token: str) -> Tuple[bool, Optional[User], str]:
        """
        Validate a session token.

        Returns:
            (valid, user, message)
        """
        try:
            doc_ref = self.db.collection(SESSIONS_COLLECTION).document(token)
            doc = doc_ref.get()

            if not doc.exists:
                return False, None, "Invalid session"

            session = Session(**doc.to_dict())

            # Check if active
            if not session.is_active:
                return False, None, "Session has been revoked"

            # Check expiry
            if datetime.utcnow() > session.expires_at:
                return False, None, "Session has expired"

            # Check inactivity (7 days)
            inactivity_limit = datetime.utcnow() - timedelta(days=SESSION_EXPIRY_DAYS)
            if session.last_activity_at < inactivity_limit:
                return False, None, "Session expired due to inactivity"

            # Update last activity
            doc_ref.update({'last_activity_at': datetime.utcnow()})

            # Get user
            user = self.get_user(session.user_email)
            if not user:
                return False, None, "User not found"

            if not user.is_active:
                return False, None, "User account is disabled"

            return True, user, "Valid session"

        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False, None, "An error occurred during validation"

    def revoke_session(self, token: str) -> bool:
        """Revoke a session (logout)."""
        try:
            doc_ref = self.db.collection(SESSIONS_COLLECTION).document(token)
            doc_ref.update({'is_active': False})
            logger.info("Session revoked")
            return True
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return False

    def revoke_all_sessions(self, user_email: str) -> int:
        """Revoke all sessions for a user."""
        try:
            query = self.db.collection(SESSIONS_COLLECTION).where(
                filter=FieldFilter('user_email', '==', user_email.lower())
            ).where(
                filter=FieldFilter('is_active', '==', True)
            )

            count = 0
            for doc in query.stream():
                doc.reference.update({'is_active': False})
                count += 1

            logger.info(f"Revoked {count} sessions for {user_email}")
            return count
        except Exception as e:
            logger.error(f"Error revoking sessions: {e}")
            return 0

    # =========================================================================
    # Credit Operations
    # =========================================================================

    def add_credits(
        self,
        email: str,
        amount: int,
        reason: str,
        job_id: Optional[str] = None,
        stripe_session_id: Optional[str] = None,
        admin_email: Optional[str] = None
    ) -> Tuple[bool, int, str]:
        """
        Add credits to a user account.

        Returns:
            (success, new_balance, message)
        """
        try:
            email = email.lower()
            user = self.get_or_create_user(email)

            # Create transaction record
            transaction = CreditTransaction(
                id=str(uuid.uuid4()),
                amount=amount,
                reason=reason,
                job_id=job_id,
                stripe_session_id=stripe_session_id,
                created_by=admin_email,
            )

            # Add to transaction history (keep last N)
            transactions = user.credit_transactions[-MAX_CREDIT_TRANSACTIONS + 1:]
            transactions.append(transaction)

            # Update user
            new_balance = user.credits + amount
            self.update_user(
                email,
                credits=new_balance,
                credit_transactions=[t.model_dump(mode='json') for t in transactions]
            )

            logger.info(f"Added {amount} credits to {email} ({reason}). New balance: {new_balance}")
            return True, new_balance, f"Added {amount} credits"

        except Exception as e:
            logger.error(f"Error adding credits to {email}: {e}")
            return False, 0, f"Failed to add credits: {e}"

    def deduct_credit(
        self,
        email: str,
        job_id: str,
        reason: str = "job_creation"
    ) -> Tuple[bool, int, str]:
        """
        Deduct one credit from a user account.

        Returns:
            (success, remaining_credits, message)
        """
        try:
            email = email.lower()
            user = self.get_user(email)

            if not user:
                return False, 0, "User not found"

            if user.credits <= 0:
                return False, 0, "Insufficient credits"

            # Create transaction record
            transaction = CreditTransaction(
                id=str(uuid.uuid4()),
                amount=-1,
                reason=reason,
                job_id=job_id,
            )

            # Add to transaction history
            transactions = user.credit_transactions[-MAX_CREDIT_TRANSACTIONS + 1:]
            transactions.append(transaction)

            # Update user
            new_balance = user.credits - 1
            self.update_user(
                email,
                credits=new_balance,
                credit_transactions=[t.model_dump(mode='json') for t in transactions],
                total_jobs_created=user.total_jobs_created + 1
            )

            logger.info(f"Deducted 1 credit from {email} for job {job_id}. Remaining: {new_balance}")
            return True, new_balance, f"Credit deducted. {new_balance} remaining"

        except Exception as e:
            logger.error(f"Error deducting credit from {email}: {e}")
            return False, 0, f"Failed to deduct credit: {e}"

    def refund_credit(
        self,
        email: str,
        job_id: str,
        reason: str = "job_failed"
    ) -> Tuple[bool, int, str]:
        """
        Refund one credit to a user account (e.g., after job failure).

        Returns:
            (success, new_balance, message)
        """
        return self.add_credits(email, 1, reason, job_id=job_id)

    def check_credits(self, email: str) -> int:
        """Check user's credit balance."""
        user = self.get_user(email)
        return user.credits if user else 0

    def has_credits(self, email: str) -> bool:
        """Check if user has at least one credit."""
        return self.check_credits(email) > 0

    # =========================================================================
    # Admin Operations
    # =========================================================================

    def set_user_role(self, email: str, role: UserRole, admin_email: str) -> bool:
        """Set a user's role (admin only)."""
        try:
            user = self.get_user(email)
            if not user:
                return False

            self.update_user(email, role=role.value)
            logger.info(f"Admin {admin_email} set role for {email} to {role.value}")
            return True
        except Exception as e:
            logger.error(f"Error setting user role: {e}")
            return False

    def disable_user(self, email: str, admin_email: str) -> bool:
        """Disable a user account (admin only)."""
        try:
            self.update_user(email, is_active=False)
            self.revoke_all_sessions(email)
            logger.info(f"Admin {admin_email} disabled user {email}")
            return True
        except Exception as e:
            logger.error(f"Error disabling user: {e}")
            return False

    def enable_user(self, email: str, admin_email: str) -> bool:
        """Enable a user account (admin only)."""
        try:
            self.update_user(email, is_active=True)
            logger.info(f"Admin {admin_email} enabled user {email}")
            return True
        except Exception as e:
            logger.error(f"Error enabling user: {e}")
            return False

    def increment_jobs_completed(self, email: str) -> bool:
        """Increment the completed jobs counter for a user."""
        try:
            user = self.get_user(email)
            if not user:
                return False

            self.update_user(email, total_jobs_completed=user.total_jobs_completed + 1)
            return True
        except Exception as e:
            logger.error(f"Error incrementing jobs completed for {email}: {e}")
            return False


# Global instance
_user_service = None


def get_user_service() -> UserService:
    """Get the global user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
