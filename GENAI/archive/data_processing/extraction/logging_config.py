"""
Enterprise-grade logging configuration for extraction system.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ExtractionLogger:
    """Centralized logging configuration for extraction system."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            ExtractionLogger._initialized = True
    
    def _setup_logging(self):
        """Setup logging with file and console handlers."""
        # Create logs directory
        log_dir = Path(".logs/extraction")
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
        log_file = log_dir / f"extraction_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler (simple logs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Error file handler
        error_file = log_dir / f"extraction_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Configure root logger for extraction
        extraction_logger = logging.getLogger('extraction')
        extraction_logger.setLevel(logging.DEBUG)
        extraction_logger.addHandler(file_handler)
        extraction_logger.addHandler(console_handler)
        extraction_logger.addHandler(error_handler)
        
        # Prevent propagation to root
        extraction_logger.propagate = False
    
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
        ExtractionLogger()
        
        # Return logger under extraction namespace
        return logging.getLogger(f'extraction.{name}')


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return ExtractionLogger.get_logger(name)
