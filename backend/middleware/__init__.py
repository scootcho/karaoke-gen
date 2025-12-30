"""Middleware package for FastAPI application."""

from backend.middleware.audit_logging import AuditLoggingMiddleware

__all__ = ["AuditLoggingMiddleware"]
