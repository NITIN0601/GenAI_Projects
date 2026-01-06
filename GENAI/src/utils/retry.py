"""
Retry Utilities for Pipeline Operations.

Provides decorators and utilities for robust error handling with:
- Exponential backoff retries
- Configurable retry counts and delays
- Exception type filtering
- Logging integration

Usage:
    from src.utils.retry import retry, RetryConfig

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def my_fragile_function():
        # Operation that might fail transiently
        pass

    # Or with custom config:
    config = RetryConfig(max_attempts=5, delay=0.5, exceptions=(IOError, TimeoutError))
    
    @retry(config=config)
    def another_function():
        pass
"""

import time
import functools
from dataclasses import dataclass, field
from typing import Callable, Tuple, Type, Optional, Any
import logging

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    delay: float = 1.0  # Initial delay in seconds
    backoff: float = 2.0  # Backoff multiplier
    max_delay: float = 60.0  # Maximum delay cap
    exceptions: Tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))
    log_level: int = logging.WARNING


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    config: Optional[RetryConfig] = None,
) -> Callable:
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts (including initial)
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exception types to catch and retry
        config: Optional RetryConfig to use instead of individual args
        
    Returns:
        Decorated function with retry behavior
        
    Example:
        @retry(max_attempts=3, delay=1.0, exceptions=(IOError, TimeoutError))
        def read_fragile_file(path):
            return open(path).read()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Use config if provided, else use individual args
            cfg = config or RetryConfig(
                max_attempts=max_attempts,
                delay=delay,
                backoff=backoff,
                max_delay=max_delay,
                exceptions=exceptions,
            )
            
            last_exception = None
            current_delay = cfg.delay
            
            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.exceptions as e:
                    last_exception = e
                    
                    if attempt == cfg.max_attempts:
                        logger.warning(
                            f"[Retry] {func.__name__} failed after {cfg.max_attempts} attempts: {e}"
                        )
                        raise
                    
                    logger.log(
                        cfg.log_level,
                        f"[Retry] {func.__name__} attempt {attempt}/{cfg.max_attempts} "
                        f"failed: {e}. Retrying in {current_delay:.1f}s..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay = min(current_delay * cfg.backoff, cfg.max_delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def retry_on_file_error(max_attempts: int = 3, delay: float = 0.5) -> Callable:
    """
    Specialized retry decorator for file operations.
    
    Catches common file-related errors:
    - IOError
    - OSError
    - PermissionError
    - FileNotFoundError (only if file might appear later)
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        
    Returns:
        Decorated function
    """
    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=1.5,
        exceptions=(IOError, OSError, PermissionError),
    )


def retry_on_network_error(max_attempts: int = 5, delay: float = 1.0) -> Callable:
    """
    Specialized retry decorator for network operations.
    
    Uses longer delays and more attempts suitable for network transients.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        
    Returns:
        Decorated function
    """
    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=2.0,
        max_delay=30.0,
        exceptions=(ConnectionError, TimeoutError, OSError),
    )


__all__ = [
    'RetryConfig',
    'retry',
    'retry_on_file_error',
    'retry_on_network_error',
]
