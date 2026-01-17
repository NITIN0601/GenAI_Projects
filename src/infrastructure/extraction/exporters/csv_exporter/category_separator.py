"""
Category Separator for CSV Tables.

Extracts category headers from CSV tables and associates line items with their parent categories.
Category headers are identified as rows with text in the first column but empty data columns.

Includes empty table detection and handling.
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


class EmptyTableAnalyzer:
    """Analyze why a table became empty after category separation."""
    
    @staticmethod
    def analyze(original_df: pd.DataFrame, processed_df: pd.DataFrame) -> Dict:
        """
        Analyze why a table became empty.
        
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "is_empty": len(processed_df) == 0,
            "original_rows": len(original_df),
            "processed_rows": len(processed_df),
            "reason": None,
            "category": None
        }
        
        if not analysis["is_empty"]:
            return analysis
        
        # Determine reason
        if len(original_df) == 0:
            analysis["reason"] = "Original table was empty"
            analysis["category"] = "empty_input"
        elif EmptyTableAnalyzer._is_metadata_only(original_df):
            analysis["reason"] = "Table contains only metadata/headers"
            analysis["category"] = "metadata_only"
        elif EmptyTableAnalyzer._is_all_categories(original_df):
            analysis["reason"] = "All rows identified as category headers"
            analysis["category"] = "all_headers"
        else:
            analysis["reason"] = "All rows filtered by category separation logic"
            analysis["category"] = "filtered_out"
        
        return analysis
    
    @staticmethod
    def _is_metadata_only(df: pd.DataFrame) -> bool:
        """Check if table is metadata-only (no actual data values)."""
        # Check if most cells are strings and no numeric data
        numeric_count = 0
        total_count = 0
        
        for col in df.columns:
            for val in df[col]:
                total_count += 1
                if pd.notna(val) and isinstance(val, (int, float)):
                    numeric_count += 1
        
        # If less than 5% numeric values, likely metadata-only
        return (numeric_count / max(total_count, 1)) < 0.05
    
    @staticmethod
    def _is_all_categories(df: pd.DataFrame) -> bool:
        """Check if all rows are category-like headers."""
        # Simple heuristic: first column has values but rest are mostly empty
        if len(df.columns) < 2:
            return False
        
        first_col_filled = df.iloc[:, 0].notna().sum()
        other_cols_filled = df.iloc[:, 1:].notna().sum().sum()
        
        return first_col_filled > 0 and other_cols_filled / max(first_col_filled * (len(df.columns) - 1), 1) < 0.1


class CategorySeparator:
    """
    Extracts categories from CSV tables and associates with line items.
    
    A row is considered a category header if:
    1. First column has text
    2. All subsequent columns are empty (or contain only dashes/whitespace)
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.empty_tables = []
        self.analyzer = EmptyTableAnalyzer()
    
    def separate_categories(self, df: pd.DataFrame, sheet_name: str = "") -> Tuple[Optional[pd.DataFrame], List[str]]:
        """
        Process a DataFrame to extract categories and associate them with line items.
        
        Args:
            df: Input DataFrame with raw table data
            sheet_name: Name of the sheet for logging/reporting
            
        Returns:
            Tuple of:
                - DataFrame with Category column added (or None if should be skipped)
                - List of unique categories found
        """
        if df.empty:
            self.logger.warning("Empty DataFrame provided")
            return df, []
        
        original_df = df.copy()
        
        result_rows = []
        current_category = ""
        categories_found = []
        
        # First row is the header
        header_row = df.iloc[0].tolist()
        
        for idx in range(1, len(df)):
            row = df.iloc[idx].tolist()
            
            # Skip empty rows (first column is empty/blank/NaN)
            if not row[0] or pd.isna(row[0]) or str(row[0]).strip() == '':
                continue
            
            
            if self.is_category_header(row, header_row):
                # This is a category header - update current category
                current_category = str(row[0]).strip()
                if current_category and current_category not in categories_found:
                    categories_found.append(current_category)
                self.logger.debug(f"Found category: '{current_category}'")
            else:
                # This is a data row - add with category
                row_dict = {
                    'Category': current_category,
                    'Product/Entity': str(row[0]).strip()
                }
                
                # Add period columns
                for i in range(1, len(header_row)):
                    row_dict[header_row[i]] = row[i] if i < len(row) else ''
                
                result_rows.append(row_dict)
        
        processed_df = pd.DataFrame(result_rows) if result_rows else pd.DataFrame()
        
        # Check if empty after processing
        if len(processed_df) == 0:
            analysis = self.analyzer.analyze(original_df, processed_df)
            self.empty_tables.append({
                "sheet_name": sheet_name,
                "analysis": analysis
            })
            
            self.logger.warning(
                f"Table {sheet_name} is empty after category separation. "
                f"Reason: {analysis['reason']}"
            )
            
            # Decide whether to skip or preserve
            if analysis["category"] in ["empty_input", "metadata_only"]:
                self.logger.info(f"Skipping export for {sheet_name} - {analysis['category']}")
                return None, categories_found  # Skip this table
            else:
                self.logger.warning(f"Exporting empty table {sheet_name} for review")
                return processed_df, categories_found  # Export for manual review
        
        if not result_rows:
            self.logger.warning("No data rows found after category separation")
            return pd.DataFrame(), categories_found
        
        self.logger.info(f"Separated {len(result_rows)} line items with {len(categories_found)} categories")
        
        return processed_df, categories_found
    
    def is_category_header(self, row: List, header_row: List) -> bool:
        """
        Determine if a row is a category header.
        
        A row is a category if:
        1. First column has text
        2. All subsequent columns are TRULY empty (not dashes - those are data)
        
        Args:
            row: The row to check (list of cell values)
            header_row: The header row for reference
        
        Returns:
            True if this is a category header row
        """
        # Skip if first column is NaN/None
        if not row[0] or pd.isna(row[0]):
            return False
        
        # First column must have text
        first_col = str(row[0]).strip()
        if not first_col:
            return False
        
        # Check if this might be repeated-header-text pattern first
        if self.is_repeated_header_category(row):
            return True
        
        # All subsequent columns must be TRULY empty (not dashes)
        # Dashes (-, $-, etc.) are VALID DATA VALUES representing zero/NA
        for i in range(1, len(row)):
            cell_value = str(row[i]).strip() if row[i] and not pd.isna(row[i]) else ''
            
            # If cell has any content at all (including dashes), it's NOT a category
            if cell_value:
                return False
        
        return True
    
    def is_repeated_header_category(self, row: List) -> bool:
        """
        Check if row has repeated text pattern (category name repeated across columns).
        
        Example:
            ['State and municipal securities', 'State and municipal securities', ...]
        
        Args:
            row: The row to check
        
        Returns:
            True if all non-empty values match the first column
        """
        first_col = str(row[0]).strip() if row[0] else ''
        if not first_col:
            return False
        
        # Check if all non-empty cells match the first column
        for i in range(1, len(row)):
            cell_value = str(row[i]).strip() if row[i] and not pd.isna(row[i]) else ''
            
            # Skip empty cells
            if not cell_value:
                continue
            
            # If any non-empty cell doesn't match, it's not repeated-header pattern
            if cell_value != first_col:
                return False
        
        # If we got here, all non-empty cells matched first column
        # Only return True if we found at least one non-empty match
        has_matches = any(
            str(row[i]).strip() == first_col 
            for i in range(1, len(row)) 
            if row[i] and not pd.isna(row[i]) and str(row[i]).strip()
        )
        
        return has_matches
    
    def generate_empty_tables_report(self) -> str:
        """Generate report of empty tables."""
        report = "# Empty Tables Report\n\n"
        report += f"**Total Empty Tables:** {len(self.empty_tables)}\n\n"
        
        if not self.empty_tables:
            report += "> [!SUCCESS]\n"
            report += "> No empty tables detected!\n\n"
            return report
        
        # Group by category
        by_category = {}
        for item in self.empty_tables:
            category = item["analysis"]["category"]
            by_category.setdefault(category, []).append(item)
        
        for category, items in by_category.items():
            report += f"## {category.replace('_', ' ').title()} ({len(items)} tables)\n\n"
            for item in items:
                report += f"- **{item['sheet_name']}**\n"
                report += f"  - Rows: {item['analysis']['original_rows']} → {item['analysis']['processed_rows']}\n"
                report += f"  - Reason: {item['analysis']['reason']}\n\n"
        
        report += "## Recommended Actions\n\n"
        report += "1. **metadata_only**: Review Index.csv to ensure metadata is captured\n"
        report += "2. **all_headers**: Verify original Excel structure; may need different parsing\n"
        report += "3. **filtered_out**: Review category detection logic for false positives\n\n"
        
        return report


def get_category_separator() -> CategorySeparator:
    """Factory function for CategorySeparator."""
    return CategorySeparator()
