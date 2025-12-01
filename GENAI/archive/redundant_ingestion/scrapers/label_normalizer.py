"""Normalize row labels across documents using canonical mappings."""

from rapidfuzz import fuzz, process
from typing import Tuple, Dict, List, Optional


class LabelNormalizer:
    """
    Normalize row labels across documents using canonical mappings.
    
    This enables aggregation of the same financial line item across
    documents even when labeled differently.
    """
    
    # Canonical label mappings for common financial line items
    CANONICAL_LABELS = {
        # Revenue items
        'net_revenues': [
            'net revenues',
            'total net revenues',
            'revenues, net',
            'revenue, net',
            'net revenue',
            'total revenues',
            'revenues'
        ],
        'investment_banking_revenue': [
            'investment banking',
            'investment banking revenues',
            'investment banking fees',
            'ib revenues'
        ],
        'trading_revenue': [
            'trading',
            'trading revenues',
            'trading income',
            'net trading revenue'
        ],
        'interest_income': [
            'interest income',
            'interest and dividend income',
            'interest revenue',
            'net interest income'
        ],
        
        # Asset items
        'total_assets': [
            'total assets',
            'assets, total',
            'assets at end of period',
            'total assets at period end',
            'assets'
        ],
        'cash_and_equivalents': [
            'cash and cash equivalents',
            'cash and equivalents',
            'cash',
            'cash and due from banks'
        ],
        'securities': [
            'securities',
            'investment securities',
            'trading securities',
            'available-for-sale securities'
        ],
        'loans': [
            'loans',
            'total loans',
            'loans and leases',
            'loans receivable',
            'net loans'
        ],
        
        # Liability items
        'total_liabilities': [
            'total liabilities',
            'liabilities, total',
            'total liabilities and equity',
            'liabilities'
        ],
        'deposits': [
            'deposits',
            'total deposits',
            'customer deposits',
            'deposit liabilities'
        ],
        'borrowings': [
            'borrowings',
            'short-term borrowings',
            'long-term debt',
            'debt'
        ],
        
        # Equity items
        'shareholders_equity': [
            'shareholders equity',
            'stockholders equity',
            'total equity',
            'equity',
            'total shareholders equity'
        ],
        'common_stock': [
            'common stock',
            'common shares',
            'common equity'
        ],
        'retained_earnings': [
            'retained earnings',
            'accumulated earnings',
            'retained income'
        ],
        
        # Expense items
        'operating_expenses': [
            'operating expenses',
            'total operating expenses',
            'expenses from operations',
            'operational expenses',
            'non-interest expenses'
        ],
        'compensation_expense': [
            'compensation and benefits',
            'employee compensation',
            'compensation expense',
            'salaries and benefits'
        ],
        'provision_for_credit_losses': [
            'provision for credit losses',
            'credit loss provision',
            'loan loss provision',
            'allowance for credit losses'
        ],
        
        # Income items
        'net_income': [
            'net income',
            'net earnings',
            'income applicable to common shareholders',
            'net income applicable to morgan stanley'
        ],
        'operating_income': [
            'operating income',
            'income from operations',
            'operating profit'
        ],
        'pretax_income': [
            'income before taxes',
            'pretax income',
            'earnings before taxes',
            'income before income taxes'
        ],
        
        # Cash flow items
        'operating_cash_flow': [
            'cash flows from operating activities',
            'net cash from operations',
            'operating activities',
            'cash from operations'
        ],
        'investing_cash_flow': [
            'cash flows from investing activities',
            'net cash from investing',
            'investing activities',
            'cash used in investing'
        ],
        'financing_cash_flow': [
            'cash flows from financing activities',
            'net cash from financing',
            'financing activities',
            'cash from financing'
        ]
    }
    
    def __init__(self, custom_mappings: Optional[Dict[str, List[str]]] = None):
        """
        Initialize label normalizer.
        
        Args:
            custom_mappings: Additional custom label mappings to add
        """
        self.mappings = self.CANONICAL_LABELS.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)
        
        # Build reverse lookup for fast exact matching
        self.reverse_lookup = {}
        for canonical, variations in self.mappings.items():
            for variation in variations:
                self.reverse_lookup[variation.lower()] = canonical
    
    def canonicalize(
        self, 
        label: str, 
        threshold: int = 85,
        return_confidence: bool = True
    ) -> Tuple[str, float]:
        """
        Find canonical label using fuzzy matching.
        
        Args:
            label: Original label text
            threshold: Minimum similarity score (0-100)
            return_confidence: Whether to return confidence score
        
        Returns:
            (canonical_label, confidence_score)
        """
        label_lower = label.lower().strip()
        
        # Check exact match first (fast path)
        if label_lower in self.reverse_lookup:
            return self.reverse_lookup[label_lower], 1.0
        
        # Fuzzy matching
        best_match = None
        best_score = 0
        best_canonical = None
        
        for canonical, variations in self.mappings.items():
            for variation in variations:
                score = fuzz.ratio(label_lower, variation)
                if score > best_score:
                    best_score = score
                    best_match = variation
                    best_canonical = canonical
        
        # Return match if above threshold
        if best_score >= threshold:
            confidence = best_score / 100.0
            return best_canonical, confidence
        
        # No match found - create canonical from original
        canonical = label_lower.replace(' ', '_').replace(',', '').replace('.', '')
        return canonical, 0.0
    
    def add_mapping(self, canonical: str, variations: List[str]):
        """
        Add a new canonical mapping.
        
        Args:
            canonical: Canonical label
            variations: List of variations that map to this canonical
        """
        if canonical in self.mappings:
            self.mappings[canonical].extend(variations)
        else:
            self.mappings[canonical] = variations
        
        # Update reverse lookup
        for variation in variations:
            self.reverse_lookup[variation.lower()] = canonical
    
    def get_all_canonicals(self) -> List[str]:
        """Get list of all canonical labels."""
        return list(self.mappings.keys())
    
    def get_variations(self, canonical: str) -> List[str]:
        """Get all variations for a canonical label."""
        return self.mappings.get(canonical, [])


# Global normalizer instance
_normalizer: Optional[LabelNormalizer] = None


def get_label_normalizer() -> LabelNormalizer:
    """Get or create global label normalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = LabelNormalizer()
    return _normalizer
