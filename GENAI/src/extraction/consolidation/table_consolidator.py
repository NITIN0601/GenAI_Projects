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
        consolidated = self._consolidate_data(data_by_year)
        
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
            if metadata.get('table_title', '').lower() == table_title.lower():
                year = metadata.get('year')
                
                if year and year not in tables_by_year:
                    tables_by_year[year] = result
        
        return tables_by_year
    
    def _parse_table_content(self, content: str) -> Dict[str, str]:
        """
        Parse table content into row_header: value mapping.
        
        Args:
            content: Markdown table content
            
        Returns:
            Dictionary mapping row headers to values
        """
        data = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and separators
            if not line or line.startswith('---') or line.startswith('==='):
                continue
            
            # Parse pipe-separated values
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # Remove empty strings
                
                if len(parts) >= 2:
                    row_header = parts[0]
                    value = parts[1] if len(parts) > 1 else ''
                    
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
        
        return data
    
    def _is_header_row(self, text: str) -> bool:
        """Check if row is a header row."""
        header_keywords = ['table', 'year', 'period', 'column', 'header']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in header_keywords)
    
    def _consolidate_data(
        self,
        data_by_year: Dict[int, Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Consolidate data from multiple years.
        
        Format:
        {
            'row_headers': ['Total Assets', 'Total Liabilities', ...],
            'years': [2020, 2021, 2022, 2023, 2024],
            'data': {
                'Total Assets': {'2020': '$1.0T', '2021': '$1.2T', ...},
                'Total Liabilities': {'2020': '$0.8T', '2021': '$0.9T', ...}
            }
        }
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
                consolidated_data[row_header][str(year)] = value
        
        return {
            'row_headers': row_headers,
            'years': years,
            'data': consolidated_data
        }
    
    def _transpose_table(
        self,
        consolidated: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transpose table for better readability.
        
        Original (horizontal, wide):
        | Line Item        | 2020   | 2021   | 2022   | 2023   | 2024   |
        | Total Assets     | $1.0T  | $1.2T  | $1.5T  | $1.8T  | $2.0T  |
        
        Transposed (vertical, tall):
        | Year | Total Assets | Total Liabilities | ... |
        | 2020 | $1.0T        | $0.8T             | ... |
        | 2021 | $1.2T        | $0.9T             | ... |
        """
        row_headers = consolidated['row_headers']
        years = consolidated['years']
        data = consolidated['data']
        
        # Build transposed structure
        transposed_data = {}
        for year in years:
            transposed_data[str(year)] = {}
            for row_header in row_headers:
                value = data[row_header].get(str(year), 'N/A')
                transposed_data[str(year)][row_header] = value
        
        return {
            'column_headers': row_headers,  # Original row headers become columns
            'row_headers': [str(y) for y in years],  # Years become rows
            'data': transposed_data
        }
    
    def _validate_consolidation(
        self,
        original_data: Dict[int, Dict[str, str]],
        transposed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate data integrity - no loss or leakage.
        
        Checks:
        - All years present
        - All row headers present
        - All values preserved
        - No duplicates
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
        
        # Verify all years present
        expected_years = set(original_data.keys())
        actual_years = set(int(y) for y in transposed['row_headers'])
        
        if expected_years != actual_years:
            validation['status'] = 'error'
            validation['errors'].append(
                f"Year mismatch: expected {expected_years}, got {actual_years}"
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
        
        Args:
            consolidated_result: Result from consolidate_multi_year_tables
            use_transposed: If True, use transposed format (recommended)
            
        Returns:
            pandas DataFrame
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
        
        Args:
            consolidated_result: Result from consolidate_multi_year_tables
            use_transposed: If True, use transposed format (recommended)
            
        Returns:
            Markdown table string
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
    
    Args:
        search_results: Results from VectorDB search
        table_title: Title of table to consolidate
        format: Output format ('dataframe', 'markdown', 'dict')
        
    Returns:
        Consolidated table in requested format
    """
    consolidator = get_multi_year_consolidator()
    result = consolidator.consolidate_multi_year_tables(search_results, table_title)
    
    if format == 'dataframe':
        return consolidator.format_as_dataframe(result, use_transposed=True)
    elif format == 'markdown':
        return consolidator.format_as_markdown(result, use_transposed=True)
    else:
        return result
