"""
Pipeline Base Classes - Unified with system architecture.

Follows the same pattern as:
- VectorDBManager (Interface + Manager + get_*())
- EmbeddingManager
- SearchOrchestrator

Pattern:
- StepInterface (abstract)
- Concrete Steps (implement interface)
- PipelineManager (orchestrates steps)
- get_pipeline_manager() (singleton)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Standardized result from a pipeline step (like SearchResult)."""
    
    step_name: str
    status: StepStatus
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.status == StepStatus.SUCCESS
    
    @property
    def failed(self) -> bool:
        return self.status == StepStatus.FAILED


@dataclass
class PipelineMetrics:
    """Pipeline execution metrics for observability."""
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    step_durations: Dict[str, float] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        total = self.completed_steps + self.failed_steps
        return self.completed_steps / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': round(self.duration_seconds, 2),
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'failed_steps': self.failed_steps,
            'skipped_steps': self.skipped_steps,
            'success_rate': f"{self.success_rate:.1%}",
            'step_durations': self.step_durations,
        }
    
    def reset(self):
        """Reset metrics for a new pipeline run."""
        self.started_at = None
        self.completed_at = None
        self.total_steps = 0
        self.completed_steps = 0
        self.failed_steps = 0
        self.skipped_steps = 0
        self.step_durations = {}


@dataclass
class PipelineContext:
    """
    Shared context for pipeline execution.
    
    Follows same pattern as SearchConfig in retrieval.
    """
    
    # Configuration
    source_dir: Optional[str] = None
    force: bool = False
    
    # Data flow between steps
    extracted_data: List[Dict[str, Any]] = field(default_factory=list)
    chunks: List[Any] = field(default_factory=list)
    
    # Query-specific (for search/query steps)
    query: Optional[str] = None
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None
    
    # Results from each step
    results: Dict[str, StepResult] = field(default_factory=dict)
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    
    def add_result(self, step_name: str, result: StepResult):
        self.results[step_name] = result
    
    def get_result(self, step_name: str) -> Optional[StepResult]:
        return self.results.get(step_name)


class StepInterface(ABC):
    """
    Abstract interface for pipeline steps.
    
    Follows same pattern as VectorDBInterface.
    """
    
    name: str = "step"
    
    @abstractmethod
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute the step."""
        pass
    
    @abstractmethod
    def validate(self, context: PipelineContext) -> bool:
        """Validate context before execution."""
        pass
    
    @abstractmethod
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        pass


class PipelineManager:
    """
    Pipeline manager - orchestrates step execution.
    
    Follows same pattern as:
    - VectorDBManager (wraps stores)
    - SearchOrchestrator (coordinates strategies)
    
    Features (merged from PipelineOrchestrator):
    - Step-based execution with StepInterface
    - Metrics collection and observability
    - Three-tier caching integration
    - Content-based deduplication
    - Configurable error handling
    
    Usage:
        manager = get_pipeline_manager()
        ctx = PipelineContext(source_dir="/data/raw")
        
        result = manager.run_step("extract", ctx)
        result = manager.run_step("embed", ctx)
        
        # Or run full pipeline
        result = manager.run_pipeline(["extract", "embed"], ctx)
        
        # Or use convenience method
        result = manager.run_full_pipeline(source_dir="/data/raw")
    """
    
    def __init__(
        self,
        use_deduplication: bool = True,
        use_caching: bool = True,
        stop_on_error: bool = True,
    ):
        """
        Initialize pipeline manager.
        
        Args:
            use_deduplication: Enable content-hash deduplication
            use_caching: Enable three-tier caching
            stop_on_error: Stop pipeline on first error
        """
        self.use_deduplication = use_deduplication
        self.use_caching = use_caching
        self.stop_on_error = stop_on_error
        
        # Step registry
        self._steps: Dict[str, StepInterface] = {}
        self._register_default_steps()
        
        # Metrics tracking
        self._metrics = PipelineMetrics()
        
        # Lazy-loaded cache components
        self._deduplicator = None
        self._extraction_cache = None
        self._embedding_cache = None
        
        logger.info(
            f"PipelineManager initialized: "
            f"dedup={use_deduplication}, cache={use_caching}, stop_on_error={stop_on_error}"
        )
    
    @property
    def deduplicator(self):
        """Lazy load deduplicator."""
        if self._deduplicator is None and self.use_deduplication:
            from src.core.deduplication import get_deduplicator
            self._deduplicator = get_deduplicator()
        return self._deduplicator
    
    @property
    def extraction_cache(self):
        """Lazy load extraction cache."""
        if self._extraction_cache is None and self.use_caching:
            from src.infrastructure.cache import ExtractionCache
            self._extraction_cache = ExtractionCache()
        return self._extraction_cache
    
    @property
    def embedding_cache(self):
        """Lazy load embedding cache."""
        if self._embedding_cache is None and self.use_caching:
            from src.infrastructure.cache import EmbeddingCache
            self._embedding_cache = EmbeddingCache()
        return self._embedding_cache
    
    @property
    def metrics(self) -> PipelineMetrics:
        """Get current pipeline metrics."""
        return self._metrics
    
    def _register_default_steps(self):
        """Register default pipeline steps."""
        from src.pipeline.steps.download import DownloadStep
        from src.pipeline.steps.extract import ExtractStep
        from src.pipeline.steps.embed import EmbedStep
        from src.pipeline.steps.search import SearchStep, ViewDBStep
        from src.pipeline.steps.query import QueryStep
        from src.pipeline.steps.consolidate import ConsolidateStep
        
        self._steps = {
            "download": DownloadStep(),
            "extract": ExtractStep(),
            "embed": EmbedStep(),
            "search": SearchStep(),
            "view_db": ViewDBStep(),
            "query": QueryStep(),
            "consolidate": ConsolidateStep(),
        }
    
    def register_step(self, name: str, step: StepInterface):
        """Register a custom step (extensibility)."""
        self._steps[name] = step
        logger.info(f"Registered step: {name}")
    
    def get_step(self, name: str) -> Optional[StepInterface]:
        """Get a step by name."""
        return self._steps.get(name)
    
    def run_step(self, step_name: str, context: PipelineContext) -> StepResult:
        """
        Execute a single step with metrics tracking.
        
        Args:
            step_name: Name of step to run
            context: Pipeline context
            
        Returns:
            StepResult
        """
        step = self._steps.get(step_name)
        if not step:
            self._metrics.failed_steps += 1
            return StepResult(
                step_name=step_name,
                status=StepStatus.FAILED,
                error=f"Unknown step: {step_name}"
            )
        
        logger.info(f"Running step: {step_name}")
        self._metrics.total_steps += 1
        
        # Validate
        if not step.validate(context):
            self._metrics.failed_steps += 1
            result = StepResult(
                step_name=step_name,
                status=StepStatus.FAILED,
                error=f"Validation failed for {step_name}"
            )
            context.add_result(step_name, result)
            return result
        
        # Execute with timing
        start = datetime.now()
        try:
            result = step.execute(context)
            duration_ms = (datetime.now() - start).total_seconds() * 1000
            result.duration_ms = duration_ms
            
            # Update metrics
            self._metrics.step_durations[step_name] = round(duration_ms, 2)
            if result.success:
                self._metrics.completed_steps += 1
            else:
                self._metrics.failed_steps += 1
                
        except Exception as e:
            duration_ms = (datetime.now() - start).total_seconds() * 1000
            logger.error(f"Step {step_name} failed: {e}")
            self._metrics.step_durations[step_name] = round(duration_ms, 2)
            self._metrics.failed_steps += 1
            result = StepResult(
                step_name=step_name,
                status=StepStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms
            )
        
        context.add_result(step_name, result)
        logger.info(f"Step {step_name} completed: {result.status.value} ({result.duration_ms:.0f}ms)")
        
        return result
    
    def run_pipeline(
        self,
        steps: List[str],
        context: PipelineContext
    ) -> StepResult:
        """
        Execute multiple steps in sequence.
        
        Args:
            steps: List of step names to run
            context: Pipeline context
            
        Returns:
            Final StepResult (success if all pass)
        """
        logger.info(f"Running pipeline with {len(steps)} steps: {steps}")
        
        # Reset and start metrics
        self._metrics.reset()
        self._metrics.started_at = datetime.now()
        
        for step_name in steps:
            result = self.run_step(step_name, context)
            
            if result.failed and self.stop_on_error:
                logger.error(f"Pipeline stopped at {step_name}")
                self._metrics.completed_at = datetime.now()
                return result
        
        self._metrics.completed_at = datetime.now()
        total_ms = (datetime.now() - context.start_time).total_seconds() * 1000
        
        return StepResult(
            step_name="pipeline",
            status=StepStatus.SUCCESS,
            message=f"Completed {len(steps)} steps",
            metadata={
                "total_duration_ms": total_ms,
                "steps": steps,
                "metrics": self._metrics.to_dict()
            }
        )
    
    def run_full_pipeline(
        self,
        source_dir: Optional[str] = None,
        download: bool = False,
        year_range: str = "25",
        force: bool = False,
    ) -> StepResult:
        """
        Run complete pipeline: [Download] → Extract → Embed.
        
        Convenience method for common ingestion workflow.
        
        Args:
            source_dir: Source directory for PDFs
            download: Include download step
            year_range: Year range for download (e.g., "20-25")
            force: Force reprocessing (ignore cache/dedup)
            
        Returns:
            StepResult with results and metrics
        """
        # Build context
        context = PipelineContext(
            source_dir=source_dir,
            force=force,
        )
        
        # Build step list
        steps = []
        if download:
            steps.append("download")
        steps.extend(["extract", "embed"])
        
        # Run pipeline
        return self.run_pipeline(steps, context)
    
    def get_available_steps(self) -> List[str]:
        """Get list of available step names."""
        return list(self._steps.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics including metrics."""
        return {
            "available_steps": self.get_available_steps(),
            "step_info": {
                name: step.get_step_info() 
                for name, step in self._steps.items()
            },
            "metrics": self._metrics.to_dict(),
            "config": {
                "use_deduplication": self.use_deduplication,
                "use_caching": self.use_caching,
                "stop_on_error": self.stop_on_error,
            }
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {}
        
        if self.extraction_cache:
            stats['extraction'] = self.extraction_cache.get_stats().to_dict()
        if self.embedding_cache:
            stats['embedding'] = self.embedding_cache.get_stats().to_dict()
        if self.deduplicator:
            stats['deduplication'] = self.deduplicator.get_stats()
        
        return stats
    
    def reset_metrics(self):
        """Reset pipeline metrics."""
        self._metrics.reset()
        logger.info("Pipeline metrics reset")


# Global instance (singleton pattern like VectorDBManager)
_pipeline_manager: Optional[PipelineManager] = None
_pipeline_manager_lock = __import__('threading').Lock()


def get_pipeline_manager(**kwargs) -> PipelineManager:
    """
    Get or create global pipeline manager.
    
    Thread-safe singleton pattern following same design as:
    - get_vectordb_manager()
    - get_embedding_manager()
    - get_search_orchestrator()
    
    Args:
        **kwargs: Configuration options passed to PipelineManager
            - use_deduplication: Enable content-hash deduplication (default: True)
            - use_caching: Enable three-tier caching (default: True)
            - stop_on_error: Stop pipeline on first error (default: True)
    
    Returns:
        PipelineManager singleton instance
    """
    global _pipeline_manager
    
    if _pipeline_manager is None:
        with _pipeline_manager_lock:
            # Double-check locking pattern
            if _pipeline_manager is None:
                _pipeline_manager = PipelineManager(**kwargs)
    
    return _pipeline_manager


# Backward compatibility alias (from orchestrator.py)
get_pipeline = get_pipeline_manager
