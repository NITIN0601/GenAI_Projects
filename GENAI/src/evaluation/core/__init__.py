"""Core evaluation components."""

from src.evaluation.core.base import (
    BaseEvaluator,
    EvaluationScores,
    MetricScore,
    EvaluationProvider,
)
from src.evaluation.core.manager import (
    EvaluationManager,
    get_evaluation_manager,
)

# Legacy exports for backward compatibility
from src.evaluation.core.legacy import (
    RAGEvaluator,
    EvaluationResult,
    EvaluationConfig,
    get_rag_evaluator,
)

__all__ = [
    'BaseEvaluator',
    'EvaluationScores',
    'MetricScore',
    'EvaluationProvider',
    'EvaluationManager',
    'get_evaluation_manager',
    # Legacy
    'RAGEvaluator',
    'EvaluationResult',
    'EvaluationConfig',
    'get_rag_evaluator',
]
