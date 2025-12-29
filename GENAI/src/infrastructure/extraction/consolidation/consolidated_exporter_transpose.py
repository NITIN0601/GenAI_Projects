
import pandas as pd
import sys
import os

# Add project root to path for imports to work when run as script
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.append(project_root)

from typing import List, Dict, Optional
from src.utils.excel_utils import ExcelUtils
from src.utils.metadata_builder import MetadataBuilder

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
    
    Crucially, it uses the original `row_labels` list (which contains unique section-keyed identifiers)
    to correctly reconstruct the Category/Line Item hierarchy for the columns, ensuring that
    duplicate line items (e.g., "Loans" under "Ratio" and "Loans" under "ROCER") are
    correctly distinguished and grouped.
    
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

    # Transpose the DataFrame
    # Set Row Label as index so it becomes the columns after transpose
    result_df = result_df.set_index('Row Label')
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
            # If it's a section header like "Ratio", it acts as a category marker
            # For the column header, we can leave Category blank or use 'General'
            # Here keeping it blank to match user preference/visual style
            category_display = ''  
            line_item_display = display_label.title()
        
        new_columns.append((category_display, line_item_display))
    
    # Verify column count match
    if len(new_columns) != len(result_df.columns):
        # Fallback/Safety: If counts don't match (shouldn't happen if logic is correct),
        # return simplified transpose or raise warning? 
        # For now, let pandas raise the error if length mismatch, or truncate/pad.
        # But we expect exact match.
        pass

    # Create MultiIndex columns
    result_df.columns = pd.MultiIndex.from_tuples(new_columns, names=['Category', 'Line Item'])

    # Convert Dates column values to QnYYYY format for traceability
    # e.g., 'Three Months Ended March 31, 2024' -> '3QTD2024'
    dates_col = ('', 'Dates')
    
    # Find the integer location of the Dates column to modify it
    # (Using simple column scan to avoid MultiIndex lookup issues)
    col_idx = -1
    for i, col in enumerate(result_df.columns):
        if col == dates_col:
            col_idx = i
            break
            
    if col_idx != -1:
        # Vectorized apply might be faster, but loop is safe for mixed types
        # Using .iloc for modification to avoid SettingWithCopy
        for row_idx in range(len(result_df)):
            val = result_df.iloc[row_idx, col_idx]
            if val is not None and pd.notna(val) and str(val).strip():
                try:
                    formatted_val = MetadataBuilder.convert_to_qn_format(str(val))
                    result_df.iloc[row_idx, col_idx] = formatted_val
                except Exception:
                    pass # Keep original if conversion fails

    return result_df

def reconstruct_metadata_from_df(df: pd.DataFrame):
    """
    Reconstruct row_labels, label_to_section, and normalized_row_labels from a DataFrame.
    Assumes "Row Label" column exists.
    Assumes Rows with text in "Row Label" but empty data columns are CATEGORY headers.
    """
    if 'Row Label' not in df.columns:
        raise ValueError("DataFrame must have 'Row Label' column")
        
    row_labels = []
    label_to_section = {}
    normalized_row_labels = {}
    
    current_category = "General"
    
    # Identify data columns (exclude Row Label and metadata columns if any)
    # Typically data columns are Q1 2024, etc.
    # We can assume any column that is NOT 'Row Label' is a data column.
    data_cols = [c for c in df.columns if c != 'Row Label']
    
    for idx, row in df.iterrows():
        # Use index as unique key
        key = str(idx) 
        row_labels.append(key)
        
        label_val = str(row['Row Label']).strip() if pd.notna(row['Row Label']) else ''
        normalized_row_labels[key] = label_val
        
        # Check if category
        # Logic: If row label is present, and ALL data columns are empty/null
        is_category = False
        if label_val:
            # Check data cols
            is_empty = True
            for col in data_cols:
                val = row[col]
                if pd.notna(val) and str(val).strip() not in ['', 'nan', 'test']: 
                    # 'test' logic is just safeguard, mainly check for numbers
                    is_empty = False
                    break
            
            if is_empty:
                is_category = True
        
        if is_category:
            current_category = label_val
            # A category header itself belongs to no parent section (or itself?)
            # In the main logic, category headers usually have section=''. 
            label_to_section[key] = '' 
        else:
            # Item
            label_to_section[key] = current_category

    return row_labels, label_to_section, normalized_row_labels

def transpose_excel_file(input_file: str, output_file: str):
    """
    Read an Excel file (first sheet), transpose it using the category logic, and save.
    """
    print(f"Reading {input_file}...")
    # Read without header first to find the header row? 
    # Usually the consolidated output has header in row 0.
    df = pd.read_excel(input_file)
    
    # Check if Row Label exists
    if 'Row Label' not in df.columns:
        print("Error: 'Row Label' column not found in input file.")
        return
        
    print("Reconstructing metadata categories...")
    row_labels, label_to_section, normalized_row_labels = reconstruct_metadata_from_df(df)
    
    print("Transposing...")
    transposed_df = create_transposed_dataframe(df, row_labels, label_to_section, normalized_row_labels)
    
    print(f"Saving to {output_file}...")
    transposed_df.to_excel(output_file)
    print("Done.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python consolidated_exporter_transpose.py <input_excel> <output_excel>")
    else:
        transpose_excel_file(sys.argv[1], sys.argv[2])
