"""
Faithfulness Evaluation.

Detects hallucinations and validates that LLM responses
are grounded in the retrieved contexts.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging
from src.utils import get_logger
import re

from config.settings import settings

logger = get_logger(__name__)


@dataclass
class FaithfulnessMetrics:
    """Container for faithfulness evaluation metrics."""
    faithfulness_score: float      # 0-1: Overall groundedness
    hallucination_detected: bool   # Any unsupported claims found
    unsupported_claims: List[str]  # List of potentially hallucinated statements
    citation_accuracy: float       # 0-1: Accuracy of cited numbers
    grounded_facts: int           # Count of facts verified in context
    unverified_facts: int         # Count of facts not in context
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'faithfulness_score': self.faithfulness_score,
            'hallucination_detected': self.hallucination_detected,
            'unsupported_claims': self.unsupported_claims,
            'citation_accuracy': self.citation_accuracy,
            'grounded_facts': self.grounded_facts,
            'unverified_facts': self.unverified_facts,
        }


@dataclass
class FactClaim:
    """A factual claim extracted from the answer."""
    text: str
    claim_type: str  # 'numeric', 'temporal', 'entity', 'comparative', 'general'
    value: Optional[str] = None  # Extracted value (for numeric claims)
    is_grounded: bool = False
    confidence: float = 0.0


class FaithfulnessEvaluator:
    """
    Evaluate faithfulness of LLM responses to retrieved contexts.
    
    Detects hallucinations by:
    1. Extracting factual claims from the answer
    2. Verifying each claim against the contexts
    3. Flagging unsupported claims as potential hallucinations
    """
    
    def __init__(
        self,
        strict_mode: bool = False,
        numeric_tolerance: float = 0.05,  # 5% tolerance for numeric comparisons
    ):
        """
        Initialize faithfulness evaluator.
        
        Args:
            strict_mode: If True, require exact matches for verification
            numeric_tolerance: Tolerance for numeric value comparisons
        """
        self.strict_mode = strict_mode
        self.numeric_tolerance = numeric_tolerance
    
    def evaluate(
        self,
        answer: str,
        contexts: List[str],
    ) -> FaithfulnessMetrics:
        """
        Evaluate faithfulness of answer to contexts.
        
        Args:
            answer: LLM-generated answer
            contexts: List of retrieved context strings
            
        Returns:
            FaithfulnessMetrics with all computed metrics
        """
        if not answer or not contexts:
            return FaithfulnessMetrics(
                faithfulness_score=0.0,
                hallucination_detected=True,
                unsupported_claims=["No answer or context provided"],
                citation_accuracy=0.0,
                grounded_facts=0,
                unverified_facts=0,
            )
        
        # Combine contexts for easier searching
        combined_context = '\n'.join(contexts).lower()
        
        # Extract claims from answer
        claims = self._extract_claims(answer)
        
        # Verify each claim
        grounded_claims = []
        unsupported_claims = []
        
        for claim in claims:
            is_grounded, confidence = self._verify_claim(claim, combined_context)
            claim.is_grounded = is_grounded
            claim.confidence = confidence
            
            if is_grounded:
                grounded_claims.append(claim)
            else:
                unsupported_claims.append(claim.text)
        
        # Compute citation accuracy (for numeric claims)
        numeric_claims = [c for c in claims if c.claim_type == 'numeric']
        citation_accuracy = self._compute_citation_accuracy(numeric_claims, combined_context)
        
        # Compute overall faithfulness
        total_claims = len(claims)
        grounded_count = len(grounded_claims)
        
        if total_claims == 0:
            faithfulness_score = 0.5  # No claims to verify
        else:
            faithfulness_score = grounded_count / total_claims
        
        # Determine if hallucination detected
        hallucination_threshold = 0.3 if self.strict_mode else 0.5
        hallucination_detected = (
            len(unsupported_claims) > 0 and 
            (1 - faithfulness_score) > hallucination_threshold
        )
        
        return FaithfulnessMetrics(
            faithfulness_score=faithfulness_score,
            hallucination_detected=hallucination_detected,
            unsupported_claims=unsupported_claims[:5],  # Limit to top 5
            citation_accuracy=citation_accuracy,
            grounded_facts=grounded_count,
            unverified_facts=len(unsupported_claims),
        )
    
    def _extract_claims(self, answer: str) -> List[FactClaim]:
        """
        Extract verifiable claims from the answer.
        
        Identifies:
        - Numeric claims (amounts, percentages, etc.)
        - Temporal claims (dates, periods, etc.)
        - Entity claims (company names, products, etc.)
        - Comparative claims (increases, decreases, etc.)
        """
        claims = []
        
        # Split into sentences
        sentences = self._split_sentences(answer)
        
        for sentence in sentences:
            sentence_claims = self._extract_sentence_claims(sentence)
            claims.extend(sentence_claims)
        
        return claims
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _extract_sentence_claims(self, sentence: str) -> List[FactClaim]:
        """Extract claims from a single sentence."""
        claims = []
        
        # Numeric claims (money, percentages, counts)
        numeric_patterns = [
            (r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?', 'numeric'),
            (r'\d+(?:\.\d+)?%', 'numeric'),
            (r'\d+(?:,\d{3})+(?:\.\d+)?', 'numeric'),
            (r'\d+(?:\.\d+)?\s*(?:million|billion|thousand)', 'numeric'),
        ]
        
        for pattern, claim_type in numeric_patterns:
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for match in matches:
                claims.append(FactClaim(
                    text=sentence,
                    claim_type=claim_type,
                    value=match,
                ))
        
        # Temporal claims
        temporal_patterns = [
            r'(?:Q[1-4]|first|second|third|fourth)\s*(?:quarter|qtr)',
            r'20\d{2}',
            r'(?:fiscal|calendar)\s*year',
        ]
        
        for pattern in temporal_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                claims.append(FactClaim(
                    text=sentence,
                    claim_type='temporal',
                ))
                break  # One temporal claim per sentence
        
        # Comparative claims
        comparative_words = [
            'increased', 'decreased', 'grew', 'declined', 'rose', 'fell',
            'higher', 'lower', 'more', 'less', 'up', 'down',
        ]
        
        sentence_lower = sentence.lower()
        for word in comparative_words:
            if word in sentence_lower:
                claims.append(FactClaim(
                    text=sentence,
                    claim_type='comparative',
                ))
                break
        
        # If no specific claims, treat substantial sentences as general claims
        if not claims and len(sentence.split()) > 5:
            claims.append(FactClaim(
                text=sentence,
                claim_type='general',
            ))
        
        return claims
    
    def _verify_claim(
        self,
        claim: FactClaim,
        context: str,
    ) -> Tuple[bool, float]:
        """
        Verify if a claim is supported by the context.
        
        Returns:
            Tuple of (is_grounded, confidence)
        """
        if claim.claim_type == 'numeric':
            return self._verify_numeric_claim(claim, context)
        elif claim.claim_type == 'temporal':
            return self._verify_temporal_claim(claim, context)
        elif claim.claim_type == 'comparative':
            return self._verify_comparative_claim(claim, context)
        else:
            return self._verify_general_claim(claim, context)
    
    def _verify_numeric_claim(
        self,
        claim: FactClaim,
        context: str,
    ) -> Tuple[bool, float]:
        """Verify a numeric claim against context."""
        if not claim.value:
            return False, 0.0
        
        # Normalize the value
        value_normalized = self._normalize_number(claim.value)
        
        # Find numbers in context
        context_numbers = re.findall(
            r'\$?[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?',
            context,
            re.IGNORECASE
        )
        
        for ctx_num in context_numbers:
            ctx_normalized = self._normalize_number(ctx_num)
            
            # Check exact match
            if value_normalized == ctx_normalized:
                return True, 1.0
            
            # Check within tolerance
            try:
                if self._numbers_within_tolerance(value_normalized, ctx_normalized):
                    return True, 0.8
            except (ValueError, TypeError):
                continue
        
        return False, 0.0
    
    def _normalize_number(self, num_str: str) -> float:
        """Normalize a number string to a float value."""
        num_str = num_str.lower().replace(',', '').replace('$', '').strip()
        
        multiplier = 1.0
        if 'billion' in num_str:
            multiplier = 1e9
            num_str = num_str.replace('billion', '').strip()
        elif 'million' in num_str:
            multiplier = 1e6
            num_str = num_str.replace('million', '').strip()
        elif 'thousand' in num_str:
            multiplier = 1e3
            num_str = num_str.replace('thousand', '').strip()
        
        try:
            return float(num_str) * multiplier
        except ValueError:
            return 0.0
    
    def _numbers_within_tolerance(self, val1: float, val2: float) -> bool:
        """Check if two numbers are within tolerance."""
        if val1 == 0 and val2 == 0:
            return True
        if val1 == 0 or val2 == 0:
            return False
        
        diff = abs(val1 - val2) / max(val1, val2)
        return diff <= self.numeric_tolerance
    
    def _verify_temporal_claim(
        self,
        claim: FactClaim,
        context: str,
    ) -> Tuple[bool, float]:
        """Verify a temporal claim against context."""
        claim_lower = claim.text.lower()
        
        # Extract year/quarter from claim
        year_match = re.search(r'20\d{2}', claim.text)
        quarter_match = re.search(r'Q[1-4]|(?:first|second|third|fourth)\s*quarter', claim.text, re.IGNORECASE)
        
        found_year = False
        found_quarter = False
        
        if year_match and year_match.group() in context:
            found_year = True
        
        if quarter_match:
            quarter_text = quarter_match.group().lower()
            if quarter_text in context.lower():
                found_quarter = True
        
        if found_year and found_quarter:
            return True, 1.0
        elif found_year or found_quarter:
            return True, 0.7
        else:
            return False, 0.0
    
    def _verify_comparative_claim(
        self,
        claim: FactClaim,
        context: str,
    ) -> Tuple[bool, float]:
        """Verify a comparative claim against context."""
        # Check if the comparison terms exist in context
        comparative_words = ['increased', 'decreased', 'grew', 'declined', 'rose', 'fell',
                           'higher', 'lower', 'growth', 'decline']
        
        claim_lower = claim.text.lower()
        context_lower = context.lower()
        
        # Find which comparative word is used in claim
        used_word = None
        for word in comparative_words:
            if word in claim_lower:
                used_word = word
                break
        
        if used_word and used_word in context_lower:
            return True, 0.8
        
        # Check for related words in context
        positive_words = {'increased', 'grew', 'rose', 'higher', 'growth', 'up'}
        negative_words = {'decreased', 'declined', 'fell', 'lower', 'decline', 'down'}
        
        if used_word in positive_words:
            if any(w in context_lower for w in positive_words):
                return True, 0.6
        elif used_word in negative_words:
            if any(w in context_lower for w in negative_words):
                return True, 0.6
        
        return False, 0.0
    
    def _verify_general_claim(
        self,
        claim: FactClaim,
        context: str,
    ) -> Tuple[bool, float]:
        """Verify a general claim using keyword overlap."""
        # Extract key terms from claim
        claim_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', claim.text.lower()))
        
        # Remove common words
        stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'could', 'should'}
        claim_words -= stop_words
        
        if not claim_words:
            return True, 0.5  # No specific terms to verify
        
        # Check overlap with context
        context_lower = context.lower()
        found_words = sum(1 for word in claim_words if word in context_lower)
        overlap_ratio = found_words / len(claim_words)
        
        if overlap_ratio >= 0.5:
            return True, overlap_ratio
        else:
            return False, overlap_ratio
    
    def _compute_citation_accuracy(
        self,
        numeric_claims: List[FactClaim],
        context: str,
    ) -> float:
        """Compute accuracy of numeric citations."""
        if not numeric_claims:
            return 1.0  # No numbers to verify
        
        accurate_count = sum(1 for c in numeric_claims if c.is_grounded)
        return accurate_count / len(numeric_claims)


# Global instance
_faithfulness_evaluator: Optional[FaithfulnessEvaluator] = None


def get_faithfulness_evaluator() -> FaithfulnessEvaluator:
    """Get or create global faithfulness evaluator."""
    global _faithfulness_evaluator
    if _faithfulness_evaluator is None:
        _faithfulness_evaluator = FaithfulnessEvaluator()
    return _faithfulness_evaluator
