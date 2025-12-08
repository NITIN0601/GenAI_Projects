"""
RAGAS Evaluation Provider.

Industry-standard RAG evaluation using the RAGAS framework.
Requires LLM calls for accurate assessment.
"""

from typing import List, Dict, Any, Optional
import logging
from src.utils import get_logger
import time

from src.evaluation.core.base import BaseEvaluator, EvaluationScores, MetricScore

logger = get_logger(__name__)

# Check if RAGAS is available
RAGAS_AVAILABLE = False
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from datasets import Dataset
    RAGAS_AVAILABLE = True
except ImportError:
    logger.warning("RAGAS not installed. Install with: pip install ragas")


class RAGASEvaluator(BaseEvaluator):
    """
    RAGAS-based evaluation provider.
    
    Uses the RAGAS framework for comprehensive RAG evaluation.
    Automatically uses the system's LLM_PROVIDER setting (local/custom/openai).
    
    Metrics:
    - Faithfulness: Is answer grounded in context?
    - Answer Relevancy: Does answer address the question?
    - Context Precision: How precise is the retrieved context?
    - Context Recall: Did we retrieve all relevant info?
    
    Best for:
    - Production evaluation
    - Comprehensive quality assessment
    - Benchmarking and reporting
    """
    
    def __init__(
        self,
        llm: Optional[Any] = None,
        embeddings: Optional[Any] = None,
        metrics: Optional[List[str]] = None,
        use_system_llm: bool = True,  # Use system's LLM_PROVIDER
    ):
        """
        Initialize RAGAS evaluator.
        
        Args:
            llm: LangChain LLM for evaluation (default: uses system LLM_PROVIDER)
            embeddings: LangChain embeddings (default: uses system EMBEDDING_PROVIDER)
            metrics: List of metric names to use (default: all)
            use_system_llm: If True, auto-use system LLM when llm not provided
        """
        if not RAGAS_AVAILABLE:
            raise ImportError(
                "RAGAS is not installed. Install with:\n"
                "  pip install ragas\n"
                "Or add 'ragas>=0.1.0' to requirements.txt"
            )
        
        # Auto-use system LLM if not explicitly provided
        if llm is None and use_system_llm:
            try:
                from src.infrastructure.llm.manager import get_llm_manager
                llm_manager = get_llm_manager()
                self.llm = llm_manager.get_llm()
                logger.info(f"Using system LLM for RAGAS: {llm_manager.provider}")
            except Exception as e:
                logger.warning(f"Could not get system LLM: {e}, RAGAS will use its default")
                self.llm = None
        else:
            self.llm = llm
        
        # Auto-use system embeddings if not explicitly provided
        if embeddings is None and use_system_llm:
            try:
                from src.infrastructure.embeddings.manager import get_embedding_manager
                emb_manager = get_embedding_manager()
                # Convert to LangChain embeddings if needed
                self.embeddings = emb_manager.get_langchain_embeddings()
                logger.info(f"Using system embeddings for RAGAS")
            except Exception as e:
                logger.debug(f"Could not get system embeddings: {e}")
                self.embeddings = None
        else:
            self.embeddings = embeddings
        
        # Select metrics
        self.available_metrics = {
            'faithfulness': faithfulness,
            'answer_relevancy': answer_relevancy,
            'context_precision': context_precision,
            'context_recall': context_recall,
        }
        
        if metrics:
            self.metrics_to_use = [
                self.available_metrics[m] 
                for m in metrics 
                if m in self.available_metrics
            ]
        else:
            # Use all metrics by default
            self.metrics_to_use = list(self.available_metrics.values())
    
    @property
    def provider_name(self) -> str:
        return "ragas"
    
    @property
    def requires_llm(self) -> bool:
        return True
    
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        **kwargs
    ) -> EvaluationScores:
        """
        Perform RAGAS evaluation.
        
        Args:
            query: User query
            answer: LLM-generated answer
            contexts: Retrieved context strings
            ground_truth: Optional ground truth answer for context_recall
            
        Returns:
            EvaluationScores with RAGAS metrics
        """
        start_time = time.time()
        scores = EvaluationScores(provider=self.provider_name)
        
        try:
            # Prepare dataset for RAGAS
            data = {
                'question': [query],
                'answer': [answer],
                'contexts': [contexts],
            }
            
            # Add ground truth if provided (required for context_recall)
            if ground_truth:
                data['ground_truth'] = [ground_truth]
            
            dataset = Dataset.from_dict(data)
            
            # Run RAGAS evaluation
            eval_kwargs = {'metrics': self.metrics_to_use}
            if self.llm:
                eval_kwargs['llm'] = self.llm
            if self.embeddings:
                eval_kwargs['embeddings'] = self.embeddings
            
            result = ragas_evaluate(dataset, **eval_kwargs)
            
            # Extract scores
            if 'faithfulness' in result:
                scores.add_metric(MetricScore(
                    name="Faithfulness",
                    score=float(result['faithfulness']),
                    category="faithfulness",
                    source="ragas",
                    details="LLM-judged grounding"
                ))
            
            if 'answer_relevancy' in result:
                scores.add_metric(MetricScore(
                    name="Answer Relevancy",
                    score=float(result['answer_relevancy']),
                    category="generation",
                    source="ragas",
                    details="LLM-judged relevance"
                ))
            
            if 'context_precision' in result:
                scores.add_metric(MetricScore(
                    name="Context Precision",
                    score=float(result['context_precision']),
                    category="retrieval",
                    source="ragas",
                    details="LLM-judged precision"
                ))
            
            if 'context_recall' in result:
                scores.add_metric(MetricScore(
                    name="Context Recall",
                    score=float(result['context_recall']),
                    category="retrieval",
                    source="ragas",
                    details="LLM-judged recall"
                ))
            
            # Compute overall scores
            scores.compute_category_scores()
            
            # Determine hallucination (faithfulness < 0.5)
            faithfulness_score = result.get('faithfulness', 1.0)
            scores.hallucination_detected = faithfulness_score < 0.5
            scores.is_reliable = scores.overall_score >= 0.6 and not scores.hallucination_detected
            
        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            scores.warnings.append(f"RAGAS error: {str(e)}")
            # Fallback to heuristic if RAGAS fails
            scores.warnings.append("Falling back to heuristic evaluation")
            try:
                from src.evaluation.heuristic_provider import get_heuristic_evaluator
                return get_heuristic_evaluator().evaluate(query, answer, contexts, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
        
        scores.evaluation_time_ms = (time.time() - start_time) * 1000
        return scores


def get_ragas_evaluator(
    llm: Optional[Any] = None,
    embeddings: Optional[Any] = None,
    metrics: Optional[List[str]] = None,
) -> RAGASEvaluator:
    """
    Create a RAGAS evaluator instance.
    
    Note: Unlike heuristic evaluator, RAGAS evaluator is not cached
    as a singleton since it may need different LLM/embedding configurations.
    
    Args:
        llm: LangChain LLM for evaluation
        embeddings: LangChain embeddings
        metrics: List of metric names
        
    Returns:
        RAGASEvaluator instance
    """
    return RAGASEvaluator(llm=llm, embeddings=embeddings, metrics=metrics)


def is_ragas_available() -> bool:
    """Check if RAGAS is installed and available."""
    return RAGAS_AVAILABLE
