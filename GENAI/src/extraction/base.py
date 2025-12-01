"""
Base interfaces for unified extraction system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class BackendType(Enum):
    """Supported extraction backends."""
    DOCLING = "docling"
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"
    CAMELOT = "camelot"


@dataclass
class ExtractionResult:
    """Result from extraction backend."""
    
    # Core data
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Backend info
    backend: BackendType = BackendType.DOCLING
    backend_version: str = ""
    
    # Quality metrics
    quality_score: float = 0.0
    table_count: int = 0
    cell_completeness: float = 0.0
    structure_score: float = 0.0
    
    # Performance metrics
    extraction_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Error handling
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    # Additional info
    pdf_path: str = ""
    pdf_hash: str = ""
    page_count: int = 0
    
    def is_successful(self) -> bool:
        """Check if extraction was successful."""
        return self.error is None and len(self.tables) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get extraction summary."""
        return {
            "backend": self.backend.value,
            "tables_found": len(self.tables),
            "quality_score": self.quality_score,
            "extraction_time": self.extraction_time,
            "successful": self.is_successful()
        }


class ExtractionBackend(ABC):
    """Base interface for all extraction backends."""
    
    @abstractmethod
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Backend-specific options
            
        Returns:
            ExtractionResult with tables and metadata
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get backend name."""
        pass
    
    @abstractmethod
    def get_backend_type(self) -> BackendType:
        """Get backend type enum."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available (dependencies installed)."""
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get backend priority (lower number = higher priority).
        
        Default priorities:
        - Docling: 1 (highest)
        - PyMuPDF: 2
        - pdfplumber: 3
        - Camelot: 4
        """
        pass
    
    def get_version(self) -> str:
        """Get backend version."""
        return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check if backend supports a specific feature."""
        return False


class ExtractionError(Exception):
    """Base exception for extraction errors."""
    pass


class BackendNotAvailableError(ExtractionError):
    """Raised when backend is not available."""
    pass


class QualityThresholdError(ExtractionError):
    """Raised when quality threshold is not met."""
    pass
