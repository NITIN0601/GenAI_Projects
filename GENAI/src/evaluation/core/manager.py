"""
Unified Evaluation Manager.

Provides a single interface for all evaluation providers,
with automatic fallback and hybrid mode support.

Configuration via .env:
    EVALUATION_PROVIDER=heuristic|ragas|hybrid
    EVALUATION_AUTO_RUN=true|false
    EVALUATION_LOG_SCORES=true|false
    EVALUATION_MIN_CONFIDENCE=0.5
    EVALUATION_BLOCK_HALLUCINATIONS=true|false
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
import time

from src.evaluation.core.base import (
    BaseEvaluator,
    EvaluationScores,
    MetricScore,
    EvaluationProvider,
)
from src.utils.logger import get_logger
from config.settings import settings

# Use centralized logger
logger = get_logger(__name__)


class EvaluationManager:
    """
    Unified evaluation manager with provider switching.
    
    Configured via .env:
        EVALUATION_PROVIDER=heuristic  # heuristic, ragas, or hybrid
        EVALUATION_AUTO_RUN=false      # Auto-evaluate every query
        EVALUATION_LOG_SCORES=true     # Log scores to file
    
    Example:
        manager = EvaluationManager()  # Uses settings from .env
        scores = manager.evaluate(query, answer, contexts)
        scores.print_table()
    """
    
    def __init__(
        self,
        provider: Union[str, EvaluationProvider] = None,
        ragas_llm: Optional[Any] = None,
        ragas_embeddings: Optional[Any] = None,
        fallback_to_heuristic: bool = True,
    ):
        """
        Initialize evaluation manager.
        
        Args:
            provider: Evaluation provider ('heuristic', 'ragas', 'hybrid')
                     If None, uses EVALUATION_PROVIDER from settings
            ragas_llm: LangChain LLM for RAGAS (optional)
            ragas_embeddings: LangChain embeddings for RAGAS (optional)
            fallback_to_heuristic: If True, fallback to heuristic on RAGAS failure
        """
        # Use settings if provider not specified
        if provider is None:
            provider = settings.EVALUATION_PROVIDER
            logger.info(f"Using evaluation provider from config: {provider}")
        
        if isinstance(provider, str):
            provider = EvaluationProvider(provider.lower())
        
        self.provider = provider
        self.fallback_to_heuristic = fallback_to_heuristic
        self._auto_run = settings.EVALUATION_AUTO_RUN
        self._log_scores = settings.EVALUATION_LOG_SCORES
        self._min_confidence = settings.EVALUATION_MIN_CONFIDENCE
        self._block_hallucinations = settings.EVALUATION_BLOCK_HALLUCINATIONS
        
        logger.info(f"Initializing EvaluationManager: provider={provider.value}, "
                   f"auto_run={self._auto_run}, log_scores={self._log_scores}")
        
        # Initialize evaluators based on provider
        self._heuristic_evaluator = None
        self._ragas_evaluator = None
        
        if provider in [EvaluationProvider.HEURISTIC, EvaluationProvider.HYBRID]:
            from src.evaluation.providers.heuristic import get_heuristic_evaluator
            self._heuristic_evaluator = get_heuristic_evaluator()
            logger.debug("Heuristic evaluator initialized")
        
        if provider in [EvaluationProvider.RAGAS, EvaluationProvider.HYBRID]:
            try:
                from src.evaluation.providers.ragas import get_ragas_evaluator, is_ragas_available
                if is_ragas_available():
                    self._ragas_evaluator = get_ragas_evaluator(
                        llm=ragas_llm,
                        embeddings=ragas_embeddings
                    )
                    logger.debug("RAGAS evaluator initialized")
                else:
                    logger.warning("RAGAS not available, using heuristic only")
                    if self._heuristic_evaluator is None:
                        from src.evaluation.providers.heuristic import get_heuristic_evaluator
                        self._heuristic_evaluator = get_heuristic_evaluator()
            except ImportError as e:
                logger.warning(f"RAGAS import failed: {e}")
                if fallback_to_heuristic and self._heuristic_evaluator is None:
                    from src.evaluation.providers.heuristic import get_heuristic_evaluator
                    self._heuristic_evaluator = get_heuristic_evaluator()
    
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        retrieval_scores: Optional[List[float]] = None,
        ground_truth: Optional[str] = None,
        **kwargs
    ) -> EvaluationScores:
        """
        Evaluate RAG response using configured provider.
        
        Args:
            query: User query
            answer: LLM-generated answer
            contexts: Retrieved context strings
            retrieval_scores: Optional similarity scores
            ground_truth: Optional ground truth for RAGAS
            
        Returns:
            EvaluationScores with all metrics
        """
        if self.provider == EvaluationProvider.HYBRID:
            return self._hybrid_evaluate(
                query, answer, contexts,
                retrieval_scores=retrieval_scores,
                ground_truth=ground_truth,
                **kwargs
            )
        elif self.provider == EvaluationProvider.RAGAS and self._ragas_evaluator:
            try:
                return self._ragas_evaluator.evaluate(
                    query, answer, contexts,
                    ground_truth=ground_truth,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"RAGAS failed: {e}, falling back to heuristic")
                if self.fallback_to_heuristic and self._heuristic_evaluator:
                    return self._heuristic_evaluator.evaluate(
                        query, answer, contexts,
                        retrieval_scores=retrieval_scores,
                        **kwargs
                    )
                raise
        else:
            # Heuristic
            return self._heuristic_evaluator.evaluate(
                query, answer, contexts,
                retrieval_scores=retrieval_scores,
                **kwargs
            )
    
    def _hybrid_evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        **kwargs
    ) -> EvaluationScores:
        """
        Combine heuristic and RAGAS evaluation.
        
        Uses heuristic metrics for speed, RAGAS for accuracy.
        """
        combined_scores = EvaluationScores(provider="hybrid")
        import time
        start_time = time.time()
        
        # Get heuristic scores (always available)
        if self._heuristic_evaluator:
            heuristic_result = self._heuristic_evaluator.evaluate(
                query, answer, contexts, **kwargs
            )
            for metric in heuristic_result.metrics:
                combined_scores.add_metric(metric)
        
        # Get RAGAS scores if available
        if self._ragas_evaluator:
            try:
                ragas_result = self._ragas_evaluator.evaluate(
                    query, answer, contexts, **kwargs
                )
                for metric in ragas_result.metrics:
                    # Avoid duplicates - RAGAS overrides heuristic for same category
                    existing_names = [m.name for m in combined_scores.metrics if m.source == 'ragas']
                    if metric.name not in existing_names:
                        combined_scores.add_metric(metric)
                
                # Use RAGAS hallucination detection (more accurate)
                combined_scores.hallucination_detected = ragas_result.hallucination_detected
                
            except Exception as e:
                logger.warning(f"RAGAS failed in hybrid mode: {e}")
                combined_scores.warnings.append(f"RAGAS unavailable: {str(e)[:50]}")
        
        # Compute overall scores
        combined_scores.compute_category_scores()
        combined_scores.is_reliable = (
            combined_scores.overall_score >= 0.5 and
            not combined_scores.hallucination_detected
        )
        
        combined_scores.evaluation_time_ms = (time.time() - start_time) * 1000
        return combined_scores
    
    def quick_check(
        self,
        answer: str,
        contexts: List[str],
    ) -> Dict[str, Any]:
        """
        Quick evaluation for real-time use.
        
        Uses heuristic only for speed.
        """
        if self._heuristic_evaluator:
            return self._heuristic_evaluator.quick_check(answer, contexts)
        elif self._ragas_evaluator:
            result = self._ragas_evaluator.evaluate("", answer, contexts)
            return {
                'is_reliable': result.is_reliable,
                'hallucination_detected': result.hallucination_detected,
                'overall_score': result.overall_score,
            }
        return {'is_reliable': False, 'hallucination_detected': True, 'overall_score': 0.0}
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Return availability status of each provider."""
        from src.evaluation.providers.ragas import is_ragas_available
        return {
            'heuristic': True,  # Always available
            'ragas': is_ragas_available(),
            'hybrid': is_ragas_available(),  # Requires RAGAS for full hybrid
        }
    
    def change_provider(self, provider: Union[str, EvaluationProvider]):
        """
        Switch to a different evaluation provider.
        
        Args:
            provider: New provider to use
        """
        if isinstance(provider, str):
            provider = EvaluationProvider(provider.lower())
        
        self.provider = provider
        
        # Initialize new evaluators if needed
        if provider in [EvaluationProvider.HEURISTIC, EvaluationProvider.HYBRID]:
            if self._heuristic_evaluator is None:
                from src.evaluation.providers.heuristic import get_heuristic_evaluator
                self._heuristic_evaluator = get_heuristic_evaluator()
        
        if provider in [EvaluationProvider.RAGAS, EvaluationProvider.HYBRID]:
            if self._ragas_evaluator is None:
                try:
                    from src.evaluation.providers.ragas import get_ragas_evaluator, is_ragas_available
                    if is_ragas_available():
                        self._ragas_evaluator = get_ragas_evaluator()
                except ImportError:
                    pass


# Global instance
_evaluation_manager: Optional[EvaluationManager] = None


def get_evaluation_manager(
    provider: Union[str, EvaluationProvider] = None,
    reset: bool = False,
) -> EvaluationManager:
    """
    Get or create global evaluation manager.
    
    Args:
        provider: Evaluation provider (default: from config or 'heuristic')
        reset: If True, create new manager even if one exists
        
    Returns:
        EvaluationManager instance
    """
    global _evaluation_manager
    
    if _evaluation_manager is None or reset:
        # Get default from config if not specified
        if provider is None:
            try:
                from config.settings import settings
                provider = getattr(settings, 'EVALUATION_PROVIDER', 'heuristic')
            except Exception:
                provider = 'heuristic'
        
        _evaluation_manager = EvaluationManager(provider=provider)
    
    return _evaluation_manager
