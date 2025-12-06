"""
Pipeline Module - Enterprise Pipeline Orchestration.

This module provides production-ready pipeline orchestration with:
- Modular step execution
- Three-tier caching integration
- Content-based deduplication
- Comprehensive error handling
- Observable metrics
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PipelineStep(Enum):
    """Pipeline step identifiers."""
    DOWNLOAD = "download"
    EXTRACT = "extract"
    EMBED = "embed"
    VIEW_DB = "view_db"
    SEARCH = "search"
    QUERY = "query"
    CONSOLIDATE = "consolidate"
    EXPORT = "export"


@dataclass
class PipelineResult:
    """Standardized result from any pipeline step."""
    
    step: PipelineStep
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    
    @property
    def failed(self) -> bool:
        return not self.success


# Import step implementations (backward compatible)
from src.pipeline.steps.download import run_download
from src.pipeline.steps.extract import run_extract
from src.pipeline.steps.embed import run_embed
from src.pipeline.steps.search import run_search, run_view_db
from src.pipeline.steps.query import run_query
from src.pipeline.steps.consolidate import run_consolidate

# Import orchestrator
from src.pipeline.orchestrator import PipelineOrchestrator, get_pipeline

__all__ = [
    # Enums and Results
    'PipelineStep',
    'PipelineResult',
    # Step functions (backward compatible)
    'run_download',
    'run_extract',
    'run_embed',
    'run_view_db',
    'run_search',
    'run_query',
    'run_consolidate',
    # Orchestrator
    'PipelineOrchestrator',
    'get_pipeline',
]
