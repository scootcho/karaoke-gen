"""
Worker logging utilities.

Provides logging that sends to both standard output AND Firestore
for remote debugging via the CLI.
"""
import logging
from typing import Optional


class JobLogger:
    """
    Logger that writes to both standard logging and Firestore job logs.
    
    This allows worker logs to be viewed remotely via the CLI.
    
    Usage:
        job_logger = JobLogger(job_id, "audio", job_manager)
        job_logger.info("Processing audio...")
        job_logger.error("Failed to process", exc_info=True)
    """
    
    def __init__(self, job_id: str, worker_name: str, job_manager):
        """
        Initialize job logger.
        
        Args:
            job_id: Job ID to log to
            worker_name: Worker name (audio, lyrics, screens, video, render)
            job_manager: JobManager instance for Firestore access
        """
        self.job_id = job_id
        self.worker_name = worker_name
        self.job_manager = job_manager
        self._logger = logging.getLogger(f"worker.{worker_name}.{job_id}")
    
    def _log(self, level: str, message: str, *args, **kwargs):
        """Internal logging method."""
        # Format message with args if provided
        if args:
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                formatted_message = f"{message} {args}"
        else:
            formatted_message = message
        
        # Log to standard logging
        log_method = getattr(self._logger, level.lower())
        log_method(formatted_message)
        
        # Also append to Firestore job logs (async-safe)
        try:
            self.job_manager.append_worker_log(
                job_id=self.job_id,
                worker=self.worker_name,
                level=level.upper(),
                message=formatted_message
            )
        except Exception as e:
            # Don't let Firestore errors break worker processing
            self._logger.warning(f"Failed to append job log: {e}")
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self._log("DEBUG", message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self._log("INFO", message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self._log("WARNING", message, *args, **kwargs)
    
    def error(self, message: str, *args, exc_info: bool = False, **kwargs):
        """Log error message."""
        self._log("ERROR", message, *args, **kwargs)
        if exc_info:
            import traceback
            tb = traceback.format_exc()
            if tb and tb != "NoneType: None\n":
                self._log("ERROR", f"Traceback:\n{tb}")
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with traceback."""
        self.error(message, *args, exc_info=True, **kwargs)


def create_job_logger(job_id: str, worker_name: str) -> JobLogger:
    """
    Create a JobLogger for a worker.
    
    This is a convenience function that creates the JobManager internally.
    
    Args:
        job_id: Job ID
        worker_name: Worker name
        
    Returns:
        JobLogger instance
    """
    from backend.services.job_manager import JobManager
    job_manager = JobManager()
    return JobLogger(job_id, worker_name, job_manager)
