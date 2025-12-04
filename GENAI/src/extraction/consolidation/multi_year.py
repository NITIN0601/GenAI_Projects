"""
Table consolidation engine for merging results from multiple PDFs.
Handles different scenarios: same table/different periods, same period/different docs, cross-table queries.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime
import pandas as pd
from dateutil import parser


class TableConsolidationEngine:
    """
    Consolidates tables from multiple PDFs into single response table.
    Handles various consolidation scenarios.
    """
    
    def consolidate_same_table_different_periods(
        self,
        results: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Scenario A: Same table type, different periods.
        
        Example:
            Doc 1: Income Statement Q1 2025
            Doc 2: Income Statement Q4 2024
            Doc 3: Income Statement Q3 2024
        
        Output: Single table with columns: Row Label | Q3 2024 | Q4 2024 | Q1 2025
        
        Args:
            results: List of search results with metadata
        
        Returns:
            Consolidated DataFrame
        """
        # Group by canonical_label (row)
        rows_data = defaultdict(dict)
        all_periods = set()
        
        for result in results:
            metadata = result.get("metadata", {})
            canonical_label = metadata.get("canonical_label")
            row_label = metadata.get("row_label", canonical_label)
            period_label = metadata.get("period_label")
            value_display = metadata.get("value_display")
            value_numeric = metadata.get("value_numeric")
            
            if canonical_label and period_label:
                rows_data[canonical_label]["label"] = row_label
                rows_data[canonical_label][period_label] = {
                    "display": value_display,
                    "numeric": value_numeric
                }
                all_periods.add(period_label)
        
        # Sort periods chronologically
        sorted_periods = self._sort_periods(list(all_periods))
        
        # Build DataFrame
        data = []
        for canonical_label, row_info in sorted(rows_data.items()):
            row = {"Row Label": row_info.get("label", canonical_label)}
            for period in sorted_periods:
                period_data = row_info.get(period, {})
                row[period] = period_data.get("display", "—")
            data.append(row)
        
        df = pd.DataFrame(data)
        return df
    
    def consolidate_same_period_different_docs(
        self,
        results: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Scenario B: Same table type, same period, different documents.
        
        Example:
            Doc 1: Income Statement Q1 2025 (Morgan Stanley)
            Doc 2: Income Statement Q1 2025 (Goldman Sachs)
        
        Output: Side-by-side comparison table
        
        Args:
            results: List of search results
        
        Returns:
            Consolidated DataFrame with company columns
        """
        # Group by canonical_label and company
        rows_data = defaultdict(dict)
        all_companies = set()
        period_label = None
        
        for result in results:
            metadata = result.get("metadata", {})
            canonical_label = metadata.get("canonical_label")
            row_label = metadata.get("row_label", canonical_label)
            company = metadata.get("company", "Unknown")
            value_display = metadata.get("value_display")
            period = metadata.get("period_label")
            
            if not period_label:
                period_label = period
            
            if canonical_label:
                rows_data[canonical_label]["label"] = row_label
                rows_data[canonical_label][company] = value_display
                all_companies.add(company)
        
        # Build DataFrame
        data = []
        for canonical_label, row_info in sorted(rows_data.items()):
            row = {"Row Label": row_info.get("label", canonical_label)}
            for company in sorted(all_companies):
                col_name = f"{company} {period_label}" if period_label else company
                row[col_name] = row_info.get(company, "—")
            data.append(row)
        
        df = pd.DataFrame(data)
        return df
    
    def consolidate_cross_table(
        self,
        results_by_table: Dict[str, List[Dict[str, Any]]]
    ) -> pd.DataFrame:
        """
        Scenario C: Different table types.
        
        Example:
            Request: "Show net income from income statement and total assets from balance sheet"
        
        Output: Combined table with mixed sources
        
        Args:
            results_by_table: Dict mapping table_type to results
        
        Returns:
            Consolidated DataFrame
        """
        # Collect all rows with their sources
        rows_data = []
        all_periods = set()
        
        for table_type, results in results_by_table.items():
            for result in results:
                metadata = result.get("metadata", {})
                canonical_label = metadata.get("canonical_label")
                row_label = metadata.get("row_label", canonical_label)
                period_label = metadata.get("period_label")
                value_display = metadata.get("value_display")
                table_title = metadata.get("table_title", table_type)
                
                if canonical_label:
                    # Find existing row or create new
                    existing_row = next(
                        (r for r in rows_data if r["canonical_label"] == canonical_label),
                        None
                    )
                    
                    if not existing_row:
                        existing_row = {
                            "canonical_label": canonical_label,
                            "Metric": row_label,
                            "Source": table_title,
                            "periods": {}
                        }
                        rows_data.append(existing_row)
                    
                    if period_label:
                        existing_row["periods"][period_label] = value_display
                        all_periods.add(period_label)
        
        # Sort periods
        sorted_periods = self._sort_periods(list(all_periods))
        
        # Build DataFrame
        data = []
        for row_info in rows_data:
            row = {
                "Metric": row_info["Metric"],
                "Source": row_info["Source"]
            }
            for period in sorted_periods:
                row[period] = row_info["periods"].get(period, "—")
            data.append(row)
        
        df = pd.DataFrame(data)
        return df
    
    def consolidate_hierarchical(
        self,
        results: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Consolidate hierarchical query results.
        Shows parent and child rows with indentation.
        
        Args:
            results: List of search results
        
        Returns:
            DataFrame with hierarchy preserved
        """
        # Group by period
        periods_data = defaultdict(list)
        all_periods = set()
        
        for result in results:
            metadata = result.get("metadata", {})
            row_label = metadata.get("row_label")
            indent_level = metadata.get("indent_level", 0)
            period_label = metadata.get("period_label")
            value_display = metadata.get("value_display")
            parent_row = metadata.get("parent_row")
            is_subtotal = metadata.get("is_subtotal", False)
            is_total = metadata.get("is_total", False)
            
            if row_label:
                periods_data[period_label].append({
                    "row_label": row_label,
                    "indent_level": indent_level,
                    "value": value_display,
                    "parent": parent_row,
                    "is_subtotal": is_subtotal,
                    "is_total": is_total
                })
                all_periods.add(period_label)
        
        # Sort periods
        sorted_periods = self._sort_periods(list(all_periods))
        
        # Build hierarchical structure
        data = []
        for period in sorted_periods:
            rows = periods_data.get(period, [])
            # Sort by hierarchy (parents before children)
            rows.sort(key=lambda x: (x.get("parent", ""), x["indent_level"]))
            
            for row_info in rows:
                indent = "  " * row_info["indent_level"]
                label = indent + row_info["row_label"]
                
                # Mark subtotals and totals
                if row_info["is_total"]:
                    label = f"**{label}**"
                elif row_info["is_subtotal"]:
                    label = f"*{label}*"
                
                data.append({
                    "Item": label,
                    period: row_info["value"]
                })
        
        df = pd.DataFrame(data)
        return df
    
    def _sort_periods(self, periods: List[str]) -> List[str]:
        """Sort periods chronologically."""
        def parse_period(period_str):
            try:
                # Try to parse as date
                return parser.parse(period_str)
            except Exception:
                # Try to extract year and quarter
                import re
                quarter_match = re.search(r'Q([1-4])\s*(\d{4})', period_str, re.IGNORECASE)
                if quarter_match:
                    quarter = int(quarter_match.group(1))
                    year = int(quarter_match.group(2))
                    # Convert to date (first day of quarter)
                    month = (quarter - 1) * 3 + 1
                    return datetime(year, month, 1)
                
                # Try year only
                year_match = re.search(r'\b(20\d{2})\b', period_str)
                if year_match:
                    return datetime(int(year_match.group(1)), 1, 1)
                
                return period_str
        
        return sorted(periods, key=parse_period)
    
    def calculate_changes(
        self,
        df: pd.DataFrame,
        periods: List[str]
    ) -> pd.DataFrame:
        """
        Calculate period-over-period changes.
        
        Args:
            df: DataFrame with period columns
            periods: List of period column names
        
        Returns:
            DataFrame with additional change columns
        """
        if len(periods) < 2:
            return df
        
        # Add change columns between consecutive periods
        for i in range(len(periods) - 1):
            current_period = periods[i + 1]
            prior_period = periods[i]
            change_col = f"Change ({prior_period} to {current_period})"
            pct_change_col = f"% Change"
            
            # Calculate changes (requires numeric conversion)
            # This is simplified - would need proper numeric parsing
            df[change_col] = "—"
            df[pct_change_col] = "—"
        
        return df


# Singleton instance
_consolidation_engine = None

def get_consolidation_engine() -> TableConsolidationEngine:
    """Get singleton consolidation engine."""
    global _consolidation_engine
    if _consolidation_engine is None:
        _consolidation_engine = TableConsolidationEngine()
    return _consolidation_engine
