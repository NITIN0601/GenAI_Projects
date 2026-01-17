"""
CSV Writer Utilities.

Handles CSV file writing with proper encoding, escaping, and formatting.
Ensures Excel compatibility and data integrity.
"""

from pathlib import Path
from typing import Optional, Union

import pandas as pd

from src.utils import get_logger
from .constants import CSVExportSettings

logger = get_logger(__name__)


class CSVWriter:
    """
    Handles CSV file writing with proper formatting.
    
    Features:
    - UTF-8 with BOM for Excel compatibility
    - Proper escaping of special characters
    - Consistent handling of NaN/None values
    - Configurable quoting style
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.encoding = CSVExportSettings.ENCODING
    
    def write_table_csv(
        self,
        df: pd.DataFrame,
        output_path: Path,
        include_header: bool = False  # Default False: first data row IS the header
    ) -> bool:
        """
        Write table data to CSV.
        
        Args:
            df: DataFrame containing table data
            output_path: Path to write CSV file
            include_header: Whether to include column headers
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Clean data before writing
            clean_df = self._clean_dataframe(df)
            
            # Write to CSV
            clean_df.to_csv(
                output_path,
                index=False,
                header=include_header,
                encoding=self.encoding,
                lineterminator=CSVExportSettings.LINE_TERMINATOR,
                na_rep='',
            )
            
            self.logger.debug(f"Wrote {len(clean_df)} rows to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write CSV {output_path}: {e}")
            return False
    
    def write_index_csv(
        self,
        df: pd.DataFrame,
        output_path: Path
    ) -> bool:
        """
        Write enhanced Index to CSV.
        
        Args:
            df: Enhanced Index DataFrame
            output_path: Path to write CSV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Clean data
            clean_df = self._clean_dataframe(df)
            
            # Write to CSV with all columns
            clean_df.to_csv(
                output_path,
                index=False,
                header=True,
                encoding=self.encoding,
                lineterminator=CSVExportSettings.LINE_TERMINATOR,
                na_rep='',
            )
            
            self.logger.info(f"Wrote Index with {len(clean_df)} rows to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write Index CSV {output_path}: {e}")
            return False
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean DataFrame for CSV export.
        
        Operations:
        - Replace NaN with empty string
        - Convert all values to strings
        - Clean up whitespace
        - Handle special characters
        """
        clean_df = df.copy()
        
        for col in clean_df.columns:
            clean_df[col] = clean_df[col].apply(self._clean_cell)
        
        return clean_df
    
    def _clean_cell(self, val) -> str:
        """
        Clean a single cell value for CSV export.
        
        Handles:
        - NaN/None -> ''
        - Float years -> int string (2024.0 -> '2024')
        - Newlines -> semicolons
        - Leading/trailing whitespace
        """
        if pd.isna(val):
            return ''
        
        # Convert to string
        if isinstance(val, float):
            # Check if it's a whole number (like 2024.0)
            if val == int(val):
                val_str = str(int(val))
            else:
                val_str = str(val)
        else:
            val_str = str(val)
        
        # Clean up
        val_str = val_str.strip()
        
        # Replace newlines with semicolons for CSV compatibility
        val_str = val_str.replace('\n', '; ').replace('\r', '')
        
        # Remove multiple spaces
        while '  ' in val_str:
            val_str = val_str.replace('  ', ' ')
        
        return val_str


def get_csv_writer() -> CSVWriter:
    """Factory function for CSVWriter."""
    return CSVWriter()
