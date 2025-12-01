"""
Enterprise-grade centralized logging configuration for GENAI RAG system.

Provides:
- Structured logging with file and console handlers
- Separate error logs
- Module-specific loggers
- Singleton pattern for consistent configuration
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class GENAILogger:
    """Centralized logging configuration for GENAI system."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            GENAILogger._initialized = True
    
    def _setup_logging(self):
        """Setup logging with file and console handlers."""
        # Create logs directory
        log_dir = Path(".logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler (detailed logs)
        log_file = log_dir / f"genai_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler (simple logs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Error file handler
        error_file = log_dir / f"genai_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Configure root logger for GENAI
        genai_logger = logging.getLogger('genai')
        genai_logger.setLevel(logging.DEBUG)
        genai_logger.addHandler(file_handler)
        genai_logger.addHandler(console_handler)
        genai_logger.addHandler(error_handler)
        
        # Prevent propagation to root
        genai_logger.propagate = False
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger for a specific module.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            Configured logger instance
        """
        # Ensure logging is initialized
        GENAILogger()
        
        # Return logger under genai namespace
        return logging.getLogger(f'genai.{name}')


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> from src.utils import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return GENAILogger.get_logger(name)


def setup_logging(level: Optional[str] = None):
    """
    Setup logging with optional level override.
    
    Args:
        level: Optional logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = GENAILogger()
    
    if level:
        logging_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger('genai').setLevel(logging_level)
