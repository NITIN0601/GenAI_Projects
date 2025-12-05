"""Evaluation providers."""

from src.evaluation.providers.heuristic import (
    HeuristicEvaluator,
    get_heuristic_evaluator,
)

# RAGAS is optional
try:
    from src.evaluation.providers.ragas import (
        RAGASEvaluator,
        get_ragas_evaluator,
        is_ragas_available,
    )
except ImportError:
    RAGASEvaluator = None
    get_ragas_evaluator = None
    is_ragas_available = lambda: False

__all__ = [
    'HeuristicEvaluator',
    'get_heuristic_evaluator',
    'RAGASEvaluator',
    'get_ragas_evaluator',
    'is_ragas_available',
]
