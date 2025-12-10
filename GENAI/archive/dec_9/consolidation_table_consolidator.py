"""
Multi-year table consolidation and transpose for RAG queries.

This module handles:
1. Querying tables across multiple years with same title
2. Consolidating into single table with year columns
3. Transposing for better readability (rows ↔ columns)
4. Zero data loss/leakage

Example:
    Input: 5 separate tables (2020-2024) with same structure
    Output: 1 consolidated transposed table with years as columns

For quarterly/period consolidation, use QuarterlyTableConsolidator instead.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from collections import defaultdict
import logging
from src.utils import get_logger

logger = get_logger(__name__)


class MultiYearTableConsolidator:
    """
    Consolidates tables across multiple years and transposes for readability.
    
    Handles:
    - Multi-year consolidation
    - Consistent row header matching
    - Automatic transposition
    - Data integrity validation
    """
    
    def __init__(self):
        """Initialize table consolidator."""
        self.consolidated_tables = {}
    
    def consolidate_multi_year_tables(
        self,
        search_results: List[Dict[str, Any]],
        table_title: str
    ) -> Dict[str, Any]:
        """
        Consolidate tables from multiple years into single table.
        
        Args:
            search_results: Results from VectorDB search
            table_title: Title of table to consolidate
            
        Returns:
            Dictionary with consolidated and transposed table
        """
        # Step 1: Group by year
        tables_by_year = self._group_by_year(search_results, table_title)
        
        if not tables_by_year:
            return {"error": "No tables found for consolidation"}
        
        # Step 2: Extract data from each year
        data_by_year = {}
        for year, result in tables_by_year.items():
            data_by_year[year] = self._parse_table_content(result['content'])
        
        # Step 3: Consolidate into single structure
        consolidated = self._consolidate_data(tables_by_year, data_by_year)
        
        # Step 4: Transpose for readability
        transposed = self._transpose_table(consolidated)
        
        # Step 5: Validate data integrity
        validation = self._validate_consolidation(data_by_year, transposed)
        
        return {
            'table_title': table_title,
            'years': sorted(tables_by_year.keys()),
            'original_format': consolidated,
            'transposed_format': transposed,
            'validation': validation,
            'metadata': self._extract_metadata(search_results)
        }
    
    def _group_by_year(
        self,
        search_results: List[Dict[str, Any]],
        table_title: str
    ) -> Dict[int, Dict[str, Any]]:
        """Group search results by year for same table title."""
        tables_by_year = {}
        
        for result in search_results:
            metadata = result.get('metadata', {})
            
            # Check if table title matches
            # TODO: Add fuzzy matching here if needed for robustness
            if metadata.get('table_title', '').lower() == table_title.lower():
                year = metadata.get('year')
                
                if year and year not in tables_by_year:
                    tables_by_year[year] = result
        
        return tables_by_year
    
    def _parse_table_content(self, content: str) -> Dict[str, str]:
        """
        Parse table content into row_header: value mapping.
        Uses robust parsing to handle various markdown formats.
        
        Args:
            content: Markdown table content
            
        Returns:
            Dictionary mapping row headers to values
        """
        from src.utils.extraction_utils import CurrencyValueCleaner
        
        data = {}
        
        try:
            # First, clean currency values in the content
            cleaned_content = CurrencyValueCleaner.clean_table_rows(content)
            
            lines = [l.strip() for l in cleaned_content.split('\n') if l.strip()]
            
            # Filter out separator lines
            lines = [l for l in lines if not all(c in '|-: ' for c in l)]
            
            for line in lines:
                # Parse pipe-separated values
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    parts = [p for p in parts if p]  # Remove empty strings
                    
                    # Clean each cell value
                    parts = CurrencyValueCleaner.clean_currency_cells(parts)
                    
                    if len(parts) >= 2:
                        row_header = parts[0]
                        # Assume the last column is the value (common in financial tables)
                        # Or if 2 columns, it's index 1
                        value = parts[-1]
                        
                        # Skip header rows
                        if row_header and not self._is_header_row(row_header):
                            data[row_header] = value
                
                # Parse colon-separated values
                elif ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        row_header = parts[0].strip()
                        value = parts[1].strip()
                        data[row_header] = value
                        
        except Exception as e:
            logger.error(f"Error parsing table content: {e}")
            
        return data
    
    def _is_header_row(self, text: str) -> bool:
        """Check if row is a header row."""
        # Dynamic check: Header rows usually have generic terms
        header_keywords = ['table', 'year', 'period', 'column', 'header', 'item', 'description', 'ended']
        text_lower = text.lower()
        
        # Exact match or starts with keyword
        for keyword in header_keywords:
            if text_lower == keyword or text_lower.startswith(f"{keyword} "):
                return True
                
        return False
    
    def _consolidate_data(
        self,
        tables_by_year: Dict[int, Dict[str, Any]],
        data_by_year: Dict[int, Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Consolidate data from multiple years.
        """
        # Collect all unique row headers
        all_row_headers = set()
        for year_data in data_by_year.values():
            all_row_headers.update(year_data.keys())
        
        # Sort row headers (maintain consistent order)
        row_headers = sorted(all_row_headers)
        years = sorted(data_by_year.keys())
        
        # Build consolidated data structure
        consolidated_data = {}
        for row_header in row_headers:
            consolidated_data[row_header] = {}
            for year in years:
                value = data_by_year[year].get(row_header, 'N/A')
                
                # Use precise date if available from metadata
                metadata = tables_by_year[year].get('metadata', {})
                date_key = self._get_period_date(year, metadata.get('quarter'))
                
                consolidated_data[row_header][date_key] = value
        
        return {
            'row_headers': row_headers,
            'years': years,
            'data': consolidated_data
        }
    
    def _get_period_date(self, year: Optional[int], quarter: Optional[str]) -> str:
        """
        Get standard period end date for quarter.
        """
        if not year:
            return "Unknown"
            
        if not quarter:
            return f"{year}-12-31"  # Default to year end
            
        quarter = quarter.upper()
        
        if "Q1" in quarter:
            return f"{year}-03-31"
        elif "Q2" in quarter:
            return f"{year}-06-30"
        elif "Q3" in quarter:
            return f"{year}-09-30"
        elif "Q4" in quarter or "10-K" in quarter or "10K" in quarter:
            return f"{year}-12-31"
        else:
            return f"{year}-12-31"  # Default
    
    def _transpose_table(
        self,
        consolidated: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transpose table for better readability.
        """
        row_headers = consolidated['row_headers']
        
        # Get all unique date keys from the data
        all_dates = set()
        for row_data in consolidated['data'].values():
            all_dates.update(row_data.keys())
        dates = sorted(all_dates)
        
        data = consolidated['data']
        
        # Build transposed structure
        transposed_data = {}
        for date_key in dates:
            transposed_data[date_key] = {}
            for row_header in row_headers:
                value = data[row_header].get(date_key, 'N/A')
                transposed_data[date_key][row_header] = value
        
        return {
            'column_headers': row_headers,  # Original row headers become columns
            'row_headers': dates,  # Dates become rows
            'data': transposed_data
        }
    
    def _validate_consolidation(
        self,
        original_data: Dict[int, Dict[str, str]],
        transposed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate data integrity - no loss or leakage.
        """
        validation = {
            'status': 'valid',
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        # Count original data points
        original_count = sum(len(data) for data in original_data.values())
        
        # Count transposed data points
        transposed_count = sum(
            len(year_data) for year_data in transposed['data'].values()
        )
        
        validation['stats']['original_data_points'] = original_count
        validation['stats']['transposed_data_points'] = transposed_count
        
        # Check for data loss
        if transposed_count < original_count:
            validation['status'] = 'warning'
            validation['warnings'].append(
                f"Data loss detected: {original_count - transposed_count} points missing"
            )
        
        # Check for data leakage (extra data)
        if transposed_count > original_count:
            validation['status'] = 'warning'
            validation['warnings'].append(
                f"Data leakage detected: {transposed_count - original_count} extra points"
            )
        
        return validation
    
    def _extract_metadata(
        self,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract common metadata from search results."""
        if not search_results:
            return {}
        
        first_result = search_results[0].get('metadata', {})
        
        return {
            'company_ticker': first_result.get('company_ticker'),
            'company_name': first_result.get('company_name'),
            'statement_type': first_result.get('statement_type'),
            'units': first_result.get('units'),
            'currency': first_result.get('currency')
        }
    
    def format_as_dataframe(
        self,
        consolidated_result: Dict[str, Any],
        use_transposed: bool = True
    ) -> pd.DataFrame:
        """
        Format consolidated result as pandas DataFrame.
        """
        if use_transposed:
            # Transposed format: Years as rows, line items as columns
            data = consolidated_result['transposed_format']['data']
            df = pd.DataFrame(data).T
            df.index.name = 'Year'
        else:
            # Original format: Line items as rows, years as columns
            data = consolidated_result['original_format']['data']
            df = pd.DataFrame(data).T
            df.index.name = 'Line Item'
        
        return df
    
    def format_as_markdown(
        self,
        consolidated_result: Dict[str, Any],
        use_transposed: bool = True
    ) -> str:
        """
        Format consolidated result as markdown table.
        """
        df = self.format_as_dataframe(consolidated_result, use_transposed)
        
        # Add metadata header
        metadata = consolidated_result.get('metadata', {})
        header = f"# {consolidated_result['table_title']}\n\n"
        
        if metadata.get('company_name'):
            header += f"**Company**: {metadata['company_name']}\n"
        if metadata.get('units'):
            header += f"**Units**: {metadata['units']}\n"
        if metadata.get('currency'):
            header += f"**Currency**: {metadata['currency']}\n"
        
        header += f"\n**Years**: {', '.join(map(str, consolidated_result['years']))}\n\n"
        
        # Convert DataFrame to markdown
        markdown_table = df.to_markdown()
        
        return header + markdown_table


# Global instance
_multi_year_consolidator: Optional[MultiYearTableConsolidator] = None


def get_multi_year_consolidator() -> MultiYearTableConsolidator:
    """Get or create global multi-year table consolidator instance."""
    global _multi_year_consolidator
    if _multi_year_consolidator is None:
        _multi_year_consolidator = MultiYearTableConsolidator()
    return _multi_year_consolidator


# Backward compatibility alias
get_table_consolidator = get_multi_year_consolidator


def consolidate_and_transpose(
    search_results: List[Dict[str, Any]],
    table_title: str,
    format: str = 'dataframe'
) -> Any:
    """
    Convenience function to consolidate and transpose tables.
    """
    consolidator = get_multi_year_consolidator()
    result = consolidator.consolidate_multi_year_tables(search_results, table_title)
    
    if format == 'dataframe':
        return consolidator.format_as_dataframe(result, use_transposed=True)
    elif format == 'markdown':
        return consolidator.format_as_markdown(result, use_transposed=True)
    else:
        return result
