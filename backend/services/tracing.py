"""
OpenTelemetry tracing configuration for Google Cloud Trace.

This module sets up distributed tracing that exports to Google Cloud Trace,
providing visibility into request flows, latency, and errors across the
entire backend.

Usage:
    # In main.py or app initialization
    from backend.services.tracing import setup_tracing, instrument_app
    
    setup_tracing(service_name="karaoke-backend")
    app = FastAPI()
    instrument_app(app)
    
    # For custom spans in your code
    from backend.services.tracing import tracer, create_span
    
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("job_id", job_id)
        # ... do work ...
"""
import os
import logging
from typing import Optional, Any, Dict
from contextlib import contextmanager
from functools import wraps

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Google Cloud Trace exporter
try:
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.resourcedetector.gcp_resource_detector import GoogleCloudResourceDetector
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    CloudTraceSpanExporter = None
    GoogleCloudResourceDetector = None

# FastAPI instrumentation
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FASTAPI_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    FASTAPI_INSTRUMENTATION_AVAILABLE = False
    FastAPIInstrumentor = None

# HTTPX instrumentation (for outgoing HTTP calls)
try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation
    HTTPX_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    HTTPX_INSTRUMENTATION_AVAILABLE = False
    HTTPXClientInstrumentation = None

# Logging instrumentation
try:
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    LOGGING_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    LOGGING_INSTRUMENTATION_AVAILABLE = False
    LoggingInstrumentor = None


logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_initialized = False


def setup_tracing(
    service_name: str = "karaoke-backend",
    service_version: str = "0.71.7",
    enable_in_dev: bool = False,
) -> bool:
    """
    Initialize OpenTelemetry tracing with Google Cloud Trace exporter.
    
    Args:
        service_name: Name of the service (appears in Cloud Trace)
        service_version: Version of the service
        enable_in_dev: Whether to enable tracing in development (default False)
        
    Returns:
        True if tracing was initialized, False if skipped
    """
    global _tracer, _initialized
    
    if _initialized:
        logger.debug("Tracing already initialized")
        return True
    
    # Check if we should enable tracing
    # In Cloud Run, GOOGLE_CLOUD_PROJECT is always set
    is_cloud_run = os.environ.get("K_SERVICE") is not None
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    
    if not is_cloud_run and not enable_in_dev:
        logger.info("Tracing disabled in development (set enable_in_dev=True to enable)")
        _tracer = trace.get_tracer(service_name)
        return False
    
    if not GCP_AVAILABLE:
        logger.warning("Google Cloud Trace exporter not available, tracing disabled")
        _tracer = trace.get_tracer(service_name)
        return False
    
    logger.info(f"Initializing OpenTelemetry tracing for {service_name} v{service_version}")
    
    try:
        # Create resource with service info and GCP resource detection
        resource_attributes = {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
        }
        
        # Detect GCP resources (project, region, instance, etc.)
        if GoogleCloudResourceDetector and is_cloud_run:
            try:
                gcp_resource = GoogleCloudResourceDetector().detect()
                resource = Resource.create(resource_attributes).merge(gcp_resource)
                logger.info("Detected GCP resources for tracing")
            except Exception as e:
                logger.warning(f"Could not detect GCP resources: {e}")
                resource = Resource.create(resource_attributes)
        else:
            resource = Resource.create(resource_attributes)
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add Cloud Trace exporter
        if CloudTraceSpanExporter and gcp_project:
            try:
                exporter = CloudTraceSpanExporter(project_id=gcp_project)
                # Use BatchSpanProcessor for production (better performance)
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)
                logger.info(f"Cloud Trace exporter configured for project: {gcp_project}")
            except Exception as e:
                logger.warning(f"Could not configure Cloud Trace exporter: {e}")
        
        # Set the global tracer provider
        trace.set_tracer_provider(provider)
        
        # Get tracer instance
        _tracer = trace.get_tracer(service_name, service_version)
        
        # Instrument logging to include trace context
        if LOGGING_INSTRUMENTATION_AVAILABLE and LoggingInstrumentor:
            try:
                LoggingInstrumentor().instrument(set_logging_format=True)
                logger.info("Logging instrumentation enabled")
            except Exception as e:
                logger.warning(f"Could not instrument logging: {e}")
        
        # Instrument HTTPX for outgoing requests
        if HTTPX_INSTRUMENTATION_AVAILABLE and HTTPXClientInstrumentation:
            try:
                HTTPXClientInstrumentation().instrument()
                logger.info("HTTPX instrumentation enabled")
            except Exception as e:
                logger.warning(f"Could not instrument HTTPX: {e}")
        
        _initialized = True
        logger.info("OpenTelemetry tracing initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        _tracer = trace.get_tracer(service_name)
        return False


def instrument_app(app) -> None:
    """
    Instrument a FastAPI application with automatic tracing.
    
    This adds spans for all incoming requests, including:
    - Request method and path
    - Response status code
    - Request duration
    - Error information
    
    Args:
        app: FastAPI application instance
    """
    if not FASTAPI_INSTRUMENTATION_AVAILABLE or not FastAPIInstrumentor:
        logger.warning("FastAPI instrumentation not available")
        return
    
    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,healthz,ready,readiness,ping",
        )
        logger.info("FastAPI instrumentation enabled")
    except Exception as e:
        logger.warning(f"Could not instrument FastAPI: {e}")


def get_tracer() -> trace.Tracer:
    """
    Get the global tracer instance.
    
    Returns:
        Tracer instance (creates a no-op tracer if not initialized)
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("karaoke-backend")
    return _tracer


# Convenience alias
tracer = property(lambda self: get_tracer())


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """
    Create a traced span as a context manager.
    
    Usage:
        with create_span("process-lyrics", {"job_id": job_id}) as span:
            # ... do work ...
            span.set_attribute("words_processed", 500)
    
    Args:
        name: Span name (appears in Cloud Trace)
        attributes: Initial span attributes
        kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)
        
    Yields:
        The active span
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def traced(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Decorator to trace a function.
    
    Usage:
        @traced("process-correction")
        def process_correction(job_id: str):
            ...
            
        @traced(attributes={"operation": "add-lyrics"})
        async def add_lyrics(job_id: str, source: str):
            ...
    
    Args:
        name: Span name (defaults to function name)
        attributes: Static attributes to add to span
    """
    def decorator(func):
        span_name = name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                # Add function arguments as attributes
                span.set_attribute("function", func.__name__)
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                span.set_attribute("function", func.__name__)
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def add_span_attribute(key: str, value: Any) -> None:
    """
    Add an attribute to the current span.
    
    Args:
        key: Attribute name
        value: Attribute value (must be string, int, float, bool, or list thereof)
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """
    Add an event to the current span.
    
    Events are timestamped annotations that appear in the trace timeline.
    
    Args:
        name: Event name
        attributes: Event attributes
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def set_span_error(error: Exception) -> None:
    """
    Mark the current span as errored.
    
    Args:
        error: The exception that occurred
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID for correlation.
    
    This can be used to link logs to traces.
    
    Returns:
        Trace ID as hex string, or None if no active trace
    """
    span = trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """
    Get the current span ID.
    
    Returns:
        Span ID as hex string, or None if no active span
    """
    span = trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.span_id, '016x')
    return None
