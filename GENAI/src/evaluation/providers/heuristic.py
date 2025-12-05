"""
Heuristic Evaluation Provider.

Fast evaluation without LLM calls - uses embedding similarity,
keyword matching, and rule-based checks.
"""

from typing import List, Dict, Any, Optional
import logging
import time

from src.evaluation.core.base import BaseEvaluator, EvaluationScores, MetricScore
from src.evaluation.metrics.retrieval import RetrievalEvaluator, get_retrieval_evaluator
from src.evaluation.metrics.generation import GenerationEvaluator, get_generation_evaluator
from src.evaluation.metrics.faithfulness import FaithfulnessEvaluator, get_faithfulness_evaluator

logger = logging.getLogger(__name__)


class HeuristicEvaluator(BaseEvaluator):
    """
    Heuristic-based evaluation provider.
    
    Uses embedding similarity, keyword overlap, and rule-based checks.
    Fast and doesn't require LLM calls.
    
    Best for:
    - Development and debugging
    - Real-time evaluation
    - Cost-sensitive applications
    """
    
    def __init__(
        self,
        retrieval_evaluator: Optional[RetrievalEvaluator] = None,
        generation_evaluator: Optional[GenerationEvaluator] = None,
        faithfulness_evaluator: Optional[FaithfulnessEvaluator] = None,
    ):
        """
        Initialize heuristic evaluator.
        
        Args:
            retrieval_evaluator: Custom retrieval evaluator
            generation_evaluator: Custom generation evaluator
            faithfulness_evaluator: Custom faithfulness evaluator
        """
        self.retrieval_eval = retrieval_evaluator or get_retrieval_evaluator()
        self.generation_eval = generation_evaluator or get_generation_evaluator()
        self.faithfulness_eval = faithfulness_evaluator or get_faithfulness_evaluator()
    
    @property
    def provider_name(self) -> str:
        return "heuristic"
    
    @property
    def requires_llm(self) -> bool:
        return False
    
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        retrieval_scores: Optional[List[float]] = None,
        **kwargs
    ) -> EvaluationScores:
        """
        Perform heuristic evaluation.
        
        Args:
            query: User query
            answer: LLM-generated answer
            contexts: Retrieved context strings
            retrieval_scores: Optional similarity scores from retrieval
            
        Returns:
            EvaluationScores with heuristic metrics
        """
        start_time = time.time()
        scores = EvaluationScores(provider=self.provider_name)
        
        try:
            # Retrieval metrics
            retrieval_result = self.retrieval_eval.evaluate(query, contexts, retrieval_scores)
            scores.add_metric(MetricScore(
                name="Context Relevance",
                score=retrieval_result.context_relevance,
                category="retrieval",
                source="heuristic",
                details="Semantic + keyword match"
            ))
            scores.add_metric(MetricScore(
                name="Context Precision",
                score=retrieval_result.context_precision,
                category="retrieval",
                source="heuristic",
                details=f"Threshold-based"
            ))
            scores.add_metric(MetricScore(
                name="MRR",
                score=retrieval_result.mrr,
                category="retrieval",
                source="heuristic",
                details="Mean Reciprocal Rank"
            ))
            
            # Generation metrics
            generation_result = self.generation_eval.evaluate(query, answer, contexts)
            scores.add_metric(MetricScore(
                name="Answer Relevance",
                score=generation_result.answer_relevance,
                category="generation",
                source="heuristic",
                details="Query-answer alignment"
            ))
            scores.add_metric(MetricScore(
                name="Answer Completeness",
                score=generation_result.answer_completeness,
                category="generation",
                source="heuristic",
                details="Context coverage"
            ))
            scores.add_metric(MetricScore(
                name="Conciseness",
                score=generation_result.conciseness,
                category="generation",
                source="heuristic",
                details="Length appropriateness"
            ))
            
            # Faithfulness metrics
            faithfulness_result = self.faithfulness_eval.evaluate(answer, contexts)
            scores.add_metric(MetricScore(
                name="Faithfulness",
                score=faithfulness_result.faithfulness_score,
                category="faithfulness",
                source="heuristic",
                details="Context grounding"
            ))
            scores.add_metric(MetricScore(
                name="Citation Accuracy",
                score=faithfulness_result.citation_accuracy,
                category="faithfulness",
                source="heuristic",
                details="Number verification"
            ))
            
            # Set flags
            scores.hallucination_detected = faithfulness_result.hallucination_detected
            if faithfulness_result.unsupported_claims:
                scores.warnings.extend(faithfulness_result.unsupported_claims[:2])
            
            # Compute category and overall scores
            scores.compute_category_scores()
            
            # Determine reliability
            scores.is_reliable = (
                scores.overall_score >= 0.5 and
                not scores.hallucination_detected
            )
            
        except Exception as e:
            logger.error(f"Heuristic evaluation failed: {e}")
            scores.warnings.append(f"Evaluation error: {str(e)}")
        
        scores.evaluation_time_ms = (time.time() - start_time) * 1000
        return scores
    
    def quick_check(
        self,
        answer: str,
        contexts: List[str],
    ) -> Dict[str, Any]:
        """Quick faithfulness check only."""
        result = self.faithfulness_eval.evaluate(answer, contexts)
        return {
            'is_reliable': result.faithfulness_score >= 0.6,
            'hallucination_detected': result.hallucination_detected,
            'overall_score': result.faithfulness_score,
        }


# Global instance
_heuristic_evaluator: Optional[HeuristicEvaluator] = None


def get_heuristic_evaluator() -> HeuristicEvaluator:
    """Get or create global heuristic evaluator."""
    global _heuristic_evaluator
    if _heuristic_evaluator is None:
        _heuristic_evaluator = HeuristicEvaluator()
    return _heuristic_evaluator
