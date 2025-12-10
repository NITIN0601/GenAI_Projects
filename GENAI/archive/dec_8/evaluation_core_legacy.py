"""
RAG Evaluator - Main Orchestrator.

Combines all evaluation metrics into a unified evaluation result.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from src.utils import get_logger

from src.evaluation.metrics.retrieval import (
    RetrievalEvaluator,
    RetrievalMetrics,
    get_retrieval_evaluator,
)
from src.evaluation.metrics.generation import (
    GenerationEvaluator,
    GenerationMetrics,
    get_generation_evaluator,
)
from src.evaluation.metrics.faithfulness import (
    FaithfulnessEvaluator,
    FaithfulnessMetrics,
    get_faithfulness_evaluator,
)

logger = get_logger(__name__)


class ConfidenceLevel(str, Enum):
    """Confidence level classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


@dataclass
class EvaluationConfig:
    """Configuration for RAG evaluation."""
    evaluate_retrieval: bool = True
    evaluate_generation: bool = True
    evaluate_faithfulness: bool = True
    
    # Thresholds
    high_confidence_threshold: float = 0.8
    medium_confidence_threshold: float = 0.6
    low_confidence_threshold: float = 0.4
    
    # Weights for overall score
    retrieval_weight: float = 0.25
    generation_weight: float = 0.25
    faithfulness_weight: float = 0.50  # Faithfulness most important


@dataclass
class EvaluationResult:
    """Comprehensive evaluation result."""
    # Individual metrics
    retrieval: Optional[RetrievalMetrics] = None
    generation: Optional[GenerationMetrics] = None
    faithfulness: Optional[FaithfulnessMetrics] = None
    
    # Overall scores
    overall_score: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    
    # Warnings and recommendations
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    evaluation_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'retrieval': self.retrieval.to_dict() if self.retrieval else None,
            'generation': self.generation.to_dict() if self.generation else None,
            'faithfulness': self.faithfulness.to_dict() if self.faithfulness else None,
            'overall_score': self.overall_score,
            'confidence_level': self.confidence_level.value,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'evaluation_time_ms': self.evaluation_time_ms,
        }
    
    @property
    def is_reliable(self) -> bool:
        """Check if the response can be considered reliable."""
        return (
            self.overall_score >= 0.6 and
            self.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM] and
            (self.faithfulness is None or not self.faithfulness.hallucination_detected)
        )
    
    @property
    def has_hallucinations(self) -> bool:
        """Check if hallucinations were detected."""
        return self.faithfulness is not None and self.faithfulness.hallucination_detected


class RAGEvaluator:
    """
    Unified RAG evaluation orchestrator.
    
    Combines retrieval, generation, and faithfulness evaluation
    into a single comprehensive assessment.
    """
    
    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        retrieval_evaluator: Optional[RetrievalEvaluator] = None,
        generation_evaluator: Optional[GenerationEvaluator] = None,
        faithfulness_evaluator: Optional[FaithfulnessEvaluator] = None,
    ):
        """
        Initialize RAG evaluator.
        
        Args:
            config: Evaluation configuration
            retrieval_evaluator: Custom retrieval evaluator
            generation_evaluator: Custom generation evaluator
            faithfulness_evaluator: Custom faithfulness evaluator
        """
        self.config = config or EvaluationConfig()
        
        self.retrieval_eval = retrieval_evaluator or get_retrieval_evaluator()
        self.generation_eval = generation_evaluator or get_generation_evaluator()
        self.faithfulness_eval = faithfulness_evaluator or get_faithfulness_evaluator()
    
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        retrieval_scores: Optional[List[float]] = None,
    ) -> EvaluationResult:
        """
        Run comprehensive RAG evaluation.
        
        Args:
            query: Original user query
            answer: LLM-generated answer
            contexts: List of retrieved context strings
            retrieval_scores: Optional similarity scores from retrieval
            
        Returns:
            EvaluationResult with all metrics and recommendations
        """
        import time
        start_time = time.time()
        
        result = EvaluationResult()
        warnings = []
        recommendations = []
        
        # Evaluate retrieval
        if self.config.evaluate_retrieval:
            try:
                result.retrieval = self.retrieval_eval.evaluate(
                    query, contexts, retrieval_scores
                )
                
                # Add warnings based on retrieval quality
                if result.retrieval.context_relevance < 0.5:
                    warnings.append("Low context relevance detected")
                    recommendations.append("Consider rephrasing the query for better results")
                
                if result.retrieval.mrr < 0.5:
                    recommendations.append("Top results may not be the most relevant")
                    
            except Exception as e:
                logger.warning(f"Retrieval evaluation failed: {e}")
                warnings.append(f"Retrieval evaluation error: {str(e)}")
        
        # Evaluate generation
        if self.config.evaluate_generation:
            try:
                result.generation = self.generation_eval.evaluate(
                    query, answer, contexts
                )
                
                # Add warnings based on generation quality
                if result.generation.answer_relevance < 0.5:
                    warnings.append("Answer may not fully address the question")
                
                if result.generation.conciseness < 0.5:
                    recommendations.append("Answer could be more concise")
                    
            except Exception as e:
                logger.warning(f"Generation evaluation failed: {e}")
                warnings.append(f"Generation evaluation error: {str(e)}")
        
        # Evaluate faithfulness (most critical)
        if self.config.evaluate_faithfulness:
            try:
                result.faithfulness = self.faithfulness_eval.evaluate(
                    answer, contexts
                )
                
                # Add warnings for hallucinations
                if result.faithfulness.hallucination_detected:
                    warnings.append("⚠️ Potential hallucination detected - verify facts manually")
                    
                    if result.faithfulness.unsupported_claims:
                        claims_preview = result.faithfulness.unsupported_claims[:2]
                        recommendations.append(
                            f"Unsupported claims: {'; '.join(claims_preview)[:100]}..."
                        )
                
                if result.faithfulness.citation_accuracy < 0.7:
                    warnings.append("Some cited numbers may not match source documents")
                    
            except Exception as e:
                logger.warning(f"Faithfulness evaluation failed: {e}")
                warnings.append(f"Faithfulness evaluation error: {str(e)}")
        
        # Compute overall score
        result.overall_score = self._compute_overall_score(result)
        
        # Determine confidence level
        result.confidence_level = self._determine_confidence_level(result)
        
        # Set warnings and recommendations
        result.warnings = warnings
        result.recommendations = recommendations
        
        # Record timing
        result.evaluation_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Evaluation complete: score={result.overall_score:.2f}, "
            f"confidence={result.confidence_level.value}, "
            f"time={result.evaluation_time_ms:.1f}ms"
        )
        
        return result
    
    def _compute_overall_score(self, result: EvaluationResult) -> float:
        """Compute weighted overall score."""
        scores = []
        weights = []
        
        if result.retrieval:
            scores.append(result.retrieval.context_relevance)
            weights.append(self.config.retrieval_weight)
        
        if result.generation:
            # Average of generation metrics
            gen_score = (
                result.generation.answer_relevance * 0.5 +
                result.generation.answer_completeness * 0.3 +
                result.generation.conciseness * 0.2
            )
            scores.append(gen_score)
            weights.append(self.config.generation_weight)
        
        if result.faithfulness:
            scores.append(result.faithfulness.faithfulness_score)
            weights.append(self.config.faithfulness_weight)
        
        if not scores:
            return 0.0
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Weighted average
        overall = sum(s * w for s, w in zip(scores, normalized_weights))
        
        # Penalty for hallucinations
        if result.faithfulness and result.faithfulness.hallucination_detected:
            overall *= 0.7  # 30% penalty
        
        return min(overall, 1.0)
    
    def _determine_confidence_level(self, result: EvaluationResult) -> ConfidenceLevel:
        """Determine confidence level based on scores."""
        score = result.overall_score
        
        # Automatic low confidence for hallucinations
        if result.faithfulness and result.faithfulness.hallucination_detected:
            return ConfidenceLevel.LOW
        
        if score >= self.config.high_confidence_threshold:
            return ConfidenceLevel.HIGH
        elif score >= self.config.medium_confidence_threshold:
            return ConfidenceLevel.MEDIUM
        elif score >= self.config.low_confidence_threshold:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def quick_evaluate(
        self,
        answer: str,
        contexts: List[str],
    ) -> Dict[str, Any]:
        """
        Quick evaluation focusing only on faithfulness.
        
        Useful for real-time checks without full evaluation overhead.
        
        Args:
            answer: LLM-generated answer
            contexts: List of retrieved contexts
            
        Returns:
            Dict with faithfulness score and hallucination flag
        """
        faithfulness = self.faithfulness_eval.evaluate(answer, contexts)
        
        return {
            'faithfulness_score': faithfulness.faithfulness_score,
            'hallucination_detected': faithfulness.hallucination_detected,
            'is_reliable': faithfulness.faithfulness_score >= 0.6,
            'unsupported_claims_count': len(faithfulness.unsupported_claims),
        }


# Global instance
_rag_evaluator: Optional[RAGEvaluator] = None


def get_rag_evaluator(config: Optional[EvaluationConfig] = None) -> RAGEvaluator:
    """Get or create global RAG evaluator."""
    global _rag_evaluator
    if _rag_evaluator is None:
        _rag_evaluator = RAGEvaluator(config=config)
    return _rag_evaluator
