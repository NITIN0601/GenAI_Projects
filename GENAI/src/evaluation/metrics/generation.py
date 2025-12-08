"""
Generation Quality Metrics.

Evaluates the quality of LLM-generated responses:
- Answer relevance to query
- Answer completeness
- Conciseness
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from src.utils import get_logger
import re

from config.settings import settings

logger = get_logger(__name__)


@dataclass
class GenerationMetrics:
    """Container for generation evaluation metrics."""
    answer_relevance: float    # 0-1: Does answer address the query
    answer_completeness: float # 0-1: Does answer cover key info
    conciseness: float         # 0-1: Is answer appropriately concise
    has_structure: bool        # Does answer have good structure
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'answer_relevance': self.answer_relevance,
            'answer_completeness': self.answer_completeness,
            'conciseness': self.conciseness,
            'has_structure': self.has_structure,
        }


class GenerationEvaluator:
    """
    Evaluate LLM response quality using heuristic methods.
    
    Assesses relevance, completeness, and formatting of responses.
    """
    
    def __init__(
        self,
        embedding_manager=None,
        min_answer_length: int = 20,
        max_answer_length: int = 2000,
    ):
        """
        Initialize generation evaluator.
        
        Args:
            embedding_manager: For semantic similarity computation
            min_answer_length: Minimum expected answer length
            max_answer_length: Maximum expected answer length
        """
        self.embedding_manager = embedding_manager
        self.min_answer_length = min_answer_length
        self.max_answer_length = max_answer_length
        
        if self.embedding_manager is None:
            try:
                from src.infrastructure.embeddings.manager import get_embedding_manager
                self.embedding_manager = get_embedding_manager()
            except Exception as e:
                logger.warning(f"Could not load embedding manager: {e}")
    
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: Optional[List[str]] = None,
    ) -> GenerationMetrics:
        """
        Evaluate generation quality.
        
        Args:
            query: Original query
            answer: LLM-generated answer
            contexts: Optional list of retrieved contexts
            
        Returns:
            GenerationMetrics with all computed metrics
        """
        if not answer or not answer.strip():
            return GenerationMetrics(
                answer_relevance=0.0,
                answer_completeness=0.0,
                conciseness=0.0,
                has_structure=False,
            )
        
        answer_relevance = self._compute_answer_relevance(query, answer)
        answer_completeness = self._compute_completeness(query, answer, contexts)
        conciseness = self._compute_conciseness(answer)
        has_structure = self._check_structure(answer)
        
        return GenerationMetrics(
            answer_relevance=answer_relevance,
            answer_completeness=answer_completeness,
            conciseness=conciseness,
            has_structure=has_structure,
        )
    
    def _compute_answer_relevance(self, query: str, answer: str) -> float:
        """
        Compute how relevant the answer is to the query.
        
        Uses a combination of:
        - Semantic similarity between query and answer
        - Key term overlap
        - Question type matching
        """
        # Extract key terms from query
        query_terms = self._extract_key_terms(query)
        
        # Check term coverage in answer
        answer_lower = answer.lower()
        terms_found = sum(1 for term in query_terms if term in answer_lower)
        term_coverage = terms_found / len(query_terms) if query_terms else 0.5
        
        # Check if answer addresses the question type
        question_type = self._detect_question_type(query)
        type_match = self._check_answer_type_match(answer, question_type)
        
        # Compute semantic similarity if available
        semantic_score = self._compute_semantic_similarity(query, answer)
        
        # Combine scores
        relevance = (
            0.3 * term_coverage +
            0.3 * type_match +
            0.4 * semantic_score
        )
        
        return min(relevance, 1.0)
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text, excluding stop words."""
        stop_words = {
            'what', 'was', 'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to',
            'for', 'of', 'and', 'or', 'how', 'much', 'many', 'when', 'where',
            'which', 'who', 'why', 'can', 'could', 'would', 'should', 'tell',
            'me', 'about', 'give', 'show', 'find', 'get', 'did', 'do', 'does',
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [w for w in words if w not in stop_words]
    
    def _detect_question_type(self, query: str) -> str:
        """Detect the type of question being asked."""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ['how much', 'what was', 'what is', 'total']):
            return 'quantitative'
        elif any(w in query_lower for w in ['why', 'explain', 'reason']):
            return 'explanatory'
        elif any(w in query_lower for w in ['compare', 'difference', 'versus', 'vs']):
            return 'comparative'
        elif any(w in query_lower for w in ['list', 'what are', 'show all']):
            return 'enumerative'
        elif any(w in query_lower for w in ['trend', 'change', 'growth', 'over time']):
            return 'trend'
        else:
            return 'general'
    
    def _check_answer_type_match(self, answer: str, question_type: str) -> float:
        """Check if answer format matches the question type."""
        answer_lower = answer.lower()
        
        if question_type == 'quantitative':
            # Should contain numbers
            has_numbers = bool(re.search(r'\$?\d+[\d,\.]*', answer))
            has_currency = '$' in answer or 'million' in answer_lower or 'billion' in answer_lower
            return 1.0 if (has_numbers or has_currency) else 0.3
        
        elif question_type == 'explanatory':
            # Should have explanatory connectors
            has_connectors = any(w in answer_lower for w in ['because', 'due to', 'since', 'therefore', 'as a result'])
            return 0.8 if has_connectors else 0.5
        
        elif question_type == 'comparative':
            # Should have comparison language
            has_comparison = any(w in answer_lower for w in ['compared to', 'higher', 'lower', 'increased', 'decreased', 'versus', 'while'])
            return 0.9 if has_comparison else 0.4
        
        elif question_type == 'enumerative':
            # Should have list structure
            has_list = bool(re.search(r'(?:\d+\.|[-•])\s', answer))
            return 0.9 if has_list else 0.5
        
        elif question_type == 'trend':
            # Should have trend language
            has_trend = any(w in answer_lower for w in ['increased', 'decreased', 'grew', 'declined', 'trend', 'growth', 'change'])
            return 0.8 if has_trend else 0.4
        
        return 0.6  # General questions
    
    def _compute_completeness(
        self,
        query: str,
        answer: str,
        contexts: Optional[List[str]],
    ) -> float:
        """
        Compute answer completeness.
        
        Checks if key information from contexts is included.
        """
        if not contexts:
            # Without contexts, use length and structure as proxy
            length_score = min(len(answer) / 200, 1.0)
            return length_score
        
        # Extract key numbers and facts from contexts
        context_numbers = self._extract_numbers(' '.join(contexts))
        answer_numbers = self._extract_numbers(answer)
        
        # Check number coverage
        if context_numbers:
            numbers_found = sum(1 for n in context_numbers if n in answer_numbers)
            number_coverage = numbers_found / min(len(context_numbers), 5)
        else:
            number_coverage = 0.5
        
        # Check key phrase coverage
        context_phrases = self._extract_key_phrases(' '.join(contexts))
        phrase_coverage = self._compute_phrase_coverage(context_phrases, answer)
        
        # Combine
        completeness = 0.5 * number_coverage + 0.5 * phrase_coverage
        
        return min(completeness, 1.0)
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Extract numeric values from text."""
        # Match various number formats: $1,234.56, 1.5 million, 15%, etc.
        patterns = [
            r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?',
            r'\d+(?:\.\d+)?%',
            r'\d+(?:,\d{3})+(?:\.\d+)?',
            r'\d+(?:\.\d+)?\s*(?:million|billion|thousand)',
        ]
        
        numbers = []
        for pattern in patterns:
            numbers.extend(re.findall(pattern, text.lower()))
        
        return numbers
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key financial phrases from text."""
        # Financial statement terms
        phrases = []
        financial_terms = [
            'total revenue', 'net income', 'operating income', 'gross profit',
            'total assets', 'total liabilities', 'shareholders equity',
            'cash flow', 'earnings per share', 'operating expenses',
        ]
        
        text_lower = text.lower()
        for term in financial_terms:
            if term in text_lower:
                phrases.append(term)
        
        return phrases[:5]  # Limit to top 5
    
    def _compute_phrase_coverage(self, phrases: List[str], answer: str) -> float:
        """Compute what fraction of key phrases appear in answer."""
        if not phrases:
            return 0.5
        
        answer_lower = answer.lower()
        found = sum(1 for phrase in phrases if phrase in answer_lower)
        
        return found / len(phrases)
    
    def _compute_conciseness(self, answer: str) -> float:
        """
        Compute conciseness score.
        
        Penalizes both too short and too long answers.
        """
        length = len(answer)
        
        if length < self.min_answer_length:
            return length / self.min_answer_length
        elif length > self.max_answer_length:
            excess = length - self.max_answer_length
            penalty = min(excess / self.max_answer_length, 0.5)
            return 1.0 - penalty
        else:
            # Ideal length range
            return 1.0
    
    def _check_structure(self, answer: str) -> bool:
        """Check if answer has good structure (paragraphs, lists, etc.)."""
        # Check for paragraph breaks
        has_paragraphs = '\n\n' in answer or len(answer.split('\n')) > 2
        
        # Check for lists
        has_lists = bool(re.search(r'(?:\d+\.|[-•])\s', answer))
        
        # Check for clear sections
        has_sections = bool(re.search(r'^#+\s|\*\*.*\*\*:', answer, re.MULTILINE))
        
        return has_paragraphs or has_lists or has_sections
    
    def _compute_semantic_similarity(self, query: str, answer: str) -> float:
        """Compute semantic similarity between query and answer."""
        if self.embedding_manager is None:
            return 0.5  # Default when embeddings unavailable
        
        try:
            query_emb = self.embedding_manager.generate_embedding(query)
            answer_emb = self.embedding_manager.generate_embedding(answer[:500])  # Limit length
            
            # Cosine similarity
            import numpy as np
            vec1 = np.array(query_emb)
            vec2 = np.array(answer_emb)
            
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Semantic similarity failed: {e}")
            return 0.5


# Global instance
_generation_evaluator: Optional[GenerationEvaluator] = None


def get_generation_evaluator() -> GenerationEvaluator:
    """Get or create global generation evaluator."""
    global _generation_evaluator
    if _generation_evaluator is None:
        _generation_evaluator = GenerationEvaluator()
    return _generation_evaluator
