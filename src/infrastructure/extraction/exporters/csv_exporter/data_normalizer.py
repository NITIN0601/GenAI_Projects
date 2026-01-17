"""
Data Normalizer - Transforms CSV data from wide to long format.

Converts period header columns (e.g., Q3-QTD-2025, Q3-2025 IS) into:
- Dates: The period identifier (e.g., Q3-QTD-2025, Q3-2025)
- Header: The suffix after the period (e.g., IS, WM, or empty)
- Data Value: The cell value

This transformation unpivots data from wide format to long format,
making it easier to analyze and query period-based data.
"""

import re
from typing import List, Tuple, Optional
import pandas as pd
from src.utils import get_logger

logger = get_logger(__name__)


class DataNormalizer:
    """
    Transforms CSV data from wide format to long format.
    
    Wide format:
        Source, Section, Table Title, Category, Product/Entity, Q3-QTD-2025, Q3-2025 IS, Q3-2025 WM
        
    Long format:
        Source, Section, Table Title, Category, Product/Entity, Dates, Header, Data Value
    """
    
    # Period patterns for known date formats
    PERIOD_PATTERNS = [
        r'^(Q[1-4]-QTD-\d{4})',         # Q3-QTD-2025
        r'^(Q[1-4]-YTD-\d{4})',         # Q3-YTD-2025
        r'^(Q[1-4]-\d{4})',              # Q3-2025
        r'^(YTD-\d{4})',                 # YTD-2024
    ]
    
    # Unit indicator headers to exclude from transformation
    UNIT_INDICATORS = {
        '$ in millions',
        '$ in billions',
        'in millions',
        'in billions',
        '$ (in thousands)',
        'in thousands',
    }
    
    # Fixed columns that should not be transformed
    FIXED_COLUMNS = [
        'Source',
        'Section',
        'Table Title',
        'Category',
        'Product/Entity',
    ]
    
    def __init__(self):
        """Initialize the Data Normalizer."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        # Compile regex patterns for efficiency
        self.period_regex = re.compile('|'.join(self.PERIOD_PATTERNS))
    
    def normalize_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform a DataFrame from wide format to long format.
        
        Args:
            df: DataFrame in wide format with period columns
            
        Returns:
            DataFrame in long format with Dates, Header, and Data Value columns
        """
        if df.empty:
            self.logger.debug("Empty DataFrame, skipping normalization")
            return df
        
        # Identify fixed columns and period columns
        fixed_cols, period_cols = self._identify_columns(df)
        
        if not period_cols:
            self.logger.debug("No period columns found, skipping normalization")
            return df
        
        self.logger.debug(
            f"Normalizing {len(df)} rows with {len(fixed_cols)} fixed columns "
            f"and {len(period_cols)} period columns"
        )
        
        # Transform to long format
        normalized_df = self._transform_to_long_format(df, fixed_cols, period_cols)
        
        self.logger.debug(
            f"Normalized to {len(normalized_df)} rows "
            f"(expansion factor: {len(normalized_df) / len(df):.1f}x)"
        )
        
        return normalized_df
    
    def _identify_columns(self, df: pd.DataFrame) -> Tuple[List[str], List[str]]:
        """
        Identify which columns are fixed and which are period columns.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Tuple of (fixed_columns, period_columns)
        """
        fixed_cols = []
        period_cols = []
        
        for col in df.columns:
            col_str = str(col).strip()
            
            # Check if it's a fixed column
            if col_str in self.FIXED_COLUMNS:
                fixed_cols.append(col)
            # Check if it's a unit indicator (exclude these)
            elif col_str in self.UNIT_INDICATORS:
                self.logger.debug(f"Excluding unit indicator column: {col_str}")
                continue
            else:
                # Treat as period column
                period_cols.append(col)
        
        return fixed_cols, period_cols
    
    def _transform_to_long_format(
        self, 
        df: pd.DataFrame, 
        fixed_cols: List[str], 
        period_cols: List[str]
    ) -> pd.DataFrame:
        """
        Transform DataFrame from wide to long format.
        
        Args:
            df: Original DataFrame
            fixed_cols: Columns to keep as-is
            period_cols: Columns to transform
            
        Returns:
            Transformed DataFrame in long format
        """
        # Create list to collect normalized rows
        normalized_rows = []
        
        # Process each row in the original DataFrame
        for _, row in df.iterrows():
            # For each period column, create a new row
            for period_col in period_cols:
                # Parse the period column header
                dates, header = self._parse_period_header(str(period_col))
                
                # Get the data value
                data_value = row[period_col]
                
                # Build new row with fixed columns + new columns
                new_row = {}
                
                # Copy fixed column values
                for fixed_col in fixed_cols:
                    new_row[fixed_col] = row[fixed_col]
                
                # Add new columns
                new_row['Dates'] = dates
                new_row['Header'] = header
                new_row['Data Value'] = data_value
                
                normalized_rows.append(new_row)
        
        # Create new DataFrame
        if not normalized_rows:
            return pd.DataFrame()
        
        normalized_df = pd.DataFrame(normalized_rows)
        
        # Ensure column order: fixed columns + Dates + Header + Data Value
        column_order = fixed_cols + ['Dates', 'Header', 'Data Value']
        normalized_df = normalized_df[column_order]
        
        return normalized_df
    
    def _parse_period_header(self, header: str) -> Tuple[str, str]:
        """
        Parse a period header into Dates and Header components.
        
        Examples:
            'Q3-QTD-2025'        -> ('Q3-QTD-2025', '')
            'Q3-2025 IS'         -> ('Q3-2025', 'IS')
            'Q3-2025 WM'         -> ('Q3-2025', 'WM')
            'YTD-2024 Trading'   -> ('YTD-2024', 'Trading')
            'MS/PF'              -> ('MS/PF', '')  # Non-period header
        
        Args:
            header: Original column header
            
        Returns:
            Tuple of (dates, header_suffix)
        """
        header = header.strip()
        
        # Try to match known period patterns
        match = self.period_regex.match(header)
        
        if match:
            # Extract the period portion - find the first non-None group
            period = None
            for i in range(1, len(match.groups()) + 1):
                if match.group(i) is not None:
                    period = match.group(i)
                    break
            
            if period is None:
                # Fallback to entire match
                period = match.group(0)
            
            # Get the remaining text after the period
            remaining = header[len(period):].strip()
            
            return (period, remaining)
        else:
            # Not a recognized period pattern
            # Put entire header in Dates, leave Header empty
            return (header, '')
    
    def validate_normalized_output(self, original_df: pd.DataFrame, normalized_df: pd.DataFrame) -> bool:
        """
        Validate that normalization was successful.
        
        Checks:
        - Row count is correct (original_rows * period_columns)
        - Required columns exist
        - No unexpected data loss
        
        Args:
            original_df: Original wide format DataFrame
            normalized_df: Normalized long format DataFrame
            
        Returns:
            True if validation passes, False otherwise
        """
        if original_df.empty:
            return normalized_df.empty
        
        # Identify period columns in original
        fixed_cols, period_cols = self._identify_columns(original_df)
        
        if not period_cols:
            # No transformation should have occurred
            return original_df.equals(normalized_df)
        
        # Check row count
        expected_rows = len(original_df) * len(period_cols)
        actual_rows = len(normalized_df)
        
        if expected_rows != actual_rows:
            self.logger.error(
                f"Row count mismatch: expected {expected_rows}, got {actual_rows}"
            )
            return False
        
        # Check required columns exist
        required_cols = set(fixed_cols + ['Dates', 'Header', 'Data Value'])
        actual_cols = set(normalized_df.columns)
        
        if required_cols != actual_cols:
            self.logger.error(
                f"Column mismatch: expected {required_cols}, got {actual_cols}"
            )
            return False
        
        self.logger.debug("Normalization validation passed")
        return True


def normalize_csv_file(input_path: str, output_path: Optional[str] = None) -> bool:
    """
    Normalize a CSV file from wide to long format.
    
    Args:
        input_path: Path to input CSV file
        output_path: Optional path to output CSV file (defaults to in-place)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read CSV
        df = pd.read_csv(input_path)
        
        # Normalize
        normalizer = DataNormalizer()
        normalized_df = normalizer.normalize_table(df)
        
        # Validate
        if not normalizer.validate_normalized_output(df, normalized_df):
            logger.error(f"Validation failed for {input_path}")
            return False
        
        # Write output
        output = output_path or input_path
        normalized_df.to_csv(output, index=False)
        
        logger.info(f"Normalized {input_path} -> {output}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to normalize {input_path}: {e}", exc_info=True)
        return False
