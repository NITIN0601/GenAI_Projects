"""
Enterprise-grade centralized logging configuration for GENAI RAG system.

Features:
- Structured JSON logging for production environments
- Rotating file handlers to manage disk space
- Separate log streams: application, error, audit, performance
- Correlation IDs for request tracing
- Environment-aware configuration (dev vs production)
- Thread-safe singleton pattern

Log Naming Convention (10-Q/10-K Extraction Project):
- 10qk_app_YYYYMMDD.log      - Application logs (INFO+)
- 10qk_debug_YYYYMMDD.log    - Debug logs (DEBUG+)
- 10qk_error_YYYYMMDD.log    - Errors only (ERROR+)
- 10qk_audit_YYYYMMDD.log    - Audit trail (security events)
- 10qk_perf_YYYYMMDD.log     - Performance metrics
"""

import logging
import logging.handlers
import json
import sys
import os
import threading
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Context variable for correlation ID (thread-safe request tracking)
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (production/ELK stack ready)."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": correlation_id.get(''),
            "thread": record.thread,
            "process": record.process,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class EnterpriseFormatter(logging.Formatter):
    """Enterprise text formatter with consistent structure."""
    
    # ANSI color codes for console
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def __init__(self, use_colors: bool = False):
        self.use_colors = use_colors
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = record.levelname.ljust(8)
        
        # Include correlation ID if set
        corr_id = correlation_id.get('')
        corr_str = f"[{corr_id[:8]}] " if corr_id else ""
        
        # Format: TIMESTAMP | LEVEL | LOGGER | CORRELATION | MESSAGE
        message = f"{timestamp} | {level} | {record.name:30s} | {corr_str}{record.getMessage()}"
        
        # Add location for DEBUG/ERROR
        if record.levelno <= logging.DEBUG or record.levelno >= logging.ERROR:
            message += f" ({record.filename}:{record.lineno})"
        
        # Add colors for console output
        if self.use_colors and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            message = f"{color}{message}{reset}"
        
        # Add exception info
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


class GENAILogger:
    """Enterprise-grade centralized logging configuration."""
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    # Log directory and naming
    LOG_DIR = ".logs"
    APP_NAME = "10qk"  # 10-Q/10-K SEC filing extraction
    LOGGER_NAMESPACE = "10qk"  # Logger namespace
    
    # Log file naming convention
    LOG_FILES = {
        'app': '{app}_{date}.log',
        'debug': '{app}_debug_{date}.log', 
        'error': '{app}_error_{date}.log',
        'audit': '{app}_audit_{date}.log',
        'perf': '{app}_perf_{date}.log',
    }
    
    # Rotation settings
    MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file
    BACKUP_COUNT = 10  # Keep 10 rotated files
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._setup_logging()
                    GENAILogger._initialized = True
    
    def _get_log_path(self, log_type: str) -> Path:
        """Get log file path with naming convention."""
        log_dir = Path(self.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y%m%d')
        filename = self.LOG_FILES[log_type].format(
            app=self.APP_NAME,
            date=date_str
        )
        return log_dir / filename
    
    def _setup_logging(self):
        """Setup enterprise logging with multiple handlers."""
        # Determine environment
        env = os.environ.get('GENAI_ENV', 'development').lower()
        use_json = env in ('production', 'staging')
        
        # Create formatters
        if use_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = EnterpriseFormatter(use_colors=False)
        
        console_formatter = EnterpriseFormatter(use_colors=True)
        
        # === Application Handler (INFO+) ===
        app_handler = logging.handlers.RotatingFileHandler(
            self._get_log_path('app'),
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8'
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(file_formatter)
        
        # === Debug Handler (DEBUG+) ===
        debug_handler = logging.handlers.RotatingFileHandler(
            self._get_log_path('debug'),
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        
        # === Error Handler (ERROR+) ===
        error_handler = logging.handlers.RotatingFileHandler(
            self._get_log_path('error'),
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # === Console Handler (WARNING+ only to reduce verbosity) ===
        # Progress bars (tqdm) work independently, detailed logs go to files
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger for GENAI
        genai_logger = logging.getLogger('10qk')
        genai_logger.setLevel(logging.DEBUG)
        genai_logger.handlers.clear()  # Clear any existing handlers
        genai_logger.addHandler(app_handler)
        genai_logger.addHandler(debug_handler)
        genai_logger.addHandler(error_handler)
        genai_logger.addHandler(console_handler)
        genai_logger.propagate = False
        
        # Silence noisy third-party loggers
        for noisy_logger in ['urllib3', 'httpx', 'httpcore', 'openai', 'chromadb']:
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger for a specific module."""
        GENAILogger()  # Ensure initialized
        return logging.getLogger(f'10qk.{name}')
    
    @staticmethod
    def get_audit_logger() -> logging.Logger:
        """Get audit logger for security events."""
        GENAILogger()
        audit_logger = logging.getLogger('10qk.audit')
        
        # Add audit handler if not present
        if not any(isinstance(h, logging.handlers.RotatingFileHandler) 
                   and 'audit' in str(h.baseFilename) for h in audit_logger.handlers):
            handler = logging.handlers.RotatingFileHandler(
                GENAILogger()._get_log_path('audit'),
                maxBytes=GENAILogger.MAX_BYTES,
                backupCount=GENAILogger.BACKUP_COUNT,
                encoding='utf-8'
            )
            handler.setFormatter(EnterpriseFormatter())
            audit_logger.addHandler(handler)
        
        return audit_logger
    
    @staticmethod
    def get_perf_logger() -> logging.Logger:
        """Get performance logger for metrics."""
        GENAILogger()
        perf_logger = logging.getLogger('10qk.perf')
        
        # Add perf handler if not present
        if not any(isinstance(h, logging.handlers.RotatingFileHandler)
                   and 'perf' in str(h.baseFilename) for h in perf_logger.handlers):
            handler = logging.handlers.RotatingFileHandler(
                GENAILogger()._get_log_path('perf'),
                maxBytes=GENAILogger.MAX_BYTES,
                backupCount=GENAILogger.BACKUP_COUNT,
                encoding='utf-8'
            )
            handler.setFormatter(EnterpriseFormatter())
            perf_logger.addHandler(handler)
        
        return perf_logger


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module."""
    return GENAILogger.get_logger(name)


def get_audit_logger() -> logging.Logger:
    """Get audit logger for security/compliance events."""
    return GENAILogger.get_audit_logger()


def get_perf_logger() -> logging.Logger:
    """Get performance logger for metrics."""
    return GENAILogger.get_perf_logger()


def setup_logging(level: Optional[str] = None):
    """Setup logging with optional level override."""
    GENAILogger()
    if level:
        logging_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger('10qk').setLevel(logging_level)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracing. Returns the ID."""
    new_id = corr_id or str(uuid.uuid4())
    correlation_id.set(new_id)
    return new_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id.get('')


# =============================================================================
# LOG EXTRA DATA HELPER
# =============================================================================

class LogExtra:
    """Helper to add structured extra data to log messages."""
    
    @staticmethod
    def with_data(logger: logging.Logger, **kwargs):
        """Create a logger adapter with extra data."""
        class ExtraAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                kwargs['extra'] = {'extra_data': self.extra}
                return msg, kwargs
        
        return ExtraAdapter(logger, kwargs)
