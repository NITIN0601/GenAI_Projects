"""
Metadata Builder for Excel Export.

Provides a centralized, modular way to build metadata rows for Excel exports.
Used by: excel_exporter.py, table_merger.py, consolidated_exporter.py

This ensures consistent metadata structure across all pipeline steps.
"""

import re
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

# Import from focused modules (no duplication)
from src.utils.metadata_labels import MetadataLabels, TableMetadata
from src.utils.quarter_mapper import QuarterDateMapper
from src.utils.header_parser import MultiLevelHeaderParser



class MetadataBuilder:


    """
    Builds standardized metadata for Excel exports.
    
    Metadata Structure (12 rows):
        Row 1:  ← Back to Index
        Row 2:  Category (Parent): [section headers]
        Row 3:  Line Items: [data row labels]
        Row 4:  Product/Entity: [unique entities]
        Row 5:  [Column Header L1] - per column (blank if no L1)
        Row 6:  [Column Header L2] - per column (blank if no L2)
        Row 7:  [Column Header L3] - per column (always present)
        Row 8:  Year/Quarter: [QTD3,2024 | QTD6,2023 | YTD,2024]
        Row 9:  [blank]
        Row 10: Table Title: [title]
        Row 11: Sources: [sources]
        Row 12: [blank]
        Row 13+: [Data]
    
    Usage:
        builder = MetadataBuilder()
        metadata = TableMetadata(
            category_parent=["Revenues", "Expenses"],
            line_items=["Investment Banking", "Trading"],
            ...
        )
        frames = builder.build_metadata_frames(metadata, result_df)
        final_df = pd.concat(frames + [result_df], ignore_index=True)
    """
    
    # Period type patterns for Year/Quarter detection
    PERIOD_PATTERNS = {
        'QTD9': ['nine months', '9 months'],
        'QTD6': ['six months', '6 months'],
        'QTD3': ['three months', '3 months'],
        'YTD': ['year ended', 'fiscal year', 'annual'],
    }
    
    # Month to quarter mapping
    MONTH_TO_QUARTER = {
        'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
        'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
        'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
        'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
    }
    
    # Patterns that indicate start of period type in compound headers
    PERIOD_START_PATTERNS = [
        'three months ended', 'six months ended', 'nine months ended',
        'year ended', 'fiscal year ended',
        'at march', 'at june', 'at september', 'at december',
        'at january', 'at february', 'at april', 'at may',
        'at july', 'at august', 'at october', 'at november',
        'as of march', 'as of june', 'as of september', 'as of december',
    ]
    
    @classmethod
    def split_compound_header(cls, header: str) -> dict:
        """
        Split compound column headers into L1 (main header) and L2 (period type).
        
        Example:
            Input: "Average Monthly Balance Three Months Ended March 31,"
            Output: {
                'l1': 'Average Monthly Balance',
                'l2': 'Three Months Ended March 31,',
                'original': 'Average Monthly Balance Three Months Ended March 31,'
            }
            
        If no split is possible, returns:
            {'l1': '', 'l2': header, 'original': header}
        
        Args:
            header: Column header string to split
            
        Returns:
            Dict with 'l1' (main header), 'l2' (period type), 'original' keys
        """
        if not header:
            return {'l1': '', 'l2': '', 'original': ''}
        
        header_lower = header.lower()
        
        # Try to find where period type starts
        for pattern in cls.PERIOD_START_PATTERNS:
            idx = header_lower.find(pattern)
            if idx > 0:  # Pattern found and not at start
                l1 = header[:idx].strip()
                l2 = header[idx:].strip()
                # Capitalize first letter of L2
                if l2:
                    l2 = l2[0].upper() + l2[1:] if len(l2) > 1 else l2.upper()
                return {
                    'l1': l1,
                    'l2': l2,
                    'original': header
                }
        
        # No split possible - treat as L2 only
        return {'l1': '', 'l2': header, 'original': header}
    
    @classmethod
    def build_year_quarter_value(
        cls,
        period_type_header: str,
        year_header: str,
        source: str = ""
    ) -> str:
        """
        Build Year/Quarter value from period type and year headers.
        
        Uses QuarterDateMapper for standardized format.
        
        Args:
            period_type_header: Column Header L2 value (e.g., "Three Months Ended June 30,")
            year_header: Column Header L3 value (e.g., "2024", "December 31, 2024")
            source: Source filename for 10-K detection
            
        Returns:
            Standardized format: "Q2-QTD-2024", "Q2-YTD-2024", "Q2-2024", "YTD-2024"
        """
        l2_str = str(period_type_header).strip() if period_type_header else ''
        l3_str = str(year_header).strip() if year_header else ''
        
        # Combine L2 (period type) and L3 (date/year) for parsing
        # e.g., "Three Months Ended June 30," + "2024" = "Three Months Ended June 30, 2024"
        combined = f"{l2_str} {l3_str}".strip()
        
        if not combined:
            return ''
        
        # Use QuarterDateMapper for standardized conversion
        code = QuarterDateMapper.display_to_code(combined, source)
        
        return code
    
    @classmethod
    def get_period_type(cls, header: str) -> str:
        """
        Detect period type from column header.
        
        Returns one of: 'QUARTERLY', 'QTD3', 'QTD6', 'QTD9', 'YTD', 'UNKNOWN'
        """
        header_lower = header.lower() if header else ''
        
        if 'nine months' in header_lower or '9 months' in header_lower:
            return 'QTD9'
        if 'six months' in header_lower or '6 months' in header_lower:
            return 'QTD6'
        if 'three months' in header_lower or '3 months' in header_lower:
            return 'QTD3'
        if 'year ended' in header_lower or 'fiscal year' in header_lower:
            return 'YTD'
        
        # Check for At/As of dates (point-in-time = quarterly)
        if re.match(r'^at\s+', header_lower) or re.match(r'^as of\s+', header_lower):
            return 'QUARTERLY'
        
        # Year only (likely from 10-K)
        if re.match(r'^20\d{2}$', header.strip() if header else ''):
            return 'YTD'
        
        return 'UNKNOWN'
    
    @classmethod
    def convert_to_qn_format(cls, header: str, period_type: Optional[str] = None, use_separator: bool = False) -> str:
        """
        Convert column header to standardized quarter code format.
        
        Uses QuarterDateMapper for consistent conversion.
        
        Args:
            header: Column header string
            period_type: Optional period type (auto-detected if not provided)
            use_separator: If True, output 'Q1-QTD-2025'; if False, same format
        
        Format Rules (NEW):
            - At/As of dates → Q1-2025, Q2-2025, Q3-2025, Q4-2025
            - Three Months Ended → Q1-QTD-2025, Q2-QTD-2025
            - Six Months Ended → Q2-YTD-2025
            - Nine Months Ended → Q3-YTD-2025
            - Year Ended → YTD-2025
        
        Examples:
            'At March 31, 2025' → 'Q1-2025'
            'Three Months Ended March 31, 2025' → 'Q1-QTD-2025'
            'Six Months Ended June 30, 2024' → 'Q2-YTD-2024'
        """
        if not header:
            return header
        
        # Use QuarterDateMapper for standardized conversion
        code = QuarterDateMapper.display_to_code(str(header))
        
        return code if code else header
    
    @classmethod
    def build_metadata_dataframe(
        cls,
        metadata: TableMetadata,
        columns: List[str],
        first_col: str = 'Row Label'
    ) -> pd.DataFrame:
        """
        Build complete metadata DataFrame (all 12 rows with simple summaries in column A).
        
        Structure:
            Row 1:  ← Back to Index
            Row 2:  Category (Parent): ...
            Row 3:  Line Items: ...
            Row 4:  Product/Entity: ...
            Row 5:  Column Header L1: ... (summary)
            Row 6:  Column Header L2: ... (summary)
            Row 7:  Column Header L3: ... (summary)
            Row 8:  Year/Quarter: ...
            Row 9:  [blank]
            Row 10: Table Title: ...
            Row 11: Sources: ...
            Row 12: [blank]
        
        Args:
            metadata: TableMetadata object with all metadata values
            columns: List of column names for the result DataFrame
            first_col: Name of the first column (default: 'Row Label')
            
        Returns:
            DataFrame with 12 metadata rows
        """
        rows = []
        
        # Row 1: Back link
        rows.append({first_col: MetadataLabels.BACK_LINK})
        
        # Row 2: Category (Parent) - with title case
        category_items = [c.title() for c in metadata.category_parent[:5]] if metadata.category_parent else []
        category_str = ', '.join(category_items)
        rows.append({first_col: f"{MetadataLabels.CATEGORY_PARENT} {category_str}"})
        
        # Row 3: Line Items - with title case
        line_items = [li.title() for li in metadata.line_items[:10]] if metadata.line_items else []
        line_items_str = ', '.join(line_items)
        rows.append({first_col: f"{MetadataLabels.LINE_ITEMS} {line_items_str}"})
        
        # Row 4: Product/Entity - with title case
        products = [p.title() for p in metadata.product_entity[:5]] if metadata.product_entity else []
        product_str = ', '.join(products)
        rows.append({first_col: f"{MetadataLabels.PRODUCT_ENTITY} {product_str}"})
        
        # Row 5: Column Header L1 (summary of unique values)
        l1_unique = sorted(set(h for h in metadata.column_header_l1 if h))
        l1_str = ', '.join(l1_unique) if l1_unique else ''
        rows.append({first_col: f"{MetadataLabels.COLUMN_HEADER_L1} {l1_str}"})
        
        # Row 6: Column Header L2 (summary of unique values)
        l2_unique = sorted(set(h for h in metadata.column_header_l2 if h))
        l2_str = ', '.join(l2_unique) if l2_unique else ''
        rows.append({first_col: f"{MetadataLabels.COLUMN_HEADER_L2} {l2_str}"})
        
        # Row 7: Column Header L3 (summary of unique values)
        l3_unique = sorted(set(h for h in metadata.column_header_l3 if h))
        l3_str = ', '.join(l3_unique) if l3_unique else ''
        rows.append({first_col: f"{MetadataLabels.COLUMN_HEADER_L3} {l3_str}"})
        
        # Row 8: Year/Quarter (derived from L2 + L3)
        # Only include valid date codes (Qn-YYYY, YTD-YYYY, Qn-QTD-YYYY, Qn-YTD-YYYY)
        valid_yq_pattern = re.compile(r'^(Q[1-4](-QTD|-YTD)?|YTD)-20\d{2}$', re.IGNORECASE)
        year_quarter_values = []
        for i, (l2_val, l3_val) in enumerate(zip(metadata.column_header_l2, metadata.column_header_l3)):
            if i > 0:  # Skip first column
                yq = cls.build_year_quarter_value(l2_val, l3_val, metadata.sources[0] if metadata.sources else '')
                # Only include if it looks like a valid date code
                if yq and valid_yq_pattern.match(yq) and yq not in year_quarter_values:
                    year_quarter_values.append(yq)
        yq_str = ', '.join(year_quarter_values) if year_quarter_values else ''
        rows.append({first_col: f"{MetadataLabels.YEAR_QUARTER} {yq_str}"})
        
        # Row 9: Blank
        rows.append({first_col: ''})
        
        # Row 10: Table Title
        title = metadata.table_title
        if metadata.section:
            title = f"{metadata.section} - {title}"
        rows.append({first_col: f"{MetadataLabels.TABLE_TITLE} {title}"})
        
        # Row 11: Sources (deduplicated)
        unique_sources = sorted(set(s for s in metadata.sources if s)) if metadata.sources else []
        sources_str = ', '.join(unique_sources)
        rows.append({first_col: f"{MetadataLabels.SOURCES} {sources_str}"})
        
        # Row 12: Blank
        rows.append({first_col: ''})
        
        # Create DataFrame and align columns
        df = pd.DataFrame(rows)
        
        # Add all missing columns at once to avoid fragmentation
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            missing_df = pd.DataFrame('', index=df.index, columns=missing_cols)
            df = pd.concat([df, missing_df], axis=1)
        df = df[columns]

        
        return df
    
    @classmethod
    def build_remaining_metadata_dataframe(
        cls,
        metadata: TableMetadata,
        columns: List[str],
        first_col: str = 'Row Label'
    ) -> pd.DataFrame:
        """
        Build remaining metadata DataFrame (rows 9-12).
        
        Args:
            metadata: TableMetadata object
            columns: List of column names
            first_col: Name of the first column
            
        Returns:
            DataFrame with rows 9-12 (blank, title, sources, blank)
        """
        rows = []
        
        # Row 9: Blank
        rows.append({first_col: ''})
        
        # Row 10: Table Title
        title = metadata.table_title
        if metadata.section:
            title = f"{metadata.section} - {title}"
        rows.append({first_col: f"Table Title: {title}"})
        
        # Row 11: Sources
        sources_str = ', '.join(metadata.sources) if metadata.sources else ''
        rows.append({first_col: f"Sources: {sources_str}"})
        
        # Row 12: Blank
        rows.append({first_col: ''})
        
        # Create DataFrame and align columns
        df = pd.DataFrame(rows)
        
        # Add all missing columns at once to avoid fragmentation
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            missing_df = pd.DataFrame('', index=df.index, columns=missing_cols)
            df = pd.concat([df, missing_df], axis=1)
        df = df[columns]

        
        return df
    
    @classmethod
    def build_column_header_dataframe(
        cls,
        header_values: List[str],
        columns: List[str]
    ) -> pd.DataFrame:
        """
        Build a single column header row DataFrame.
        
        Args:
            header_values: List of header values (one per column)
            columns: List of column names
            
        Returns:
            DataFrame with a single row of header values
        """
        # Ensure header values align with columns
        while len(header_values) < len(columns):
            header_values.append('')
        header_values = header_values[:len(columns)]
        
        return pd.DataFrame([header_values], columns=columns, dtype=str)
    
    @classmethod
    def build_year_quarter_dataframe(
        cls,
        l1_headers: List[str],
        l2_headers: List[str],
        columns: List[str],
        sources: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Build Year/Quarter row DataFrame.
        
        Args:
            l1_headers: Column Header L2 values (Period Type)
            l2_headers: Column Header L3 values (Years/Dates)
            columns: List of column names
            sources: Optional list of source filenames (for 10-K detection)
            
        Returns:
            DataFrame with Year/Quarter row
        """
        values = []
        source = sources[0] if sources else ''
        
        for idx in range(len(columns)):
            if idx == 0:
                values.append(MetadataLabels.YEAR_QUARTER)
            elif idx < len(l1_headers) and idx < len(l2_headers):
                yq = cls.build_year_quarter_value(l1_headers[idx], l2_headers[idx], source)
                values.append(yq)
            else:
                values.append('')
        
        return pd.DataFrame([values], columns=columns, dtype=str)
    
    @classmethod
    def build_all_metadata_frames(
        cls,
        metadata: TableMetadata,
        columns: List[str],
        first_col: str = 'Row Label'
    ) -> List[pd.DataFrame]:
        """
        Build all metadata frames in order (rows 1-12).
        
        Returns list of DataFrames that can be concatenated with data:
        [metadata_df, l1_df, l2_df, l3_df, year_quarter_df, remaining_df]
        
        Usage:
            frames = MetadataBuilder.build_all_metadata_frames(metadata, columns)
            final_df = pd.concat(frames + [result_df], ignore_index=True)
        """
        # Rows 1-4: Basic metadata
        metadata_df = cls.build_metadata_dataframe(metadata, columns, first_col)
        
        # Rows 5-7: Column headers
        l1_df = cls.build_column_header_dataframe(metadata.column_header_l1, columns)
        l2_df = cls.build_column_header_dataframe(metadata.column_header_l2, columns)
        l3_df = cls.build_column_header_dataframe(metadata.column_header_l3, columns)
        
        # Row 8: Year/Quarter
        year_quarter_df = cls.build_year_quarter_dataframe(
            metadata.column_header_l2,
            metadata.column_header_l3,
            columns,
            metadata.sources
        )
        
        # Rows 9-12: Remaining metadata
        remaining_df = cls.build_remaining_metadata_dataframe(metadata, columns, first_col)
        
        return [metadata_df, l1_df, l2_df, l3_df, year_quarter_df, remaining_df]
    
    # =========================================================================
    # METADATA EXTRACTION (from existing Excel cells/rows)
    # =========================================================================
    
    @classmethod
    def extract_metadata_from_cell(cls, cell_value: str) -> Dict[str, Set[str]]:
        """
        Extract metadata values from a single cell string.
        
        Args:
            cell_value: Cell content like "Period Type: Q1 2024, Q2 2024"
            
        Returns:
            Dict with keys: 'period_type', 'years', 'sources', 'main_header'
        """
        metadata = {
            'period_type': set(),
            'years': set(),
            'sources': set(),
            'main_header': set(),
        }
        
        if not cell_value:
            return metadata
        
        cell_str = str(cell_value).strip()
        
        # Column Header L2 (Period Type)
        if cell_str.startswith(MetadataLabels.COLUMN_HEADER_L2) or cell_str.startswith('Period Type:'):
            values = cell_str.split(':', 1)[1].strip()
            for v in values.split(','):
                v = v.strip()
                if v:
                    metadata['period_type'].add(v)
        
        # Column Header L3 (Year(s))
        elif cell_str.startswith(MetadataLabels.COLUMN_HEADER_L3) or cell_str.startswith('Year(s):') or cell_str.startswith('Years:'):
            values = cell_str.split(':', 1)[1].strip()
            for v in values.split(','):
                v = v.strip()
                if v and re.match(r'^20\d{2}$', v):
                    metadata['years'].add(v)
        
        # Sources
        elif cell_str.startswith(MetadataLabels.SOURCES) or cell_str.startswith('Source:') or cell_str.startswith('Sources:'):
            values = cell_str.split(':', 1)[1].strip()
            for v in values.split(','):
                v = v.strip()
                if v:
                    metadata['sources'].add(v)
        
        # Column Header L1 (Main Header)
        elif cell_str.startswith(MetadataLabels.COLUMN_HEADER_L1) or cell_str.startswith('Main Header:'):
            values = cell_str.split(':', 1)[1].strip()
            for v in values.split(','):
                v = v.strip()
                if v:
                    metadata['main_header'].add(v)
        
        return metadata
    
    @classmethod
    def merge_metadata_sets(cls, *metadata_dicts) -> Dict[str, Set[str]]:
        """
        Merge multiple metadata dictionaries into one.
        
        Args:
            *metadata_dicts: Variable number of metadata dicts
            
        Returns:
            Combined metadata dict with all unique values
        """
        combined = {
            'period_type': set(),
            'years': set(),
            'sources': set(),
            'main_header': set(),
        }
        
        for md in metadata_dicts:
            if md:
                combined['period_type'].update(md.get('period_type', set()))
                combined['years'].update(md.get('years', set()))
                combined['sources'].update(md.get('sources', set()))
                combined['main_header'].update(md.get('main_header', set()))
        
        return combined
    
    @classmethod
    def format_merged_metadata(cls, combined: Dict[str, Set[str]]) -> Dict[str, str]:
        """
        Format merged metadata sets into display strings.
        
        Args:
            combined: Dict with sets of values
            
        Returns:
            Dict with formatted strings for each metadata type
        """
        # Sort main_header chronologically by date embedded in header
        # e.g. "At June 30, 2024" should sort after "At December 31, 2023"
        sorted_main_headers = cls._sort_headers_chronologically(list(combined['main_header']))
        
        return {
            'period_type': ', '.join(sorted(combined['period_type'])),
            'years': ', '.join(sorted(combined['years'], reverse=True)),
            'sources': ', '.join(sorted(combined['sources'])),
            'main_header': ', '.join(sorted_main_headers),
        }
    
    @classmethod
    def _sort_headers_chronologically(cls, headers: List[str]) -> List[str]:
        """
        Sort header strings chronologically by the date embedded in them.
        
        Uses year and month to determine order.
        e.g., "At December 31, 2023" < "At March 31, 2024" < "At June 30, 2024"
        
        Args:
            headers: List of header strings
            
        Returns:
            Headers sorted chronologically (oldest first)
        """
        
        # Month name to number mapping
        MONTH_TO_NUM = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        }
        
        def extract_date_key(header: str) -> tuple:
            """Extract (year, month) tuple for sorting."""
            if not header:
                return (0, 0, header)
            
            header_lower = header.lower()
            
            # Extract year
            year_match = re.search(r'20(\d{2})', header)
            year = int(year_match.group(0)) if year_match else 0
            
            # Extract month
            month = 0
            for month_name, month_num in MONTH_TO_NUM.items():
                if month_name in header_lower:
                    month = month_num
                    break
            
            # Return tuple (year, month, original header for stable sort)
            return (year, month, header)
        
        return [h for _, _, h in sorted([extract_date_key(h) for h in headers])]
    
    @classmethod
    def extract_year_from_header(cls, header: str) -> str:
        """
        Extract year (20XX) from column header.
        
        Examples:
            'Three Months Ended March 31, 2024' -> '2024'
            'At June 30, 2023' -> '2023'
            '2024' -> '2024'
        """
        if not header:
            return ''
        match = re.search(r'(20\d{2})', str(header))
        return match.group(1) if match else ''
    
    @classmethod
    def extract_quarter_from_header(cls, header: str) -> str:
        """
        Extract quarter designation from column header.
        
        Uses QuarterDateMapper for standardized format.
        
        Format (NEW):
            - At/As of dates -> Q1, Q2, Q3, Q4
            - Three Months Ended -> Q1-QTD, Q2-QTD, etc. (returns just period part)
            - Six Months Ended -> Q2-YTD (returns just period part)
            - Nine Months Ended -> Q3-YTD (returns just period part)
            - Year Ended / standalone year -> YTD
        
        Examples:
            'At March 31, 2025' -> 'Q1'
            'Three Months Ended June 30, 2024' -> 'Q2-QTD'
            'Six Months Ended June 30, 2024' -> 'Q2-YTD'
            'Year Ended December 31, 2024' -> 'YTD'
        """
        if not header:
            return ''
        
        # Use QuarterDateMapper for conversion
        code = QuarterDateMapper.display_to_code(str(header))
        
        if not code:
            return ''
        
        # Remove year from code to get just the period part
        # e.g., 'Q2-QTD-2024' -> 'Q2-QTD', 'Q1-2024' -> 'Q1', 'YTD-2024' -> 'YTD'
        parts = code.split('-')
        if len(parts) >= 2 and parts[-1].isdigit():
            return '-'.join(parts[:-1])
        
        return code

