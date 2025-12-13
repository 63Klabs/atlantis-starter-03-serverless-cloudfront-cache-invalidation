"""Retry decorator with exponential backoff and jitter."""

import functools
import random
import time
from typing import Callable, Optional, Tuple, Type

from .constants import (
    RETRY_INITIAL_DELAY_MS,
    RETRY_MAX_DELAY_MS,
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_JITTER_PERCENT
)
from .logger import setup_logger

logger = setup_logger(__name__)


def calculate_delay_with_jitter(attempt: int, 
                                initial_delay_ms: int = RETRY_INITIAL_DELAY_MS,
                                max_delay_ms: int = RETRY_MAX_DELAY_MS,
                                multiplier: float = RETRY_BACKOFF_MULTIPLIER,
                                jitter_percent: float = RETRY_JITTER_PERCENT) -> float:
    """Calculate exponential backoff delay with jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        initial_delay_ms: Initial delay in milliseconds
        max_delay_ms: Maximum delay in milliseconds
        multiplier: Backoff multiplier
        jitter_percent: Jitter as a percentage (0.25 = ±25%)
        
    Returns:
        Delay in seconds with jitter applied
    """
    # Calculate exponential delay
    delay_ms = min(initial_delay_ms * (multiplier ** attempt), max_delay_ms)
    
    # Apply jitter (±jitter_percent)
    jitter_range = delay_ms * jitter_percent
    jitter = random.uniform(-jitter_range, jitter_range)
    final_delay_ms = delay_ms + jitter
    
    # Ensure non-negative delay
    final_delay_ms = max(0, final_delay_ms)
    
    # Convert to seconds
    return final_delay_ms / 1000.0


def retry_with_backoff(max_attempts: int = 3,
                       exceptions: Tuple[Type[Exception], ...] = (Exception,),
                       initial_delay_ms: int = RETRY_INITIAL_DELAY_MS,
                       max_delay_ms: int = RETRY_MAX_DELAY_MS,
                       multiplier: float = RETRY_BACKOFF_MULTIPLIER,
                       jitter_percent: float = RETRY_JITTER_PERCENT,
                       on_retry: Optional[Callable] = None) -> Callable:
    """Decorator for retrying a function with exponential backoff and jitter.
    
    Args:
        max_attempts: Maximum number of attempts (including initial attempt)
        exceptions: Tuple of exception types to catch and retry
        initial_delay_ms: Initial delay in milliseconds
        max_delay_ms: Maximum delay in milliseconds
        multiplier: Backoff multiplier
        jitter_percent: Jitter as a percentage (0.25 = ±25%)
        on_retry: Optional callback function called on each retry
        
    Returns:
        Decorated function
        
    Example:
        @retry_with_backoff(max_attempts=3, exceptions=(ClientError,))
        def call_aws_api():
            # API call that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            func_name = getattr(func, '__name__', repr(func))
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func_name} failed after {max_attempts} attempts",
                            extra={'extra_fields': {
                                'function': func_name,
                                'attempts': max_attempts,
                                'error': str(e)
                            }}
                        )
                        raise
                    
                    # Calculate delay
                    delay = calculate_delay_with_jitter(
                        attempt,
                        initial_delay_ms,
                        max_delay_ms,
                        multiplier,
                        jitter_percent
                    )
                    
                    logger.warning(
                        f"Function {func_name} failed on attempt {attempt + 1}/{max_attempts}, "
                        f"retrying in {delay:.3f}s",
                        extra={'extra_fields': {
                            'function': func_name,
                            'attempt': attempt + 1,
                            'max_attempts': max_attempts,
                            'delay_seconds': delay,
                            'error': str(e)
                        }}
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e)
                    
                    # Wait before retrying
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator