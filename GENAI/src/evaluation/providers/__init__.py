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
    # Alias for convenience
    RagasEvaluator = RAGASEvaluator
except ImportError:
    RAGASEvaluator = None
    RagasEvaluator = None
    get_ragas_evaluator = None
    is_ragas_available = lambda: False

__all__ = [
    'HeuristicEvaluator',
    'get_heuristic_evaluator',
    'RAGASEvaluator',
    'RagasEvaluator',  # Alias
    'get_ragas_evaluator',
    'is_ragas_available',
]
