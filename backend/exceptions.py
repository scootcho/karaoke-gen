"""
Custom exceptions for the karaoke generation backend.

These exceptions are used for structured error handling across the application,
particularly for rate limiting and validation errors.
"""


class RateLimitExceededError(Exception):
    """
    Raised when a rate limit is exceeded.

    Includes information about when the limit will reset for client retry logic.

    Attributes:
        message: Human-readable error message
        limit_type: Type of limit exceeded (e.g., "jobs_per_day", "youtube_uploads")
        remaining_seconds: Seconds until the limit resets (for Retry-After header)
        current_count: Current usage count
        limit_value: The limit that was exceeded
    """

    def __init__(
        self,
        message: str,
        limit_type: str = "unknown",
        remaining_seconds: int = 0,
        current_count: int = 0,
        limit_value: int = 0
    ):
        self.message = message
        self.limit_type = limit_type
        self.remaining_seconds = remaining_seconds
        self.current_count = current_count
        self.limit_value = limit_value
        super().__init__(message)


class EmailValidationError(Exception):
    """
    Raised when email validation fails.

    Attributes:
        message: Human-readable error message
        reason: Specific reason for failure (e.g., "disposable", "blocked", "invalid")
    """

    def __init__(self, message: str, reason: str = "invalid"):
        self.message = message
        self.reason = reason
        super().__init__(message)


class IPBlockedError(Exception):
    """
    Raised when a request comes from a blocked IP address.

    Attributes:
        message: Human-readable error message
        ip_address: The blocked IP address (may be partially masked)
    """

    def __init__(self, message: str, ip_address: str = ""):
        self.message = message
        self.ip_address = ip_address
        super().__init__(message)
