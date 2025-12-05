"""
Financial Validator.

Validates financial accuracy in LLM responses:
- Number verification against source contexts
- Calculation validation
- Currency format checking
- Stale data detection
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class NumberValidation:
    """Result of validating a single number."""
    value_in_response: str
    found_in_context: bool
    matching_context_value: Optional[str] = None
    discrepancy: Optional[str] = None


@dataclass
class FinancialValidationResult:
    """Result of financial validation."""
    is_valid: bool
    accuracy_score: float  # 0-1
    number_validations: List[NumberValidation] = field(default_factory=list)
    calculation_errors: List[str] = field(default_factory=list)
    format_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'accuracy_score': self.accuracy_score,
            'number_validations': [
                {
                    'value': nv.value_in_response,
                    'found': nv.found_in_context,
                    'match': nv.matching_context_value,
                    'discrepancy': nv.discrepancy,
                }
                for nv in self.number_validations
            ],
            'calculation_errors': self.calculation_errors,
            'format_issues': self.format_issues,
            'warnings': self.warnings,
        }


class FinancialValidator:
    """
    Validate financial accuracy in responses.
    
    Checks:
    - Numbers match source documents
    - Calculations are correct
    - Currency formats are consistent
    - Data is not stale
    """
    
    def __init__(
        self,
        tolerance: float = 0.01,  # 1% tolerance for number matching
        strict_numbers: bool = False,  # Require exact matches
    ):
        """
        Initialize financial validator.
        
        Args:
            tolerance: Tolerance for numeric comparisons (percentage)
            strict_numbers: If True, require exact number matches
        """
        self.tolerance = tolerance
        self.strict_numbers = strict_numbers
    
    def validate(
        self,
        response: str,
        contexts: List[str],
    ) -> FinancialValidationResult:
        """
        Validate financial accuracy of response against contexts.
        
        Args:
            response: LLM response to validate
            contexts: Source contexts to validate against
            
        Returns:
            FinancialValidationResult with validation details
        """
        number_validations = []
        calculation_errors = []
        format_issues = []
        warnings = []
        
        combined_context = '\n'.join(contexts).lower()
        
        # Extract and validate numbers
        response_numbers = self._extract_numbers(response)
        context_numbers = self._extract_numbers(combined_context)
        
        for num_str in response_numbers:
            validation = self._validate_number(num_str, context_numbers, combined_context)
            number_validations.append(validation)
        
        # Check calculations
        calc_errors = self._validate_calculations(response)
        calculation_errors.extend(calc_errors)
        
        # Check currency formatting
        format_issues.extend(self._check_currency_format(response))
        
        # Check for potential stale data
        stale_warnings = self._check_stale_data(response, contexts)
        warnings.extend(stale_warnings)
        
        # Compute accuracy score
        if number_validations:
            correct_count = sum(1 for v in number_validations if v.found_in_context)
            accuracy_score = correct_count / len(number_validations)
        else:
            accuracy_score = 1.0  # No numbers to validate
        
        # Determine overall validity
        is_valid = (
            accuracy_score >= 0.7 and
            len(calculation_errors) == 0
        )
        
        return FinancialValidationResult(
            is_valid=is_valid,
            accuracy_score=accuracy_score,
            number_validations=number_validations,
            calculation_errors=calculation_errors,
            format_issues=format_issues,
            warnings=warnings,
        )
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Extract financial numbers from text."""
        patterns = [
            # Currency amounts: $1,234.56, $1.5 million
            r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand|M|B|K))?',
            # Percentages: 15.5%, 100%
            r'-?\d+(?:\.\d+)?%',
            # Large numbers with commas: 1,234,567
            r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b',
            # Decimal numbers: 123.45
            r'\b\d+\.\d+\b',
            # Numbers with magnitude: 1.5 million
            r'\b\d+(?:\.\d+)?\s*(?:million|billion|thousand|M|B|K)\b',
        ]
        
        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.extend(matches)
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for num in numbers:
            normalized = num.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(num)
        
        return unique
    
    def _validate_number(
        self,
        num_str: str,
        context_numbers: List[str],
        full_context: str,
    ) -> NumberValidation:
        """Validate a single number against context."""
        num_normalized = self._normalize_number(num_str)
        
        # Try exact match first
        num_lower = num_str.lower()
        for ctx_num in context_numbers:
            ctx_lower = ctx_num.lower()
            
            if num_lower == ctx_lower:
                return NumberValidation(
                    value_in_response=num_str,
                    found_in_context=True,
                    matching_context_value=ctx_num,
                )
        
        # Try normalized value match
        for ctx_num in context_numbers:
            ctx_normalized = self._normalize_number(ctx_num)
            
            if num_normalized == ctx_normalized:
                return NumberValidation(
                    value_in_response=num_str,
                    found_in_context=True,
                    matching_context_value=ctx_num,
                )
            
            # Check within tolerance
            if not self.strict_numbers and num_normalized > 0 and ctx_normalized > 0:
                diff = abs(num_normalized - ctx_normalized) / max(num_normalized, ctx_normalized)
                if diff <= self.tolerance:
                    return NumberValidation(
                        value_in_response=num_str,
                        found_in_context=True,
                        matching_context_value=ctx_num,
                        discrepancy=f"Within {diff*100:.1f}% tolerance",
                    )
        
        # Check if the raw string appears in context (for formatted numbers)
        if num_str.lower().replace(',', '') in full_context.replace(',', ''):
            return NumberValidation(
                value_in_response=num_str,
                found_in_context=True,
            )
        
        return NumberValidation(
            value_in_response=num_str,
            found_in_context=False,
            discrepancy="Not found in source documents",
        )
    
    def _normalize_number(self, num_str: str) -> float:
        """Normalize a number string to float value."""
        num = num_str.lower().strip()
        
        # Remove currency symbols and commas
        num = num.replace('$', '').replace(',', '')
        
        # Handle percentages
        is_percent = '%' in num
        num = num.replace('%', '')
        
        # Handle magnitude suffixes
        multiplier = 1.0
        if 'billion' in num or num.endswith('b'):
            multiplier = 1e9
            num = num.replace('billion', '').replace('b', '')
        elif 'million' in num or num.endswith('m'):
            multiplier = 1e6
            num = num.replace('million', '').replace('m', '')
        elif 'thousand' in num or num.endswith('k'):
            multiplier = 1e3
            num = num.replace('thousand', '').replace('k', '')
        
        try:
            value = float(num.strip()) * multiplier
            if is_percent:
                value = value / 100  # Convert to decimal
            return value
        except ValueError:
            return 0.0
    
    def _validate_calculations(self, response: str) -> List[str]:
        """Validate any calculations in the response."""
        errors = []
        
        # Look for calculation patterns
        # Pattern: "X + Y = Z" or "X plus Y equals Z"
        calc_patterns = [
            r'(\$?[\d,]+(?:\.\d+)?)\s*\+\s*(\$?[\d,]+(?:\.\d+)?)\s*=\s*(\$?[\d,]+(?:\.\d+)?)',
            r'(\$?[\d,]+(?:\.\d+)?)\s*-\s*(\$?[\d,]+(?:\.\d+)?)\s*=\s*(\$?[\d,]+(?:\.\d+)?)',
        ]
        
        for pattern in calc_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                try:
                    val1 = self._normalize_number(match[0])
                    val2 = self._normalize_number(match[1])
                    result = self._normalize_number(match[2])
                    
                    if '+' in pattern:
                        expected = val1 + val2
                    else:
                        expected = val1 - val2
                    
                    if abs(expected - result) > 0.01:  # Allow small rounding errors
                        errors.append(
                            f"Calculation error: {match[0]} ± {match[1]} = {match[2]} "
                            f"(expected ~{expected:,.2f})"
                        )
                except Exception:
                    continue
        
        # Check percentage calculations
        pct_pattern = r'(\d+(?:\.\d+)?%)\s+of\s+\$?([\d,]+(?:\.\d+)?)\s+(?:is|equals?)\s+\$?([\d,]+(?:\.\d+)?)'
        matches = re.findall(pct_pattern, response, re.IGNORECASE)
        
        for match in matches:
            try:
                pct = float(match[0].replace('%', '')) / 100
                base = self._normalize_number(match[1])
                result = self._normalize_number(match[2])
                expected = pct * base
                
                if abs(expected - result) / max(expected, 1) > 0.05:  # 5% tolerance
                    errors.append(
                        f"Percentage calculation error: {match[0]} of ${match[1]} = ${match[2]} "
                        f"(expected ~${expected:,.2f})"
                    )
            except Exception:
                continue
        
        return errors
    
    def _check_currency_format(self, response: str) -> List[str]:
        """Check for currency formatting issues."""
        issues = []
        
        # Check for inconsistent decimal places
        currency_values = re.findall(r'\$[\d,]+(?:\.\d+)?', response)
        
        decimal_places = set()
        for val in currency_values:
            if '.' in val:
                decimals = len(val.split('.')[1])
                decimal_places.add(decimals)
        
        if len(decimal_places) > 1 and {1, 3, 4}.intersection(decimal_places):
            issues.append("Inconsistent decimal places in currency values")
        
        # Check for numbers that should probably be currency
        large_nums = re.findall(r'\b(?<!\$)\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?\b', response)
        if large_nums:
            issues.append(f"Large numbers without currency symbol: {large_nums[:2]}")
        
        return issues
    
    def _check_stale_data(
        self,
        response: str,
        contexts: List[str],
    ) -> List[str]:
        """Check for potential use of stale/outdated data."""
        warnings = []
        
        # Extract years from response
        response_years = set(re.findall(r'\b(20\d{2})\b', response))
        
        # Extract years from contexts
        context_years = set()
        for ctx in contexts:
            context_years.update(re.findall(r'\b(20\d{2})\b', ctx))
        
        # Check for years in response not in context
        missing_years = response_years - context_years
        if missing_years:
            warnings.append(
                f"Response mentions years not found in source documents: {missing_years}"
            )
        
        return warnings
    
    def validate_numbers_quick(
        self,
        response: str,
        contexts: List[str],
    ) -> Tuple[bool, float]:
        """
        Quick validation of numbers in response.
        
        Returns:
            Tuple of (all_valid, accuracy_percentage)
        """
        result = self.validate(response, contexts)
        return result.is_valid, result.accuracy_score


# Global instance
_financial_validator: Optional[FinancialValidator] = None


def get_financial_validator() -> FinancialValidator:
    """Get or create global financial validator."""
    global _financial_validator
    if _financial_validator is None:
        _financial_validator = FinancialValidator()
    return _financial_validator
