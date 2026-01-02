"""
Period Type Detector - Classify column headers by period type pattern.

Used by: consolidated_exporter.py
"""

import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from src.utils import get_logger

logger = get_logger(__name__)


class PeriodTypeDetector:
    """
    Detect and classify period types in column headers.
    
    Groups:
    - point_in_time: Qn-YYYY (e.g., Q4-2024, Q3-2025)
    - period_based: Qn-QTD-YYYY, Qn-YTD-YYYY (e.g., Q3-QTD-2024, Q3-YTD-2024)
    - annual: YYYY only (e.g., 2024, 2025)
    - other: Non-period columns (Row Label, metadata, etc.)
    """
    
    # Pattern definitions - order matters (more specific first)
    PATTERNS = {
        'period_based': re.compile(r'Q[1-4]-(QTD|YTD)-\d{4}'),  # Q3-QTD-2024, Q3-YTD-2024
        'point_in_time': re.compile(r'^Q[1-4]-\d{4}$'),          # Q4-2024 (exact match)
        'annual': re.compile(r'^\d{4}$'),                        # 2024, 2025 (exact 4 digits)
    }
    
    # Suffix mapping for sheet naming
    SUFFIX_MAP = {
        'point_in_time': '_1',
        'period_based': '_2',
        'annual': '_3',
    }
    
    # Human-readable labels for Index
    LABEL_MAP = {
        'point_in_time': '(Point-in-Time)',
        'period_based': '(Period-Based)',
        'annual': '(Annual)',
    }
    
    @classmethod
    def classify_header(cls, header: str) -> str:
        """
        Classify a single column header by period type.
        
        Args:
            header: Column header string (e.g., 'Q4-2024', 'Q3-YTD-2024')
            
        Returns:
            Period type: 'point_in_time', 'period_based', 'annual', or 'other'
        """
        if not header or not isinstance(header, str):
            return 'other'
        
        header = header.strip()
        
        # Skip obvious non-period values
        if not header or header.lower() in ['nan', 'none', '', 'row label']:
            return 'other'
        
        # Check patterns in order (most specific first)
        for period_type, pattern in cls.PATTERNS.items():
            if pattern.search(header):
                return period_type
        
        return 'other'
    
    @classmethod
    def group_columns_by_type(
        cls, 
        columns: List[str],
        include_other: bool = True
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Group columns by their period type.
        
        Args:
            columns: List of column headers
            include_other: If True, include non-period columns in each group
            
        Returns:
            Dict mapping period_type -> [(col_index, col_header), ...]
        """
        groups = defaultdict(list)
        other_columns = []
        
        for idx, header in enumerate(columns):
            period_type = cls.classify_header(str(header))
            
            if period_type == 'other':
                other_columns.append((idx, header))
            else:
                groups[period_type].append((idx, header))
        
        # If include_other, add non-period columns to each group
        # (these are typically Row Label and other metadata columns)
        if include_other and other_columns:
            for period_type in groups:
                # Prepend 'other' columns (they should come first, e.g., Row Label)
                groups[period_type] = other_columns + groups[period_type]
        
        return dict(groups)
    
    @classmethod
    def get_suffix(cls, period_type: str) -> str:
        """Get sheet name suffix for a period type."""
        return cls.SUFFIX_MAP.get(period_type, '')
    
    @classmethod
    def get_label(cls, period_type: str) -> str:
        """Get human-readable label for Index entries."""
        return cls.LABEL_MAP.get(period_type, '')
    
    @classmethod
    def detect_mixed_types(cls, columns: List[str]) -> bool:
        """
        Check if columns contain multiple period types (would need split).
        
        Args:
            columns: List of column headers
            
        Returns:
            True if multiple period types detected
        """
        period_types = set()
        
        for header in columns:
            period_type = cls.classify_header(str(header))
            if period_type != 'other':
                period_types.add(period_type)
        
        return len(period_types) > 1
    
    @classmethod
    def analyze_dataframe_columns(
        cls,
        df,
        header_row_idx: int = 0
    ) -> Dict[str, any]:
        """
        Analyze a DataFrame to determine period type composition.
        
        Args:
            df: pandas DataFrame
            header_row_idx: Row index containing column headers
            
        Returns:
            Dict with:
            - 'types_found': set of period types
            - 'needs_split': bool
            - 'groups': Dict mapping type -> column indices
        """
        import pandas as pd
        
        if df.empty:
            return {'types_found': set(), 'needs_split': False, 'groups': {}}
        
        # Get header row values
        if header_row_idx < len(df):
            headers = [str(df.iloc[header_row_idx, col]) for col in range(len(df.columns))]
        else:
            headers = [str(col) for col in df.columns]
        
        groups = cls.group_columns_by_type(headers, include_other=False)
        types_found = set(groups.keys())
        
        return {
            'types_found': types_found,
            'needs_split': len(types_found) > 1,
            'groups': groups
        }
