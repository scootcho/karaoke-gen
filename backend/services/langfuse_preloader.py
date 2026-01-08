"""Langfuse callback handler preloader for container startup.

Initializes the Langfuse callback handler at container startup to avoid
slow initialization during request processing. The CallbackHandler()
constructor makes blocking network calls to the Langfuse API, which can
take 3+ minutes on Cloud Run cold starts.

See docs/archive/2026-01-08-performance-investigation.md for background.
"""

import logging
import os
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Singleton storage for preloaded handler
_preloaded_handler: Optional[Any] = None
_initialization_attempted: bool = False


def preload_langfuse_handler() -> Optional[Any]:
    """Preload Langfuse callback handler at startup.

    Only initializes if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
    environment variables are set.

    Returns:
        The preloaded CallbackHandler, or None if not configured
    """
    global _preloaded_handler, _initialization_attempted

    if _initialization_attempted:
        logger.debug("Langfuse initialization already attempted")
        return _preloaded_handler

    _initialization_attempted = True

    # Check if Langfuse is configured
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not (public_key and secret_key):
        logger.info("Langfuse not configured (missing keys), skipping preload")
        return None

    logger.info("Preloading Langfuse callback handler...")
    start_time = time.time()

    try:
        from langfuse.langchain import CallbackHandler

        # Initialize the handler - this is the slow part that makes network calls
        _preloaded_handler = CallbackHandler()

        elapsed = time.time() - start_time
        host = os.getenv("LANGFUSE_HOST", "cloud.langfuse.com")
        logger.info(f"Langfuse handler preloaded in {elapsed:.2f}s (host: {host})")

        return _preloaded_handler

    except ImportError:
        logger.warning("langfuse package not installed, skipping preload")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Failed to preload Langfuse handler after {elapsed:.2f}s: {e}")
        # Don't raise - Langfuse is optional
        return None


def get_preloaded_langfuse_handler() -> Optional[Any]:
    """Get the preloaded Langfuse callback handler if available.

    Returns:
        The preloaded CallbackHandler, or None if not preloaded/configured
    """
    return _preloaded_handler


def is_langfuse_preloaded() -> bool:
    """Check if Langfuse handler has been preloaded."""
    return _preloaded_handler is not None


def is_langfuse_configured() -> bool:
    """Check if Langfuse environment variables are configured."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


def clear_preloaded_handler() -> None:
    """Clear preloaded handler. Useful for testing."""
    global _preloaded_handler, _initialization_attempted
    _preloaded_handler = None
    _initialization_attempted = False
