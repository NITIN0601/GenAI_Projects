"""
Quality assessment for extraction results.
"""

from typing import List, Dict, Any
import re
from src.infrastructure.extraction.base import ExtractionResult


class QualityAssessor:
    """Assess extraction quality with multiple metrics."""
    
    # Scoring constants for table count assessment
    SCORE_NO_TABLES = 0.0
    SCORE_FEW_TABLES = 10.0      # 1-2 tables
    SCORE_MODERATE_TABLES = 15.0  # 3-5 tables
    SCORE_MANY_TABLES = 20.0      # 6+ tables
    
    # Scoring constants for structure assessment
    SCORE_HEADERS_DETECTED = 15.0
    SCORE_CONSISTENT_STRUCTURE = 10.0
    
    # Scoring constants for text quality
    SCORE_TEXT_GARBLED = 5.0
    SCORE_TEXT_GOOD = 10.0
    SCORE_TEXT_EXCELLENT = 15.0
    
    def __init__(self):
        self.weights = {
            'table_count': 0.20,      # 20 points
            'cell_completeness': 0.30,  # 30 points
            'structure': 0.25,          # 25 points
            'text_quality': 0.15,       # 15 points
            'backend_confidence': 0.10  # 10 points
        }
    
    def assess(self, result: ExtractionResult) -> float:
        """
        Calculate overall quality score (0-100).
        
        Args:
            result: Extraction result to assess
            
        Returns:
            Quality score from 0-100
        """
        if not result.is_successful():
            return 0.0
        
        # Get base confidence from backend type (not from result.quality_score to avoid circular dependency)
        backend_confidence = self._get_backend_confidence(result.backend)
        
        scores = {
            'table_count': self._assess_table_count(result),
            'cell_completeness': self._assess_cell_completeness(result),
            'structure': self._assess_structure(result),
            'text_quality': self._assess_text_quality(result),
            'backend_confidence': backend_confidence
        }
        
        # Weighted sum
        total_score = sum(
            scores[metric] * weight
            for metric, weight in self.weights.items()
        )
        
        # Update result with detailed scores
        result.table_count = len(result.tables)
        result.cell_completeness = scores['cell_completeness']
        result.structure_score = scores['structure']
        
        return min(total_score, 100.0)
    
    def _get_backend_confidence(self, backend) -> float:
        """
        Get base confidence score for a backend type.
        
        Returns confidence score out of 10 (weight is 0.10).
        """
        from src.infrastructure.extraction.base import BackendType
        
        confidence_map = {
            BackendType.DOCLING: 10.0,      # Highest confidence
            BackendType.PYMUPDF: 8.0,
            BackendType.PDFPLUMBER: 7.0,
            BackendType.CAMELOT: 6.0,
            BackendType.UNSTRUCTURED: 7.0,
        }
        return confidence_map.get(backend, 5.0)
    
    def _assess_table_count(self, result: ExtractionResult) -> float:
        """
        Assess based on number of tables found.
        
        Scoring:
        - 0 tables: 0 points
        - 1-2 tables: 10 points
        - 3-5 tables: 15 points
        - 6+ tables: 20 points
        """
        count = len(result.tables)
        if count == 0:
            return self.SCORE_NO_TABLES
        elif count <= 2:
            return self.SCORE_FEW_TABLES
        elif count <= 5:
            return self.SCORE_MODERATE_TABLES
        else:
            return self.SCORE_MANY_TABLES
    
    def _assess_cell_completeness(self, result: ExtractionResult) -> float:
        """
        Assess based on percentage of non-empty cells.
        
        Returns score 0-30 based on fill rate.
        """
        if not result.tables:
            return 0.0
        
        total_cells = 0
        filled_cells = 0
        
        for table in result.tables:
            cells = self._count_cells(table)
            filled = self._count_filled_cells(table)
            total_cells += cells
            filled_cells += filled
        
        if total_cells == 0:
            return 0.0
        
        fill_rate = filled_cells / total_cells
        return fill_rate * 30.0
    
    def _assess_structure(self, result: ExtractionResult) -> float:
        """
        Assess table structure quality.
        
        Checks:
        - Headers detected (15 points)
        - Consistent column count (10 points)
        """
        if not result.tables:
            return 0.0
        
        score = 0.0
        
        # Check for headers
        if self._has_headers(result.tables):
            score += self.SCORE_HEADERS_DETECTED
        
        # Check structure consistency
        if self._has_consistent_structure(result.tables):
            score += self.SCORE_CONSISTENT_STRUCTURE
        
        return score
    
    def _assess_text_quality(self, result: ExtractionResult) -> float:
        """
        Assess text quality (no garbled text, proper encoding).
        
        Returns 0-15 points.
        """
        if not result.tables:
            return 0.0
        
        # Check for garbled text
        if self._has_garbled_text(result.tables):
            return self.SCORE_TEXT_GARBLED  # Penalize but don't zero out
        
        # Check for proper numeric formatting
        if self._has_proper_numbers(result.tables):
            return self.SCORE_TEXT_EXCELLENT
        
        return self.SCORE_TEXT_GOOD
    
    def _count_cells(self, table: Dict[str, Any]) -> int:
        """Count total cells in table."""
        if 'content' in table and isinstance(table['content'], str):
            # Markdown table - count cells
            lines = [l for l in table['content'].split('\n') if '|' in l and '---' not in l]
            return sum(len([c for c in line.split('|') if c.strip()]) for line in lines)
        return 0
    
    def _count_filled_cells(self, table: Dict[str, Any]) -> int:
        """Count non-empty cells in table."""
        if 'content' in table and isinstance(table['content'], str):
            lines = [l for l in table['content'].split('\n') if '|' in l and '---' not in l]
            filled = 0
            for line in lines:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                filled += sum(1 for c in cells if c and c not in ['-', '—', 'N/A', 'n/a'])
            return filled
        return 0
    
    def _has_headers(self, tables: List[Dict[str, Any]]) -> bool:
        """Check if tables have headers."""
        for table in tables:
            if 'content' in table:
                content = table['content']
                # Look for separator line (|---|---|)
                if '---' in content or '===' in content:
                    return True
        return False
    
    def _has_consistent_structure(self, tables: List[Dict[str, Any]]) -> bool:
        """Check if tables have consistent column counts."""
        for table in tables:
            if 'content' in table:
                lines = [l for l in table['content'].split('\n') if '|' in l and '---' not in l]
                if len(lines) < 2:
                    continue
                
                col_counts = [len([c for c in line.split('|') if c.strip()]) for line in lines]
                # Check if all rows have same column count
                if len(set(col_counts)) > 2:  # Allow some variation
                    return False
        
        return True
    
    def _has_garbled_text(self, tables: List[Dict[str, Any]]) -> bool:
        """Check for garbled or corrupted text."""
        garbled_patterns = [
            r'[^\x00-\x7F]{5,}',  # Long sequences of non-ASCII
            r'(\?{3,})',          # Multiple question marks
            r'(�{2,})',           # Replacement characters
        ]
        
        for table in tables:
            if 'content' in table:
                content = table['content']
                for pattern in garbled_patterns:
                    if re.search(pattern, content):
                        return True
        
        return False
    
    def _has_proper_numbers(self, tables: List[Dict[str, Any]]) -> bool:
        """Check if numeric values are properly formatted."""
        for table in tables:
            if 'content' in table:
                content = table['content']
                # Look for numeric patterns
                if re.search(r'\d{1,3}(,\d{3})*(\.\d+)?', content):
                    return True
                if re.search(r'\$\s*\d+', content):
                    return True
        
        return False
    
    def get_quality_grade(self, score: float) -> str:
        """
        Get quality grade from score.
        
        Grades:
        - Excellent: 90-100
        - Good: 75-89
        - Fair: 60-74
        - Poor: 0-59
        """
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        else:
            return "Poor"
