"""
Extraction strategy with automatic fallback.
"""

import logging
from src.utils import get_logger
from typing import List, Optional

from src.infrastructure.extraction.base import ExtractionBackend, ExtractionResult, ExtractionError
from src.infrastructure.extraction.quality import QualityAssessor

logger = get_logger(__name__)


class ExtractionStrategy:
    """
    Manage extraction with automatic fallback.
    
    Tries backends in priority order until quality threshold is met.
    """
    
    def __init__(
        self,
        backends: List[ExtractionBackend],
        quality_assessor: Optional[QualityAssessor] = None
    ):
        """
        Initialize extraction strategy.
        
        Args:
            backends: List of extraction backends
            quality_assessor: Quality assessor instance
        """
        # Sort backends by priority (lower number = higher priority)
        self.backends = sorted(backends, key=lambda b: b.get_priority())
        self.quality_assessor = quality_assessor or QualityAssessor()
        
        logger.info(f"Initialized strategy with {len(self.backends)} backends:")
        for backend in self.backends:
            logger.info(f"  - {backend.get_name()} (priority: {backend.get_priority()})")
    
    def extract_with_fallback(
        self,
        pdf_path: str,
        min_quality: float = 60.0,
        max_attempts: int = 3
    ) -> ExtractionResult:
        """
        Extract with automatic fallback.
        
        Args:
            pdf_path: Path to PDF file
            min_quality: Minimum acceptable quality score
            max_attempts: Maximum number of backends to try
            
        Returns:
            Best extraction result
            
        Raises:
            ExtractionError: If all backends fail
        """
        results = []
        attempts = 0
        
        for backend in self.backends:
            if attempts >= max_attempts:
                logger.warning(f"Reached max attempts ({max_attempts})")
                break
            
            # Skip unavailable backends
            if not backend.is_available():
                logger.warning(f"{backend.get_name()} not available, skipping")
                continue
            
            attempts += 1
            
            try:
                logger.info(f"Attempt {attempts}: Trying {backend.get_name()}...")
                
                # Extract with backend
                result = backend.extract(pdf_path)
                
                # Assess quality
                quality = self.quality_assessor.assess(result)
                result.quality_score = quality
                
                grade = self.quality_assessor.get_quality_grade(quality)
                logger.info(
                    f"{backend.get_name()} completed: "
                    f"quality={quality:.1f} ({grade}), "
                    f"tables={len(result.tables)}, "
                    f"time={result.extraction_time:.2f}s"
                )
                
                results.append(result)
                
                # If quality is good enough, use it
                if quality >= min_quality:
                    logger.info(
                        f"Using {backend.get_name()} "
                        f"(quality {quality:.1f} >= {min_quality})"
                    )
                    return result
                
                logger.warning(
                    f"✗ {backend.get_name()} quality too low: "
                    f"{quality:.1f} < {min_quality}, trying fallback..."
                )
                
            except Exception as e:
                logger.error(f"✗ {backend.get_name()} failed: {e}")
                continue
        
        # No backend met quality threshold
        if results:
            # Return best result
            best = max(results, key=lambda r: r.quality_score)
            logger.warning(
                f"⚠ No backend met quality threshold ({min_quality}). "
                f"Using best result from {best.backend.value} "
                f"(quality: {best.quality_score:.1f})"
            )
            return best
        
        # All backends failed
        raise ExtractionError(
            f"All {attempts} extraction attempts failed for {pdf_path}"
        )
    
    def extract_parallel(
        self,
        pdf_path: str,
        min_quality: float = 60.0
    ) -> ExtractionResult:
        """
        Extract with all backends in parallel and return best result.
        
        Args:
            pdf_path: Path to PDF file
            min_quality: Minimum acceptable quality score
            
        Returns:
            Best extraction result
        """
        import sys
        import platform
        from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, TimeoutError
        
        # Get available backends
        available_backends = [b for b in self.backends if b.is_available()]
        
        if not available_backends:
            raise ExtractionError("No backends available for extraction")
        
        logger.info(f"Starting parallel extraction with {len(available_backends)} backends")
        
        results = []
        
        # Windows compatibility: use ThreadPoolExecutor on Windows
        # ProcessPoolExecutor requires special handling on Windows (freeze_support)
        use_threads = platform.system() == 'Windows' or sys.platform == 'win32'
        
        ExecutorClass = ThreadPoolExecutor if use_threads else ProcessPoolExecutor
        executor_name = "ThreadPoolExecutor" if use_threads else "ProcessPoolExecutor"
        logger.debug(f"Using {executor_name} for parallel extraction")
        
        with ExecutorClass(max_workers=min(len(available_backends), 4)) as executor:
            # Submit all backends
            future_to_backend = {
                executor.submit(self._extract_with_backend, backend, pdf_path): backend
                for backend in available_backends
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_backend, timeout=300):  # 5 min timeout
                backend = future_to_backend[future]
                
                try:
                    result = future.result(timeout=60)  # 1 min per backend
                    
                    # Assess quality
                    quality = self.quality_assessor.assess(result)
                    result.quality_score = quality
                    
                    logger.info(
                        f"{backend.get_name()} completed: "
                        f"quality={quality:.1f}, tables={len(result.tables)}"
                    )
                    
                    results.append(result)
                    
                    # If quality is good enough, we can stop early
                    if quality >= min_quality:
                        logger.info(f"{backend.get_name()} met quality threshold, using result")
                        # Cancel remaining futures
                        for f in future_to_backend:
                            f.cancel()
                        return result
                        
                except TimeoutError:
                    logger.warning(f"{backend.get_name()} timed out")
                except Exception as e:
                    logger.error(f"{backend.get_name()} failed: {e}")
        
        # Return best result
        if results:
            best = max(results, key=lambda r: r.quality_score)
            logger.info(
                f"Using best result from {best.backend.value} "
                f"(quality: {best.quality_score:.1f})"
            )
            return best
        
        raise ExtractionError(f"All backends failed for {pdf_path}")
    
    def _extract_with_backend(self, backend: ExtractionBackend, pdf_path: str) -> ExtractionResult:
        """Helper method for parallel extraction."""
        try:
            return backend.extract(pdf_path)
        except Exception as e:
            logger.error(f"{backend.get_name()} extraction failed: {e}")
            raise
    
    def get_available_backends(self) -> List[str]:
        """Get list of available backend names."""
        return [
            backend.get_name()
            for backend in self.backends
            if backend.is_available()
        ]
    
    def get_backend_info(self) -> List[dict]:
        """Get information about all backends."""
        return [
            {
                'name': backend.get_name(),
                'type': backend.get_backend_type().value,
                'priority': backend.get_priority(),
                'available': backend.is_available(),
                'version': backend.get_version()
            }
            for backend in self.backends
        ]
