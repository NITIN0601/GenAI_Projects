"""
Row Matcher - Match and align row labels across tables.

Extracted for modularity from consolidation logic.

Used for merging tables with different row structures.
"""

from typing import Dict, List, Set, Any, Optional
import re
from src.utils import get_logger

logger = get_logger(__name__)


class RowMatcher:
    """
    Match and align row labels for table merging.
    
    Handles:
    - Fuzzy matching of row labels
    - Label normalization
    - Row alignment for horizontal merge
    
    Design: Stateless class methods for horizontal scaling.
    """
    
    @classmethod
    def normalize_label(cls, label: str) -> str:
        """
        Normalize a row label for matching.
        
        Args:
            label: Original row label
            
        Returns:
            Normalized label (lowercase, stripped, special chars removed)
        """
        if not label:
            return ''
        
        normalized = str(label).strip().lower()
        # Remove special characters but keep alphanumeric and spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    @classmethod
    def get_all_unique_labels(cls, tables: List[Dict[str, Any]]) -> List[str]:
        """
        Get all unique row labels across multiple tables, preserving order.
        
        Args:
            tables: List of table dicts with 'row_labels' key
            
        Returns:
            Ordered list of unique row labels
        """
        seen = set()
        all_labels = []
        
        for table in tables:
            for label in table.get('row_labels', []):
                normalized = cls.normalize_label(label)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    all_labels.append(label)  # Keep original form
        
        return all_labels
    
    @classmethod
    def build_label_to_row_map(cls, row_labels: List[str]) -> Dict[str, int]:
        """
        Build a mapping from normalized labels to row indices.
        
        Args:
            row_labels: List of row labels
            
        Returns:
            Dict mapping normalized labels to indices
        """
        return {
            cls.normalize_label(label): idx
            for idx, label in enumerate(row_labels)
        }
    
    @classmethod
    def align_rows(
        cls, 
        source_labels: List[str], 
        target_labels: List[str]
    ) -> Dict[int, int]:
        """
        Align source row indices to target row indices.
        
        Args:
            source_labels: Labels from source table
            target_labels: Labels in target (merged) table
            
        Returns:
            Dict mapping source indices to target indices
        """
        target_map = cls.build_label_to_row_map(target_labels)
        alignment = {}
        
        for src_idx, label in enumerate(source_labels):
            normalized = cls.normalize_label(label)
            if normalized in target_map:
                alignment[src_idx] = target_map[normalized]
        
        return alignment


__all__ = ['RowMatcher']
