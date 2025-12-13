"""JSON logger utility with environment-based log levels."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .constants import LOG_LEVEL_PROD, LOG_LEVEL_TEST, LOG_LEVEL_DEV


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def get_log_level() -> str:
    """Determine log level based on deployment environment.
    
    Returns:
        Log level string (INFO, DEBUG, etc.)
    """
    # Check for explicit LOG_LEVEL environment variable first
    log_level = os.environ.get('LOG_LEVEL')
    if log_level:
        return log_level.upper()
    
    # Fall back to environment-based defaults
    deploy_env = os.environ.get('DEPLOY_ENVIRONMENT', 'DEV').upper()
    
    if deploy_env == 'PROD':
        return LOG_LEVEL_PROD
    elif deploy_env == 'TEST':
        return LOG_LEVEL_TEST
    else:
        return LOG_LEVEL_DEV


def setup_logger(name: str) -> logging.Logger:
    """Set up a JSON logger with environment-based log level.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        log_level = get_log_level()
        logger.setLevel(getattr(logging, log_level))
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_level))
        
        # Set JSON formatter
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, 
                     context: Optional[Dict[str, Any]] = None) -> None:
    """Log a message with additional context fields.
    
    Args:
        logger: Logger instance
        level: Log level (info, debug, warning, error, critical)
        message: Log message
        context: Additional fields to include in JSON output
    """
    log_func = getattr(logger, level.lower())
    
    if context:
        # Create a log record with extra fields
        extra = {'extra_fields': context}
        log_func(message, extra=extra)
    else:
        log_func(message)