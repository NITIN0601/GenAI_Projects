"""
Output Guard.

Validates LLM output before returning to user:
- Response validation
- Disclaimer injection based on confidence
- Sensitive data filtering
- Financial response formatting
"""

from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass
import logging
from src.utils import get_logger
import re

logger = get_logger(__name__)


@dataclass
class OutputValidationResult:
    """Result of output validation."""
    is_valid: bool
    processed_response: str
    original_response: str
    modifications: List[str]
    disclaimers_added: List[str]
    confidence_level: str


class OutputGuard:
    """
    Validate and process LLM output before returning to user.
    
    Handles:
    - Adding appropriate disclaimers
    - Filtering sensitive information
    - Formatting financial data
    - Marking low-confidence responses
    """
    
    def __init__(
        self,
        add_disclaimers: bool = True,
        filter_sensitive: bool = True,
        format_financial: bool = True,
        moderate_mode: bool = True,  # Add warnings but still return
    ):
        """
        Initialize output guard.
        
        Args:
            add_disclaimers: Whether to add confidence-based disclaimers
            filter_sensitive: Whether to filter sensitive information
            format_financial: Whether to format financial data
            moderate_mode: If True, add warnings; if False, block low-confidence
        """
        self.add_disclaimers = add_disclaimers
        self.filter_sensitive = filter_sensitive
        self.format_financial = format_financial
        self.moderate_mode = moderate_mode
        
        # Sensitive patterns to filter
        self.sensitive_patterns = [
            r'\b[A-Z]{2}\d{6,9}\b',  # SSN-like patterns
            r'\b\d{16}\b',  # Credit card-like
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email (if sensitive)
            r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone numbers
        ]
        
        # Disclaimer templates
        self.disclaimers = {
            'high': None,  # No disclaimer for high confidence
            'medium': "ℹ️ *This information is derived from the provided documents. Please verify critical figures.*",
            'low': "⚠️ **Note:** This response has lower confidence. Some information may be incomplete or require verification.",
            'very_low': "⚠️ **Warning:** This response has very low confidence. The information may be unreliable and should be independently verified.",
            'hallucination': "🚨 **Caution:** Some statements in this response may not be fully supported by the source documents. Please verify all facts.",
        }
    
    def validate(
        self,
        response: str,
        confidence_level: str = 'medium',
        evaluation_result: Optional[Any] = None,
    ) -> OutputValidationResult:
        """
        Validate and process LLM response.
        
        Args:
            response: Raw LLM response
            confidence_level: Confidence level ('high', 'medium', 'low', 'very_low')
            evaluation_result: Optional EvaluationResult for detailed checks
            
        Returns:
            OutputValidationResult with processed response
        """
        modifications = []
        disclaimers_added = []
        original_response = response
        processed = response
        
        # Check for empty response
        if not processed or not processed.strip():
            return OutputValidationResult(
                is_valid=False,
                processed_response="I couldn't generate a response. Please try rephrasing your question.",
                original_response=original_response,
                modifications=["Replaced empty response"],
                disclaimers_added=[],
                confidence_level=confidence_level,
            )
        
        # Filter sensitive information
        if self.filter_sensitive:
            processed, sensitive_found = self._filter_sensitive(processed)
            if sensitive_found:
                modifications.append("Filtered potentially sensitive information")
        
        # Format financial data
        if self.format_financial:
            processed, formatting_applied = self._format_financial_data(processed)
            if formatting_applied:
                modifications.append("Applied financial formatting")
        
        # Add disclaimers based on confidence
        if self.add_disclaimers:
            processed, disclaimer = self._add_disclaimer(
                processed, 
                confidence_level, 
                evaluation_result
            )
            if disclaimer:
                disclaimers_added.append(disclaimer)
        
        # In non-moderate mode, block very low confidence
        is_valid = True
        if not self.moderate_mode and confidence_level == 'very_low':
            is_valid = False
            modifications.append("Response blocked due to very low confidence")
        
        return OutputValidationResult(
            is_valid=is_valid,
            processed_response=processed,
            original_response=original_response,
            modifications=modifications,
            disclaimers_added=disclaimers_added,
            confidence_level=confidence_level,
        )
    
    def _filter_sensitive(self, response: str) -> Tuple[str, bool]:
        """Filter sensitive information from response."""
        found_sensitive = False
        processed = response
        
        for pattern in self.sensitive_patterns:
            if re.search(pattern, processed):
                processed = re.sub(pattern, '[REDACTED]', processed)
                found_sensitive = True
        
        return processed, found_sensitive
    
    def _format_financial_data(self, response: str) -> Tuple[str, bool]:
        """Apply consistent formatting to financial data."""
        formatting_applied = False
        processed = response
        
        # Ensure consistent currency formatting
        # Add commas to large numbers without them
        def add_commas(match):
            num = match.group(1)
            if ',' not in num and len(num) > 3:
                # Add commas to number
                formatted = '{:,}'.format(int(float(num)))
                return f'${formatted}'
            return match.group(0)
        
        # Match dollar amounts without commas
        pattern = r'\$(\d{4,}(?:\.\d{2})?)'
        if re.search(pattern, processed):
            processed = re.sub(pattern, add_commas, processed)
            formatting_applied = True
        
        return processed, formatting_applied
    
    def _add_disclaimer(
        self,
        response: str,
        confidence_level: str,
        evaluation_result: Optional[Any] = None,
    ) -> Tuple[str, Optional[str]]:
        """Add appropriate disclaimer based on confidence and evaluation."""
        # Check for hallucination
        has_hallucination = False
        if evaluation_result is not None:
            if hasattr(evaluation_result, 'has_hallucinations'):
                has_hallucination = evaluation_result.has_hallucinations
            elif hasattr(evaluation_result, 'faithfulness'):
                has_hallucination = (
                    evaluation_result.faithfulness and 
                    evaluation_result.faithfulness.hallucination_detected
                )
        
        # Select disclaimer
        if has_hallucination:
            disclaimer = self.disclaimers['hallucination']
        else:
            disclaimer = self.disclaimers.get(confidence_level)
        
        if disclaimer:
            processed = f"{response}\n\n---\n{disclaimer}"
            return processed, disclaimer
        
        return response, None
    
    def add_sources_section(
        self,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> str:
        """Add a sources section to the response."""
        if not sources:
            return response
        
        sources_text = "\n\n---\n**Sources:**\n"
        
        for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
            doc = source.get('source_doc', source.get('filename', 'Unknown'))
            page = source.get('page_no', 'N/A')
            title = source.get('table_title', source.get('title', ''))
            
            if title:
                sources_text += f"{i}. {doc} (Page {page}) - {title}\n"
            else:
                sources_text += f"{i}. {doc} (Page {page})\n"
        
        return response + sources_text
    
    def format_error_response(self, error: str) -> str:
        """Format an error response appropriately."""
        return (
            f"I apologize, but I encountered an issue while processing your request.\n\n"
            f"**Error:** {error}\n\n"
            f"Please try rephrasing your question or contact support if the issue persists."
        )


# Global instance
_output_guard: Optional[OutputGuard] = None


def get_output_guard() -> OutputGuard:
    """Get or create global output guard."""
    global _output_guard
    if _output_guard is None:
        _output_guard = OutputGuard()
    return _output_guard
