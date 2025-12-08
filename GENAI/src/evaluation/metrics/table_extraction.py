"""
Table Extraction Quality Metrics.

Evaluates the quality of extracted tabular data:
- Structure completeness (headers, rows, columns)
- Cell quality (empty cells, formatting)
- Numeric accuracy (currency, percentages, numbers)
- Metadata completeness
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging
from src.utils import get_logger
import re
from statistics import mean

logger = get_logger(__name__)


@dataclass
class TableQualityMetrics:
    """Container for table extraction quality metrics."""
    
    # Structure metrics
    structure_score: float = 0.0  # 0-1: header/row/col structure
    cell_completeness: float = 0.0  # 0-1: non-empty cells ratio
    column_consistency: float = 0.0  # 0-1: consistent column count
    
    # Content metrics
    numeric_accuracy: float = 0.0  # 0-1: properly formatted numbers
    header_quality: float = 0.0  # 0-1: quality of headers
    content_quality: float = 0.0  # 0-1: overall content quality
    
    # Metadata metrics
    metadata_completeness: float = 0.0  # 0-1: required metadata present
    
    # Overall score
    overall_score: float = 0.0  # 0-100: weighted average
    
    # Additional info
    tables_evaluated: int = 0
    total_cells: int = 0
    empty_cells: int = 0
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "structure_score": round(self.structure_score, 3),
            "cell_completeness": round(self.cell_completeness, 3),
            "column_consistency": round(self.column_consistency, 3),
            "numeric_accuracy": round(self.numeric_accuracy, 3),
            "header_quality": round(self.header_quality, 3),
            "content_quality": round(self.content_quality, 3),
            "metadata_completeness": round(self.metadata_completeness, 3),
            "overall_score": round(self.overall_score, 1),
            "tables_evaluated": self.tables_evaluated,
            "total_cells": self.total_cells,
            "empty_cells": self.empty_cells,
            "issues": self.issues,
        }


class TableExtractionEvaluator:
    """
    Evaluate quality of extracted tabular data.
    
    Focuses on:
    - Table structure integrity
    - Cell content quality
    - Numeric/financial data accuracy
    - Metadata completeness
    
    Best for:
    - Validating extraction quality
    - Comparing extraction backends
    - Quality assurance for financial tables
    """
    
    # Required metadata fields for financial tables
    REQUIRED_METADATA = [
        'source_doc', 'page_no', 'table_title', 
        'year', 'quarter', 'report_type'
    ]
    
    # Financial number patterns
    CURRENCY_PATTERN = re.compile(r'^\$?[\d,]+\.?\d*$|^\([\d,]+\.?\d*\)$')
    PERCENTAGE_PATTERN = re.compile(r'^-?[\d.]+%$')
    NUMBER_PATTERN = re.compile(r'^-?[\d,]+\.?\d*$')
    
    def __init__(
        self,
        min_rows: int = 2,
        min_columns: int = 2,
        max_empty_ratio: float = 0.3,
    ):
        """
        Initialize table extraction evaluator.
        
        Args:
            min_rows: Minimum rows for valid table
            min_columns: Minimum columns for valid table
            max_empty_ratio: Maximum acceptable empty cell ratio
        """
        self.min_rows = min_rows
        self.min_columns = min_columns
        self.max_empty_ratio = max_empty_ratio
    
    def evaluate(
        self,
        tables: List[Dict[str, Any]],
        ground_truth: Optional[List[Dict[str, Any]]] = None,
    ) -> TableQualityMetrics:
        """
        Evaluate extraction quality for a set of tables.
        
        Args:
            tables: List of extracted tables (each with 'content' and 'metadata')
            ground_truth: Optional ground truth for comparison
            
        Returns:
            TableQualityMetrics with all computed metrics
        """
        metrics = TableQualityMetrics()
        
        if not tables:
            metrics.issues.append("No tables to evaluate")
            return metrics
        
        metrics.tables_evaluated = len(tables)
        
        # Collect scores per table
        structure_scores = []
        cell_completeness_scores = []
        column_consistency_scores = []
        numeric_accuracy_scores = []
        header_quality_scores = []
        content_quality_scores = []
        metadata_scores = []
        
        total_cells = 0
        empty_cells = 0
        
        for i, table in enumerate(tables):
            try:
                content = table.get('content', '')
                metadata = table.get('metadata', {})
                
                # Parse table content
                rows = self._parse_markdown_table(content)
                
                if not rows:
                    metrics.issues.append(f"Table {i+1}: Could not parse content")
                    continue
                
                # Compute per-table metrics
                struct_score, issues = self._compute_structure_score(rows)
                structure_scores.append(struct_score)
                metrics.issues.extend([f"Table {i+1}: {issue}" for issue in issues])
                
                # Cell completeness
                cells, empty = self._count_cells(rows)
                total_cells += cells
                empty_cells += empty
                cell_completeness_scores.append(1 - (empty / max(cells, 1)))
                
                # Column consistency
                col_score = self._compute_column_consistency(rows)
                column_consistency_scores.append(col_score)
                
                # Numeric accuracy
                num_score = self._compute_numeric_accuracy(rows)
                numeric_accuracy_scores.append(num_score)
                
                # Header quality
                header_score = self._evaluate_header(rows)
                header_quality_scores.append(header_score)
                
                # Content quality
                content_score = self._compute_content_quality(rows)
                content_quality_scores.append(content_score)
                
                # Metadata completeness
                meta_score = self._compute_metadata_completeness(metadata)
                metadata_scores.append(meta_score)
                
            except Exception as e:
                logger.error(f"Error evaluating table {i+1}: {e}")
                metrics.issues.append(f"Table {i+1}: Evaluation error - {e}")
        
        # Aggregate scores
        metrics.structure_score = mean(structure_scores) if structure_scores else 0
        metrics.cell_completeness = mean(cell_completeness_scores) if cell_completeness_scores else 0
        metrics.column_consistency = mean(column_consistency_scores) if column_consistency_scores else 0
        metrics.numeric_accuracy = mean(numeric_accuracy_scores) if numeric_accuracy_scores else 0
        metrics.header_quality = mean(header_quality_scores) if header_quality_scores else 0
        metrics.content_quality = mean(content_quality_scores) if content_quality_scores else 0
        metrics.metadata_completeness = mean(metadata_scores) if metadata_scores else 0
        
        metrics.total_cells = total_cells
        metrics.empty_cells = empty_cells
        
        # Compute weighted overall score (0-100)
        weights = {
            'structure': 0.20,
            'cell_completeness': 0.15,
            'column_consistency': 0.10,
            'numeric_accuracy': 0.20,
            'header_quality': 0.10,
            'content_quality': 0.15,
            'metadata': 0.10,
        }
        
        metrics.overall_score = (
            metrics.structure_score * weights['structure'] +
            metrics.cell_completeness * weights['cell_completeness'] +
            metrics.column_consistency * weights['column_consistency'] +
            metrics.numeric_accuracy * weights['numeric_accuracy'] +
            metrics.header_quality * weights['header_quality'] +
            metrics.content_quality * weights['content_quality'] +
            metrics.metadata_completeness * weights['metadata']
        ) * 100
        
        return metrics
    
    def _parse_markdown_table(self, content: str) -> List[List[str]]:
        """Parse markdown table into rows and cells."""
        rows = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('|---') or line.startswith('| ---'):
                continue  # Skip separator lines
            
            if '|' in line:
                # Remove leading/trailing pipes and split
                cells = [c.strip() for c in line.strip('|').split('|')]
                rows.append(cells)
        
        return rows
    
    def _compute_structure_score(self, rows: List[List[str]]) -> tuple:
        """Compute structure quality score."""
        issues = []
        score = 1.0
        
        # Check minimum rows
        if len(rows) < self.min_rows:
            issues.append(f"Too few rows ({len(rows)} < {self.min_rows})")
            score -= 0.3
        
        # Check minimum columns
        if rows:
            max_cols = max(len(row) for row in rows)
            if max_cols < self.min_columns:
                issues.append(f"Too few columns ({max_cols} < {self.min_columns})")
                score -= 0.3
        
        # Check for header row
        if rows and not self._looks_like_header(rows[0]):
            issues.append("First row may not be a header")
            score -= 0.2
        
        return max(0, score), issues
    
    def _count_cells(self, rows: List[List[str]]) -> tuple:
        """Count total and empty cells."""
        total = sum(len(row) for row in rows)
        empty = sum(1 for row in rows for cell in row if not cell.strip())
        return total, empty
    
    def _compute_column_consistency(self, rows: List[List[str]]) -> float:
        """Check if column count is consistent across rows."""
        if not rows:
            return 0
        
        col_counts = [len(row) for row in rows]
        most_common = max(set(col_counts), key=col_counts.count)
        consistent = sum(1 for c in col_counts if c == most_common)
        
        return consistent / len(col_counts)
    
    def _compute_numeric_accuracy(self, rows: List[List[str]]) -> float:
        """Evaluate quality of numeric/financial values."""
        if len(rows) < 2:
            return 0
        
        data_rows = rows[1:]  # Skip header
        numeric_cells = 0
        valid_numeric = 0
        
        for row in data_rows:
            for cell in row[1:]:  # Skip first column (usually labels)
                cell = cell.strip()
                if not cell or cell == '-' or cell.lower() == 'n/a':
                    continue
                
                # Check if looks numeric
                if any(c.isdigit() for c in cell):
                    numeric_cells += 1
                    
                    # Check if properly formatted
                    if (self.CURRENCY_PATTERN.match(cell) or 
                        self.PERCENTAGE_PATTERN.match(cell) or
                        self.NUMBER_PATTERN.match(cell)):
                        valid_numeric += 1
        
        return valid_numeric / max(numeric_cells, 1)
    
    def _looks_like_header(self, row: List[str]) -> bool:
        """Check if row looks like a header."""
        if not row:
            return False
        
        # Headers typically have text, not numbers
        numeric_count = sum(1 for cell in row if any(c.isdigit() for c in cell))
        text_count = len(row) - numeric_count
        
        return text_count >= len(row) * 0.5
    
    def _evaluate_header(self, rows: List[List[str]]) -> float:
        """Evaluate header quality."""
        if not rows:
            return 0
        
        header = rows[0]
        score = 1.0
        
        # Check for empty header cells
        empty_headers = sum(1 for cell in header if not cell.strip())
        if empty_headers > 0:
            score -= 0.1 * empty_headers
        
        # Check for numeric values in header (usually bad)
        numeric_headers = sum(1 for cell in header 
                             if cell.strip() and cell.strip()[0].isdigit())
        if numeric_headers > 0:
            score -= 0.1 * numeric_headers
        
        # Check header length (too short = unclear)
        short_headers = sum(1 for cell in header if 0 < len(cell.strip()) < 2)
        if short_headers > 0:
            score -= 0.1 * short_headers
        
        return max(0, score)
    
    def _compute_content_quality(self, rows: List[List[str]]) -> float:
        """Compute overall content quality."""
        if len(rows) < 2:
            return 0
        
        score = 1.0
        
        # Check for garbled text (multiple special characters)
        garbled_cells = 0
        total_cells = 0
        
        for row in rows:
            for cell in row:
                total_cells += 1
                special_ratio = sum(1 for c in cell if not c.isalnum() and c not in ' .,%-$()') / max(len(cell), 1)
                if special_ratio > 0.3:
                    garbled_cells += 1
        
        if total_cells > 0:
            garbled_ratio = garbled_cells / total_cells
            score -= garbled_ratio
        
        return max(0, score)
    
    def _compute_metadata_completeness(self, metadata: Dict[str, Any]) -> float:
        """Check if required metadata fields are present."""
        if not metadata:
            return 0
        
        present = sum(1 for field in self.REQUIRED_METADATA 
                     if field in metadata and metadata[field] is not None)
        
        return present / len(self.REQUIRED_METADATA)
    
    def compare_backends(
        self,
        results: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, TableQualityMetrics]:
        """
        Compare extraction quality across different backends.
        
        Args:
            results: Dict mapping backend name to extracted tables
            
        Returns:
            Dict mapping backend name to quality metrics
        """
        comparison = {}
        
        for backend_name, tables in results.items():
            metrics = self.evaluate(tables)
            comparison[backend_name] = metrics
            
            logger.info(
                f"{backend_name}: Overall={metrics.overall_score:.1f}, "
                f"Structure={metrics.structure_score:.2f}, "
                f"Numeric={metrics.numeric_accuracy:.2f}"
            )
        
        return comparison


# Global instance
_table_evaluator: Optional[TableExtractionEvaluator] = None


def get_table_evaluator() -> TableExtractionEvaluator:
    """Get or create global table extraction evaluator."""
    global _table_evaluator
    if _table_evaluator is None:
        _table_evaluator = TableExtractionEvaluator()
    return _table_evaluator
