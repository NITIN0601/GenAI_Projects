"""Consolidated Exporter Transpose - Time-series conversion.

Converts consolidated point-in-time tables (dates as columns) to 
time-series format (dates as rows).

Fixed issues per docs/pipeline_operations.md:
1. ✓ Y/Q Format - Uses QuarterDateMapper (Q1-QTD-2024 format)
2. ✓ Multi-sheet processing - Loops all sheets except Index/TOC
3. ✓ Auto-detect first column - No hardcoded "Row Label" assumption
4. ✓ Skip metadata rows - Detects and skips 12-row header
5. ✓ Index/TOC in output - Generates navigation sheets
6. ✓ Logging - Uses proper logger instead of print()
7. ✓ No sys.path hack - Standard module imports

Edge cases handled per docs:
- Chronological Y/Q sorting
- Unknown Y/Q labels preserved with "Unknown-" prefix
- Empty tables skipped gracefully
- Category headers detected correctly
"""

import pandas as pd
import re
import warnings
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Suppress PerformanceWarning from non-lexsorted MultiIndex operations
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)

from src.utils.excel_utils import ExcelUtils
from src.utils.metadata_labels import MetadataLabels
from src.utils.quarter_mapper import QuarterDateMapper
from src.utils.metadata_builder import MetadataBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _sort_chronologically(df: pd.DataFrame, dates_col) -> pd.DataFrame:
    """
    Sort DataFrame rows chronologically by Y/Q code.
    
    Y/Q codes like Q1-2024, Q2-QTD-2025 are parsed and sorted by:
    1. Year (ascending)
    2. Quarter number (ascending)
    3. Period type (QTD before YTD)
    
    Args:
        df: DataFrame with transposed data
        dates_col: Column tuple for dates (e.g., ('', 'Dates'))
        
    Returns:
        Sorted DataFrame
    """
    if df.empty:
        return df
    
    # Handle MultiIndex columns - check if dates_col is in columns
    try:
        col_list = list(df.columns)
        if dates_col not in col_list:
            return df
    except Exception:
        return df
    
    def get_sort_key(yq_code):
        """Extract (year, quarter_num, period_priority) for sorting."""
        if pd.isna(yq_code) or not yq_code:
            return (9999, 9, 9)  # Put nulls last
        
        yq_str = str(yq_code)
        
        # Handle Unknown- prefix
        if yq_str.startswith('Unknown'):
            return (9998, 9, 9)  # Put unknowns near end
        
        # Parse patterns like: Q1-2024, Q2-QTD-2025, Q3-YTD-2024, YTD-2024
        year_match = re.search(r'20(\d{2})', yq_str)
        year = int('20' + year_match.group(1)) if year_match else 9999
        
        quarter_match = re.search(r'Q(\d)', yq_str)
        quarter = int(quarter_match.group(1)) if quarter_match else 4  # Default Q4 for YTD-2024
        
        # Period priority: point-in-time < QTD < YTD
        if 'YTD' in yq_str:
            period = 2
        elif 'QTD' in yq_str:
            period = 1
        else:
            period = 0
        return (year, quarter, period)
    
    # Create sort key column - handle both regular and MultiIndex columns
    try:
        if dates_col in df.columns:
            df = df.copy()  # Avoid SettingWithCopyWarning
            df['_sort_key'] = df[dates_col].apply(get_sort_key)
            
            # Sort rows chronologically (oldest first) and remove helper column
            df = df.sort_values('_sort_key').reset_index(drop=True)
            df = df.drop('_sort_key', axis=1, errors='ignore')
    except Exception as e:
        logger.debug(f"Could not sort chronologically: {e}")
    
    return df


def create_transposed_dataframe(
    result_df: pd.DataFrame,
    row_labels: List[str],
    label_to_section: Dict[str, str],
    normalized_row_labels: Dict[str, str]
) -> pd.DataFrame:
    """
    Transpose the dataframe and create multi-level column headers (Category, Line Item).
    
    This function handles the logic of converting the consolidated point-in-time table
    (where dates are columns) into a time-series table (where dates are rows).
    
    Args:
        result_df: The consolidated DataFrame (before transposition)
        row_labels: List of unique row keys (e.g. ['Ratio', 'Ratio::Loans']) matching df rows
        label_to_section: Map of row key to section name
        normalized_row_labels: Map of row key to original display label
        
    Returns:
        Transposed DataFrame with MultiIndex columns (Category, Line Item)
    """
    if result_df.empty:
        return result_df

    # Auto-detect first column name (not hardcoded to 'Row Label')
    first_col = result_df.columns[0] if len(result_df.columns) > 0 else 'Row Label'
    
    # Transpose the DataFrame
    # Set first column as index so it becomes the columns after transpose
    result_df = result_df.set_index(first_col)
    result_df = result_df.T
    
    # The index now contains the column headers (dates/periods)
    result_df.index.name = 'Dates'
    result_df = result_df.reset_index()
    
    # Create multi-level column headers using the known row_labels structure
    new_columns = []
    
    # First column is always Dates
    new_columns.append(('', 'Dates'))
    
    # Iterate through the row_labels which correspond exactly to the subsequent columns
    # matching the original row order
    for key in row_labels:
        # Recover section and display label
        section = label_to_section.get(key, '').strip()
        # Get display label (original case)
        original_display = normalized_row_labels.get(key, key)
        display_label = ExcelUtils.clean_footnote_references(original_display)
        
        if section:
            # Item under a category
            category_display = section.title()
            line_item_display = display_label.title()
        else:
            # Root item (Category header or top-level item)
            category_display = ''  
            line_item_display = display_label.title()
        
        new_columns.append((category_display, line_item_display))
    
    # Verify column count match
    if len(new_columns) != len(result_df.columns):
        logger.warning(f"Column count mismatch: {len(new_columns)} vs {len(result_df.columns)}")
        # Fallback: use simple columns
        return result_df

    # Create MultiIndex columns
    result_df.columns = pd.MultiIndex.from_tuples(new_columns, names=['Category', 'Line Item'])

    # Convert Dates column values to standard Y/Q format for traceability
    # e.g., 'Three Months Ended March 31, 2024' -> 'Q1-QTD-2024'
    dates_col = ('', 'Dates')
    
    # Find the integer location of the Dates column to modify it
    col_idx = -1
    for i, col in enumerate(result_df.columns):
        if col == dates_col:
            col_idx = i
            break
            
    if col_idx != -1:
        for row_idx in range(len(result_df)):
            val = result_df.iloc[row_idx, col_idx]
            if val is not None and pd.notna(val) and str(val).strip():
                val_str = str(val).strip()
                try:
                    # Check if already in code format (Q1-2024, Q2-QTD-2025, YTD-2024)
                    import re
                    is_already_code = bool(re.match(r'^(Q[1-4](-QTD|-YTD)?-20\d{2}|YTD-20\d{2})$', val_str))
                    
                    if is_already_code:
                        # Already in code format, keep as-is
                        pass
                    else:
                        # Use QuarterDateMapper for standardized format
                        formatted_val = QuarterDateMapper.display_to_code(val_str)
                        if formatted_val and formatted_val != val_str:
                            result_df.iloc[row_idx, col_idx] = formatted_val
                        elif not formatted_val:
                            # Keep original but mark as unknown for sorting
                            result_df.iloc[row_idx, col_idx] = f"Unknown-{val_str[:20]}"
                except Exception:
                    pass  # Keep original if conversion fails
    
    # Sort rows chronologically by the Y/Q code (Dates column)
    result_df = _sort_chronologically(result_df, dates_col)

    return result_df


def reconstruct_metadata_from_df(df: pd.DataFrame, first_col: Optional[str] = None) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    """
    Reconstruct row_labels, label_to_section, and normalized_row_labels from a DataFrame.
    
    Args:
        df: DataFrame to process
        first_col: Name of first column (auto-detected if None)
    
    Returns:
        Tuple of (row_labels, label_to_section, normalized_row_labels)
    """
    # Auto-detect first column if not provided
    if first_col is None:
        first_col = df.columns[0] if len(df.columns) > 0 else 'Row Label'
    
    if first_col not in df.columns:
        raise ValueError(f"DataFrame must have '{first_col}' column")
        
    row_labels = []
    label_to_section = {}
    normalized_row_labels = {}
    
    current_category = ""  # No category prefix for items without explicit section
    
    # Identify data columns (exclude first column)
    data_cols = [c for c in df.columns if c != first_col]
    
    for idx, row in df.iterrows():
        # Use index as unique key
        key = str(idx) 
        row_labels.append(key)
        
        label_val = str(row[first_col]).strip() if pd.notna(row[first_col]) else ''
        normalized_row_labels[key] = label_val
        
        # Check if category (row label present but all data columns empty)
        is_category = False
        if label_val:
            is_empty = True
            for col in data_cols:
                val = row[col]
                # Handle case where val is a Series (duplicate column names)
                if isinstance(val, pd.Series):
                    # If any value in the series is not empty, it's not a category
                    if val.notna().any() and any(str(v).strip() not in ['', 'nan'] for v in val):
                        is_empty = False
                        break
                else:
                    if pd.notna(val) and str(val).strip() not in ['', 'nan']: 
                        is_empty = False
                        break
            
            if is_empty:
                is_category = True
        
        if is_category:
            current_category = label_val
            label_to_section[key] = '' 
        else:
            label_to_section[key] = current_category

    return row_labels, label_to_section, normalized_row_labels


def skip_metadata_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Skip metadata rows (first 12 rows) from the DataFrame.
    
    Detects metadata rows using MetadataLabels.is_metadata_row().
    
    Args:
        df: DataFrame with potential metadata rows
        
    Returns:
        DataFrame with metadata rows removed
    """
    if df.empty:
        return df
    
    first_col = df.columns[0] if len(df.columns) > 0 else None
    if first_col is None:
        return df
    
    # Find first non-metadata row
    data_start_idx = 0
    for idx, row in df.iterrows():
        cell_val = str(row[first_col]) if pd.notna(row[first_col]) else ''
        if MetadataLabels.is_metadata_row(cell_val):
            data_start_idx = idx + 1
        else:
            # Check if this looks like a data row (has numeric values)
            has_data = False
            for col in df.columns[1:]:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    try:
                        float(str(val).replace(',', '').replace('$', '').replace('(', '-').replace(')', ''))
                        has_data = True
                        break
                    except ValueError:
                        pass
            if has_data:
                break
            data_start_idx = idx + 1
    
    # Return DataFrame starting from data rows
    if data_start_idx > 0 and data_start_idx < len(df):
        logger.debug(f"Skipping {data_start_idx} metadata rows")
        return df.iloc[data_start_idx:].reset_index(drop=True)
    
    return df


def transpose_sheet(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """
    Transpose a single sheet's DataFrame.
    
    Args:
        df: DataFrame to transpose
        sheet_name: Name of sheet (for logging)
        
    Returns:
        Transposed DataFrame
    """
    if df.empty:
        logger.warning(f"Sheet {sheet_name} is empty, skipping")
        return pd.DataFrame()
    
    # Skip metadata rows
    df = skip_metadata_rows(df)
    
    if df.empty:
        logger.warning(f"Sheet {sheet_name} has only metadata, skipping")
        return pd.DataFrame()
    
    # Get first column name
    first_col = df.columns[0] if len(df.columns) > 0 else 'Row Label'
    
    # Reconstruct metadata
    row_labels, label_to_section, normalized_row_labels = reconstruct_metadata_from_df(df, first_col)
    
    # Transpose
    transposed_df = create_transposed_dataframe(df, row_labels, label_to_section, normalized_row_labels)
    
    return transposed_df


def transpose_excel_file(input_file: str, output_file: str) -> Dict:
    """
    Read an Excel file, transpose ALL sheets (except Index/TOC), and save.
    
    Args:
        input_file: Path to input Excel file
        output_file: Path to output Excel file
        
    Returns:
        Dict with processing stats
    """
    logger.info(f"Reading {input_file}...")
    
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_file}")
        return {'error': 'Input file not found'}
    
    # Get all sheet names
    xlsx = pd.ExcelFile(input_file)
    sheet_names = xlsx.sheet_names
    
    stats = {
        'sheets_processed': 0,
        'sheets_skipped': 0,
        'errors': []
    }
    
    logger.info(f"Found {len(sheet_names)} sheets")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name in sheet_names:
            # Skip navigation sheets
            if sheet_name in ['Index', 'TOC', 'TOC_Sheet']:
                logger.debug(f"Skipping navigation sheet: {sheet_name}")
                stats['sheets_skipped'] += 1
                continue
            
            try:
                logger.debug(f"Processing sheet: {sheet_name}")
                df = pd.read_excel(input_file, sheet_name=sheet_name)
                
                transposed_df = transpose_sheet(df, sheet_name)
                
                if not transposed_df.empty:
                    # Flatten MultiIndex columns before writing (pandas limitation)
                    if isinstance(transposed_df.columns, pd.MultiIndex):
                        # Convert MultiIndex to flat column names: "Category - Line Item"
                        flat_cols = []
                        for col in transposed_df.columns:
                            if isinstance(col, tuple):
                                # Filter out empty parts and join with ' - '
                                parts = [str(p).strip() for p in col if p and str(p).strip()]
                                flat_cols.append(' - '.join(parts) if parts else 'Unnamed')
                            else:
                                flat_cols.append(str(col))
                        transposed_df.columns = flat_cols
                    
                    transposed_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    stats['sheets_processed'] += 1
                else:
                    stats['sheets_skipped'] += 1
                    
            except Exception as e:
                logger.warning(f"Error processing sheet {sheet_name}: {e}")
                stats['errors'].append(f"{sheet_name}: {str(e)}")
        
        # Create Index sheet
        _create_index_sheet(writer, stats['sheets_processed'])
    
    logger.info(f"Saved to {output_file}")
    logger.info(f"Processed {stats['sheets_processed']} sheets, skipped {stats['sheets_skipped']}")
    
    return stats


def _create_index_sheet(writer, total_sheets: int):
    """Create a simple index sheet for the transposed output."""
    index_data = {
        'Info': ['Transposed Tables Report', 'Generated by Pipeline Step 5'],
        'Value': [f'{total_sheets} sheets processed', 'Time-series format']
    }
    index_df = pd.DataFrame(index_data)
    index_df.to_excel(writer, sheet_name='Index', index=False)


# For backward compatibility with existing code
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python consolidated_exporter_transpose.py <input_excel> <output_excel>")
    else:
        transpose_excel_file(sys.argv[1], sys.argv[2])
