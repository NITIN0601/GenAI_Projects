"""
Pipeline Orchestrator - Enterprise pipeline coordination.

Provides:
- Full pipeline execution (download → extract → embed → query)
- Step-by-step execution with state management
- Metrics collection and observability
- Graceful error handling and recovery
"""

import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Pipeline execution metrics."""
    
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


class PipelineOrchestrator:
    """
    Enterprise pipeline orchestrator.
    
    Coordinates pipeline execution with:
    - Configurable step sequence
    - State management between steps
    - Metrics collection
    - Error recovery options
    
    Example:
        >>> pipeline = PipelineOrchestrator()
        >>> 
        >>> # Run full pipeline
        >>> result = pipeline.run_full_pipeline(source_dir="raw_data")
        >>> 
        >>> # Or step by step
        >>> pipeline.execute_step('extract', source_dir="raw_data")
        >>> pipeline.execute_step('embed')
    """
    
    def __init__(
        self,
        use_deduplication: bool = True,
        use_caching: bool = True,
        stop_on_error: bool = True,
    ):
        """
        Initialize pipeline orchestrator.
        
        Args:
            use_deduplication: Enable content-hash deduplication
            use_caching: Enable three-tier caching
            stop_on_error: Stop pipeline on first error
        """
        self.use_deduplication = use_deduplication
        self.use_caching = use_caching
        self.stop_on_error = stop_on_error
        
        # State management
        self._state: Dict[str, Any] = {}
        self._metrics = PipelineMetrics()
        self._step_results: List[Any] = []
        
        # Lazy-loaded components
        self._deduplicator = None
        self._extraction_cache = None
        self._embedding_cache = None
        
        logger.info(
            f"Pipeline orchestrator initialized: "
            f"dedup={use_deduplication}, cache={use_caching}"
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
    
    def run_full_pipeline(
        self,
        source_dir: Optional[str] = None,
        download: bool = False,
        year_range: str = "25",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Run complete pipeline: [Download] → Extract → Embed.
        
        Args:
            source_dir: Source directory for PDFs
            download: Include download step
            year_range: Year range for download (e.g., "20-25")
            force: Force reprocessing (ignore cache/dedup)
            
        Returns:
            Dict with results and metrics
        """
        from src.pipeline.steps.download import run_download
        from src.pipeline.steps.extract import run_extract
        from src.pipeline.steps.embed import run_embed
        
        self._metrics = PipelineMetrics(started_at=datetime.now())
        results = []
        
        # Step 1: Download (optional)
        if download:
            self._metrics.total_steps += 1
            result = self._execute_timed('download', lambda: run_download(year_range))
            results.append(result)
            if result.failed and self.stop_on_error:
                return self._finalize_results(results)
        
        # Step 2: Extract
        self._metrics.total_steps += 1
        result = self._execute_timed(
            'extract',
            lambda: run_extract(
                source_dir=source_dir,
                force=force,
                deduplicator=self.deduplicator if not force else None,
                extraction_cache=self.extraction_cache if not force else None,
            )
        )
        results.append(result)
        if result.failed and self.stop_on_error:
            return self._finalize_results(results)
        
        extracted_data = result.data if result.success else []
        
        # Step 3: Embed
        if extracted_data:
            self._metrics.total_steps += 1
            result = self._execute_timed(
                'embed',
                lambda: run_embed(
                    extracted_data=extracted_data,
                    embedding_cache=self.embedding_cache if self.use_caching else None,
                )
            )
            results.append(result)
        
        return self._finalize_results(results)
    
    def execute_step(
        self,
        step_name: str,
        **kwargs
    ) -> Any:
        """
        Execute a single pipeline step.
        
        Args:
            step_name: Step name (extract, embed, search, query, consolidate)
            **kwargs: Step-specific arguments
            
        Returns:
            PipelineResult
        """
        from src.pipeline import PipelineStep
        
        step_map = {
            'download': ('src.pipeline.steps.download', 'run_download'),
            'extract': ('src.pipeline.steps.extract', 'run_extract'),
            'embed': ('src.pipeline.steps.embed', 'run_embed'),
            'search': ('src.pipeline.steps.search', 'run_search'),
            'view_db': ('src.pipeline.steps.search', 'run_view_db'),
            'query': ('src.pipeline.steps.query', 'run_query'),
            'consolidate': ('src.pipeline.steps.consolidate', 'run_consolidate'),
        }
        
        if step_name not in step_map:
            raise ValueError(f"Unknown step: {step_name}. Valid: {list(step_map.keys())}")
        
        module_name, func_name = step_map[step_name]
        
        import importlib
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        
        return self._execute_timed(step_name, lambda: func(**kwargs))
    
    def _execute_timed(self, step_name: str, func: Callable) -> Any:
        """Execute step with timing."""
        start = time.time()
        
        try:
            result = func()
            duration = (time.time() - start) * 1000
            
            self._metrics.step_durations[step_name] = round(duration, 2)
            
            if hasattr(result, 'success'):
                if result.success:
                    self._metrics.completed_steps += 1
                else:
                    self._metrics.failed_steps += 1
                result.duration_ms = duration
            
            logger.info(f"Step '{step_name}' completed in {duration:.0f}ms")
            return result
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._metrics.step_durations[step_name] = round(duration, 2)
            self._metrics.failed_steps += 1
            logger.error(f"Step '{step_name}' failed: {e}")
            
            from src.pipeline import PipelineResult, PipelineStep
            return PipelineResult(
                step=PipelineStep[step_name.upper()],
                success=False,
                error=str(e),
                duration_ms=duration,
            )
    
    def _finalize_results(self, results: List[Any]) -> Dict[str, Any]:
        """Finalize pipeline execution."""
        self._metrics.completed_at = datetime.now()
        
        return {
            'success': all(r.success for r in results if hasattr(r, 'success')),
            'results': results,
            'metrics': self._metrics.to_dict(),
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current pipeline metrics."""
        return self._metrics.to_dict()
    
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


# Singleton instance
_pipeline: Optional[PipelineOrchestrator] = None


def get_pipeline(**kwargs) -> PipelineOrchestrator:
    """Get global pipeline orchestrator."""
    global _pipeline
    if _pipeline is None:
        _pipeline = PipelineOrchestrator(**kwargs)
    return _pipeline
