"""
Input Guard.

Validates and sanitizes user input before processing:
- Query validation
- Prompt injection detection
- Financial query classification
"""

from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class InputValidationResult:
    """Result of input validation."""
    is_valid: bool
    cleaned_query: str
    original_query: str
    issues: List[str]
    filters_extracted: Dict[str, Any]
    query_type: str  # 'financial', 'general', 'off_topic', 'potentially_harmful'


class InputGuard:
    """
    Validate and sanitize user input.
    
    Checks for:
    - Empty or too short queries
    - Prompt injection attempts
    - Off-topic queries
    - Extracts temporal and entity filters
    """
    
    def __init__(
        self,
        min_query_length: int = 3,
        max_query_length: int = 1000,
        strict_mode: bool = False,
    ):
        """
        Initialize input guard.
        
        Args:
            min_query_length: Minimum allowed query length
            max_query_length: Maximum allowed query length
            strict_mode: If True, block off-topic queries
        """
        self.min_query_length = min_query_length
        self.max_query_length = max_query_length
        self.strict_mode = strict_mode
        
        # Prompt injection patterns
        self.injection_patterns = [
            r'ignore\s+(previous|all|above)\s+instructions?',
            r'disregard\s+.*\s+instructions?',
            r'forget\s+(everything|all|your)',
            r'you\s+are\s+now\s+a',
            r'pretend\s+you\s+are',
            r'act\s+as\s+(if|a)',
            r'new\s+instructions?:',
            r'system\s*:\s*',
            r'</?(system|user|assistant)>',
            r'\[INST\]|\[/INST\]',
            r'<\|im_start\|>|<\|im_end\|>',
        ]
        
        # Financial keywords for classification
        self.financial_keywords = [
            'revenue', 'income', 'profit', 'loss', 'earnings', 'eps',
            'assets', 'liabilities', 'equity', 'debt', 'cash',
            'balance sheet', 'income statement', 'cash flow',
            'quarter', 'q1', 'q2', 'q3', 'q4', 'annual', 'fiscal',
            'margin', 'growth', 'ratio', 'return', 'yield',
            'dividend', 'stock', 'share', 'market', 'cap',
            'financial', 'report', 'filing', 'sec', '10-k', '10-q',
        ]
        
        # Off-topic patterns
        self.off_topic_patterns = [
            r'write\s+(me\s+)?(a\s+)?(poem|story|song|code|script)',
            r'tell\s+me\s+a\s+joke',
            r'what\s+is\s+the\s+(meaning|purpose)\s+of\s+life',
            r'(play|sing|dance|draw)',
            r'(recipe|cook|bake)',
            r'(weather|news|sports)\s+(today|now|in)',
        ]
    
    def validate(self, query: str) -> InputValidationResult:
        """
        Validate and process user input.
        
        Args:
            query: Raw user query
            
        Returns:
            InputValidationResult with validation details
        """
        issues = []
        original_query = query
        
        # Basic sanitization
        cleaned_query = self._sanitize_query(query)
        
        # Check length
        if len(cleaned_query) < self.min_query_length:
            issues.append("Query too short")
            return InputValidationResult(
                is_valid=False,
                cleaned_query=cleaned_query,
                original_query=original_query,
                issues=issues,
                filters_extracted={},
                query_type='invalid',
            )
        
        if len(cleaned_query) > self.max_query_length:
            issues.append("Query too long, truncating")
            cleaned_query = cleaned_query[:self.max_query_length]
        
        # Check for prompt injection
        if self._detect_prompt_injection(cleaned_query):
            issues.append("Potential prompt injection detected")
            return InputValidationResult(
                is_valid=False,
                cleaned_query=cleaned_query,
                original_query=original_query,
                issues=issues,
                filters_extracted={},
                query_type='potentially_harmful',
            )
        
        # Classify query
        query_type = self._classify_query(cleaned_query)
        
        # Handle off-topic in strict mode
        if self.strict_mode and query_type == 'off_topic':
            issues.append("Query appears to be off-topic for financial analysis")
            return InputValidationResult(
                is_valid=False,
                cleaned_query=cleaned_query,
                original_query=original_query,
                issues=issues,
                filters_extracted={},
                query_type=query_type,
            )
        
        # Extract filters
        filters = self._extract_filters(cleaned_query)
        
        # Add warnings for general queries
        if query_type == 'general':
            issues.append("Query may be outside financial domain")
        
        return InputValidationResult(
            is_valid=True,
            cleaned_query=cleaned_query,
            original_query=original_query,
            issues=issues,
            filters_extracted=filters,
            query_type=query_type,
        )
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize query by removing potentially harmful content."""
        # Strip whitespace
        cleaned = query.strip()
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Remove potential HTML/XML tags
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        # Remove control characters
        cleaned = ''.join(c for c in cleaned if c.isprintable() or c.isspace())
        
        return cleaned
    
    def _detect_prompt_injection(self, query: str) -> bool:
        """Detect potential prompt injection attempts."""
        query_lower = query.lower()
        
        for pattern in self.injection_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"Prompt injection pattern detected: {pattern}")
                return True
        
        # Check for suspicious character sequences
        if '```' in query and ('system' in query_lower or 'instruction' in query_lower):
            return True
        
        return False
    
    def _classify_query(self, query: str) -> str:
        """Classify query as financial, general, or off-topic."""
        query_lower = query.lower()
        
        # Check for off-topic patterns
        for pattern in self.off_topic_patterns:
            if re.search(pattern, query_lower):
                return 'off_topic'
        
        # Check for financial keywords
        financial_score = sum(1 for kw in self.financial_keywords if kw in query_lower)
        
        if financial_score >= 2:
            return 'financial'
        elif financial_score == 1:
            return 'general'  # Borderline
        else:
            return 'general'
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract temporal and entity filters from query."""
        filters = {}
        query_lower = query.lower()
        
        # Extract year
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            filters['year'] = int(year_match.group(1))
        
        # Extract quarter
        quarter_patterns = [
            (r'\bq1\b', 'Q1'),
            (r'\bq2\b', 'Q2'),
            (r'\bq3\b', 'Q3'),
            (r'\bq4\b', 'Q4'),
            (r'\bfirst\s+quarter\b', 'Q1'),
            (r'\bsecond\s+quarter\b', 'Q2'),
            (r'\bthird\s+quarter\b', 'Q3'),
            (r'\bfourth\s+quarter\b', 'Q4'),
        ]
        
        for pattern, quarter in quarter_patterns:
            if re.search(pattern, query_lower):
                filters['quarter'] = quarter
                break
        
        # Extract statement type
        statement_patterns = [
            (r'balance\s+sheet', 'Balance Sheet'),
            (r'income\s+statement', 'Income Statement'),
            (r'cash\s+flow', 'Cash Flow Statement'),
            (r'statement\s+of\s+operations', 'Income Statement'),
        ]
        
        for pattern, stmt_type in statement_patterns:
            if re.search(pattern, query_lower):
                filters['statement_type'] = stmt_type
                break
        
        return filters
    
    def is_financial_query(self, query: str) -> bool:
        """Quick check if query is financial."""
        return self._classify_query(query) == 'financial'


# Global instance
_input_guard: Optional[InputGuard] = None


def get_input_guard() -> InputGuard:
    """Get or create global input guard."""
    global _input_guard
    if _input_guard is None:
        _input_guard = InputGuard()
    return _input_guard
