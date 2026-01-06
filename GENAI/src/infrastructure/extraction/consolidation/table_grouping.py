"""
Table Grouping - Fuzzy matching and grouping logic for table consolidation.

Standalone module for grouping tables by title/section for merging.
Used by: consolidated_exporter.py

Merge Conditions (ALL must be satisfied):
1. Table Title: 80%+ fuzzy match on normalized title
2. First Column (Row Labels): 80%+ Jaccard overlap on Category + Line Items
3. Column Header Pattern: Must match period type format (Qn-YYYY, Qn-QTD-YYYY, YTD-YYYY)
"""

import re
from typing import Dict, List, Optional, Tuple, Set
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
        threshold: float = 0.80,
        row_labels: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Find an existing group key that fuzzy-matches using 80% conditions.
        
        Merge Conditions (ALL must be satisfied):
        1. Table Title: 80%+ fuzzy match on normalized title
        2. First Column (Row Labels): 80%+ Jaccard overlap (if row_labels provided)
        3. Header Pattern: Must match exactly (via structure_key)
        
        Args:
            all_tables_by_full_title: Existing groups dictionary with table data
            section_title_combo: The Section|Title combination to match
            structure_key: The exact structure (fingerprint::header_pattern) that must match
            threshold: Minimum similarity ratio (default 0.80 = 80%)
            row_labels: Optional list of row labels for overlap checking
        
        Returns:
            The matching key if found, None otherwise
        """
        best_match_key = None
        best_score = 0.0
        
        # Split input into section and title
        if '|' in section_title_combo:
            input_section, input_title = section_title_combo.split('|', 1)
        else:
            input_section = ''
            input_title = section_title_combo
        
        input_title_lower = input_title.lower().strip()
        
        for existing_key, existing_tables in all_tables_by_full_title.items():
            # Split the existing key to extract Section+Title and structure parts
            # Key format: "section|title::structure_fingerprint::header_pattern"
            parts = existing_key.split('::')
            if len(parts) >= 2:
                existing_section_title = parts[0]
                existing_structure = '::'.join(parts[1:])
                
                # Structure key must match exactly (header pattern check)
                if existing_structure != structure_key:
                    continue
                
                # Split existing key into section and title
                if '|' in existing_section_title:
                    existing_section, existing_title = existing_section_title.split('|', 1)
                else:
                    existing_section = ''
                    existing_title = existing_section_title
                
                existing_title_lower = existing_title.lower().strip()
                
                # Condition 1: Title fuzzy match (80% threshold)
                title_ratio = SequenceMatcher(None, input_title_lower, existing_title_lower).ratio()
                
                if title_ratio < threshold:
                    continue
                
                # Condition 2: Row label overlap (80% threshold) - if row_labels provided
                row_overlap = 1.0  # Default to pass if no row_labels
                if row_labels and existing_tables:
                    # Get row_labels from the first table in the existing group
                    existing_row_labels = existing_tables[0].get('metadata', {}).get('row_labels', [])
                    if existing_row_labels:
                        row_overlap, meets_threshold = cls.calculate_row_label_overlap(
                            row_labels, existing_row_labels, threshold
                        )
                        if not meets_threshold:
                            continue
                
                # Calculate combined score (average of title and row overlap)
                combined_score = (title_ratio + row_overlap) / 2
                
                if combined_score > best_score:
                    best_match_key = existing_key
                    best_score = combined_score
        
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
    
    @classmethod
    def normalize_row_label(cls, label: str) -> str:
        """
        Normalize a row label for comparison.
        
        Handles:
        - Case normalization (lowercase)
        - Whitespace normalization
        - Punctuation removal
        - Common financial abbreviations
        
        Args:
            label: Original row label
            
        Returns:
            Normalized label for comparison
        """
        if not label:
            return ""
        
        label = str(label).strip().lower()
        
        # Remove common prefixes that don't affect meaning
        prefixes_to_remove = ['total ', 'net ', 'less: ', 'add: ']
        for prefix in prefixes_to_remove:
            if label.startswith(prefix):
                label = label[len(prefix):]
        
        # Normalize whitespace and remove punctuation
        label = re.sub(r'\s+', ' ', label)
        label = re.sub(r'[^\w\s]', '', label)
        
        return label.strip()
    
    @classmethod
    def calculate_row_label_overlap(
        cls,
        source_rows: List[str],
        target_rows: List[str],
        threshold: float = 0.80
    ) -> Tuple[float, bool]:
        """
        Calculate Jaccard overlap between two sets of row labels.
        
        This determines structural similarity between tables by comparing
        their first column values (Category/Line Items).
        
        Args:
            source_rows: Row labels from source table
            target_rows: Row labels from target table
            threshold: Minimum overlap ratio (default 0.80 = 80%)
            
        Returns:
            Tuple of (overlap_ratio, meets_threshold)
        """
        # Normalize all labels
        source_normalized = {cls.normalize_row_label(r) for r in source_rows if r and str(r).strip()}
        target_normalized = {cls.normalize_row_label(r) for r in target_rows if r and str(r).strip()}
        
        # Filter out empty and metadata labels
        skip_labels = {'', 'nan', 'none', 'row label', '$ in millions', '$ in billions'}
        source_normalized = source_normalized - skip_labels
        target_normalized = target_normalized - skip_labels
        
        if not source_normalized or not target_normalized:
            return 0.0, False
        
        # Calculate Jaccard similarity: |intersection| / |union|
        intersection = source_normalized & target_normalized
        union = source_normalized | target_normalized
        
        overlap = len(intersection) / len(union) if union else 0.0
        return overlap, overlap >= threshold
    
    @classmethod
    def should_merge_tables(
        cls,
        source_title: str,
        target_title: str,
        source_rows: List[str],
        target_rows: List[str],
        source_header_pattern: str,
        target_header_pattern: str,
        title_threshold: float = 0.80,
        row_threshold: float = 0.80
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Determine if two tables should be merged.
        
        Merge conditions (ALL must be satisfied):
        1. Table Title: 80%+ fuzzy match on normalized title
        2. First Column (Row Labels): 80%+ Jaccard overlap
        3. Column Header Pattern: Must match period type format
        
        Period Type Formats:
        - Qn-YYYY → _1 suffix (point_in_time)
        - Qn-QTD-YYYY, Qn-YTD-YYYY → _2 suffix (period_based)
        - YTD-YYYY → _3 suffix (annual_ytd)
        
        Args:
            source_title: Title from source table
            target_title: Title from target table
            source_rows: First column values from source table
            target_rows: First column values from target table
            source_header_pattern: Header pattern from source (e.g., "L2_L3::CUMULATIVE")
            target_header_pattern: Header pattern from target
            title_threshold: Minimum title similarity (default 0.80)
            row_threshold: Minimum row overlap (default 0.80)
            
        Returns:
            Tuple of (should_merge, scores_dict)
            scores_dict contains title_similarity, row_overlap, pattern_match
        """
        scores = {
            'title_similarity': 0.0,
            'row_overlap': 0.0,
            'pattern_match': False
        }
        
        # 1. Check title similarity (80% threshold)
        title_similarity = cls.calculate_similarity(source_title, target_title)
        scores['title_similarity'] = title_similarity
        
        if title_similarity < title_threshold:
            return False, scores
        
        # 2. Check row label overlap (80% threshold)
        row_overlap, meets_row_threshold = cls.calculate_row_label_overlap(
            source_rows, target_rows, row_threshold
        )
        scores['row_overlap'] = row_overlap
        
        if not meets_row_threshold:
            return False, scores
        
        # 3. Check header pattern compatibility
        # Patterns must match exactly for merge
        # This ensures period types align (Qn-YYYY with Qn-YYYY, not with Qn-QTD-YYYY)
        pattern_match = source_header_pattern == target_header_pattern
        scores['pattern_match'] = pattern_match
        
        if not pattern_match:
            return False, scores
        
        return True, scores
