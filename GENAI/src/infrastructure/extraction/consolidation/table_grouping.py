"""
Table Grouping - Fuzzy matching and grouping logic for table consolidation.

Standalone module for grouping tables by title/section for merging.
Used by: consolidated_exporter.py
"""

import re
from typing import Dict, List, Optional
from difflib import SequenceMatcher


class TableGrouper:
    """
    Group tables by fuzzy-matching titles and sections.
    
    Handles:
    - Fuzzy title matching with configurable threshold
    - Header normalization for deduplication
    - Structure-based grouping constraints
    """
    
    # Month abbreviation to full mapping
    MONTH_ABBREVIATIONS = {
        'jan': 'january', 'feb': 'february', 'mar': 'march',
        'apr': 'april', 'may': 'may', 'jun': 'june', 
        'jul': 'july', 'aug': 'august', 'sep': 'september',
        'oct': 'october', 'nov': 'november', 'dec': 'december'
    }
    
    @classmethod
    def find_fuzzy_matching_group(
        cls,
        all_tables_by_full_title: Dict[str, List],
        section_title_combo: str,
        structure_key: str,
        threshold: float = 0.80
    ) -> Optional[str]:
        """
        Find an existing group key that fuzzy-matches the given Section+Title combo.
        
        Args:
            all_tables_by_full_title: Existing groups dictionary
            section_title_combo: The Section|Title combination to match
            structure_key: The exact structure (fingerprint::header_pattern) that must match
            threshold: Minimum similarity ratio (default 0.80 = 80%)
        
        Returns:
            The matching key if found (similarity >= threshold), None otherwise
        """
        best_match_key = None
        best_ratio = 0.0
        
        for existing_key in all_tables_by_full_title.keys():
            # Split the existing key to extract Section+Title and structure parts
            # Key format: "section_title_combo::structure_fingerprint::header_pattern"
            parts = existing_key.split('::')
            if len(parts) >= 2:
                existing_section_title = parts[0]
                existing_structure = '::'.join(parts[1:])
                
                # Structure key must match exactly
                if existing_structure != structure_key:
                    continue
                
                # Compare Section+Title with fuzzy matching
                ratio = SequenceMatcher(None, section_title_combo.lower(), existing_section_title.lower()).ratio()
                
                if ratio >= threshold and ratio > best_ratio:
                    best_match_key = existing_key
                    best_ratio = ratio
        
        return best_match_key
    
    @classmethod
    def normalize_header_for_deduplication(cls, header: str) -> str:
        """
        Normalize header for deduplication comparison.
        
        Handles minor variations in header text to prevent duplicate columns:
        - Case normalization (title case)
        - Month abbreviation expansion (Dec → December)
        - Trailing punctuation removal
        - Decimal number cleanup (2024.0 → 2024)
        
        Examples:
            "three months ended june 30," → "Three Months Ended June 30"
            "At Dec 31, 2024" → "At December 31 2024"
            "2024.0" → "2024"
        
        Args:
            header: Original header string
            
        Returns:
            Normalized header string for comparison
        """
        if not header:
            return ""
        
        header = str(header).strip()
        
        # Remove trailing punctuation
        header = header.rstrip('.,;:')
        
        # Expand month abbreviations
        header_lower = header.lower()
        for abbr, full in cls.MONTH_ABBREVIATIONS.items():
            # Use word boundaries to avoid partial matches
            header_lower = re.sub(f'\\b{abbr}\\b', full, header_lower)
        
        # Remove .0 from year values (e.g., 2024.0 → 2024)
        header_lower = re.sub(r'(\d{4})\.0\b', r'\1', header_lower)
        
        # Title case for consistency
        header = header_lower.title()
        
        return header
    
    @classmethod
    def create_grouping_key(
        cls,
        section: str,
        title: str,
        structure_fingerprint: str,
        header_pattern: str
    ) -> str:
        """
        Create a standardized grouping key for table merge lookup.
        
        Format: "section|title::structure_fingerprint::header_pattern"
        
        Args:
            section: Section name (e.g., "Institutional Securities")
            title: Table title (e.g., "Income Statement")
            structure_fingerprint: Row structure hash
            header_pattern: L1/L2/L3 pattern (e.g., "L2_L3::CUMULATIVE")
            
        Returns:
            Composite grouping key
        """
        section_clean = section.strip() if section else ''
        title_clean = title.strip() if title else ''
        
        section_title = f"{section_clean}|{title_clean}" if section_clean else title_clean
        return f"{section_title}::{structure_fingerprint}::{header_pattern}"
    
    @classmethod
    def extract_key_parts(cls, grouping_key: str) -> Dict[str, str]:
        """
        Extract component parts from a grouping key.
        
        Args:
            grouping_key: Full grouping key
            
        Returns:
            Dict with 'section_title', 'structure', 'pattern' keys
        """
        parts = grouping_key.split('::')
        
        return {
            'section_title': parts[0] if len(parts) > 0 else '',
            'structure': parts[1] if len(parts) > 1 else '',
            'pattern': parts[2] if len(parts) > 2 else ''
        }
    
    @classmethod
    def calculate_similarity(cls, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two strings.
        
        Uses difflib SequenceMatcher for fuzzy comparison.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Float between 0.0 and 1.0 representing similarity
        """
        if not text1 or not text2:
            return 0.0
        
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
