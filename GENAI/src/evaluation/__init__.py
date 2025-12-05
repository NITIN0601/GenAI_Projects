"""
RAG Evaluation Module - Enterprise Edition.

├── core/           # Base classes, manager, legacy
├── providers/      # Evaluation providers (heuristic, RAGAS)
└── metrics/        # Individual metric evaluators

Configuration via .env:
    EVALUATION_PROVIDER=heuristic|ragas|hybrid
    EVALUATION_AUTO_RUN=true|false
    EVALUATION_LOG_SCORES=true|false

Usage:
    from src.evaluation import get_evaluation_manager
    
    manager = get_evaluation_manager()  # Uses config from .env
    scores = manager.evaluate(query, answer, contexts)
    scores.print_table()
"""

# Core
from src.evaluation.core import (
    BaseEvaluator,
    EvaluationScores,
    MetricScore,
    EvaluationProvider,
    EvaluationManager,
    get_evaluation_manager,
    # Legacy
    RAGEvaluator,
    EvaluationResult,
    EvaluationConfig,
    get_rag_evaluator,
)

# Providers
from src.evaluation.providers import (
    HeuristicEvaluator,
    get_heuristic_evaluator,
    RAGASEvaluator,
    get_ragas_evaluator,
    is_ragas_available,
)

# Metrics
from src.evaluation.metrics import (
    RetrievalEvaluator,
    RetrievalMetrics,
    get_retrieval_evaluator,
    GenerationEvaluator,
    GenerationMetrics,
    get_generation_evaluator,
    FaithfulnessEvaluator,
    FaithfulnessMetrics,
    get_faithfulness_evaluator,
)

__version__ = "2.0.0"

__all__ = [
    # Core
    'BaseEvaluator',
    'EvaluationScores',
    'MetricScore',
    'EvaluationProvider',
    'EvaluationManager',
    'get_evaluation_manager',
    
    # Providers
    'HeuristicEvaluator',
    'get_heuristic_evaluator',
    'RAGASEvaluator',
    'get_ragas_evaluator',
    'is_ragas_available',
    
    # Metrics
    'RetrievalEvaluator',
    'RetrievalMetrics',
    'get_retrieval_evaluator',
    'GenerationEvaluator',
    'GenerationMetrics',
    'get_generation_evaluator',
    'FaithfulnessEvaluator',
    'FaithfulnessMetrics',
    'get_faithfulness_evaluator',
    
    # Legacy
    'RAGEvaluator',
    'EvaluationResult',
    'EvaluationConfig',
    'get_rag_evaluator',
]
