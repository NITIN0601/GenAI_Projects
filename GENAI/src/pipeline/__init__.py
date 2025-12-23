"""
Pipeline Module - Enterprise Pipeline Orchestration.

This module provides production-ready pipeline orchestration with:
- OOP-based step execution (Abstract Interface + Manager pattern)
- Three-tier caching integration
- Content-based deduplication
- Comprehensive error handling
- Observable metrics

Architecture follows the same pattern as infrastructure/*Manager classes.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from src.utils import get_logger

logger = get_logger(__name__)


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
    PROCESS_ADVANCED = "process_advanced"


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


# Import base classes (unified OOP pattern)
from src.pipeline.base import (
    StepStatus,
    StepResult,
    PipelineMetrics,
    PipelineContext,
    StepInterface,
    PipelineManager,
    get_pipeline_manager,
    get_pipeline,  # Backward compatibility alias
)

# Import step classes
from src.pipeline.steps.download import DownloadStep
from src.pipeline.steps.extract import ExtractStep
from src.pipeline.steps.embed import EmbedStep
from src.pipeline.steps.search import SearchStep, ViewDBStep
from src.pipeline.steps.query import QueryStep
from src.pipeline.steps.consolidate import ConsolidateStep

# Import step functions (backward compatible)
from src.pipeline.steps.download import run_download
from src.pipeline.steps.extract import run_extract
from src.pipeline.steps.embed import run_embed
from src.pipeline.steps.search import run_search, run_view_db
from src.pipeline.steps.query import run_query
from src.pipeline.steps.consolidate import run_consolidate

__all__ = [
    # Enums and Results (legacy)
    'PipelineStep',
    'PipelineResult',
    
    # Unified OOP Base Classes
    'StepStatus',
    'StepResult',
    'PipelineMetrics',
    'PipelineContext',
    'StepInterface',
    'PipelineManager',
    'get_pipeline_manager',
    'get_pipeline',  # Backward compatibility alias
    
    # Step Classes
    'DownloadStep',
    'ExtractStep',
    'EmbedStep',
    'SearchStep',
    'ViewDBStep',
    'QueryStep',
    'ConsolidateStep',
    
    # Step Functions (backward compatible)
    'run_download',
    'run_extract',
    'run_embed',
    'run_view_db',
    'run_search',
    'run_query',
    'run_consolidate',
]

