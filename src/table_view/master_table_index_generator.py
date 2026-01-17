"""
Master Table Index Generator.

This module is responsible for analyzing the Master_Consolidated.csv and generating
a `Master_Table_Index.csv`. This index serves as the central catalog for all available
tables in the dataset.

Key Logic:
1.  **Grouping**: Identified unique tables by (Section, Table Title).
2.  **Sorting**: Uses ORIGINAL ORDER of appearance in the master file (DO NOT SORT ALPHABETICALLY).
3.  **ID Assignment**: Assigns sequential IDs (TBL_001, ...).
4.  **Metadata**: Cleans source filenames, aggregates years, counts products/records.
"""

import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Configure logger
logger = logging.getLogger(__name__)

class MasterTableIndexGenerator:
    """Generates the Master Table Index from consolidated data."""

    def __init__(self, input_file: Path, output_dir: Path):
        """
        Initialize the generator.

        Args:
            input_file: Path to the Master_Consolidated.csv
            output_dir: Directory to save the Master_Table_Index.csv
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _clean_sources(self, source_series: pd.Series) -> str:
        """
        Clean and aggregate source filenames.
        
        Logic:
        - Extract base filename by removing '_pg.*' suffix.
        - Deduplicate.
        - Sort alphabetically.
        - Join with comma.
        """
        cleaned_sources = set()
        for source in source_series.dropna().unique():
            # Remove _pg... suffix (e.g., '10k.pdf_pg10' -> '10k.pdf')
            # Handle cases where source might not have _pg or be empty
            if not isinstance(source, str):
                continue
            
            clean_name = re.sub(r'_pg.*', '', source)
            cleaned_sources.add(clean_name)
        
        return ", ".join(sorted(cleaned_sources))

    def _extract_years(self, dates_series: pd.Series) -> str:
        """Extract year range from Dates column."""
        years = set()
        for date_str in dates_series.dropna().unique():
            # Extract 4 consecutive digits
            matches = re.findall(r'20\d{2}', str(date_str))
            for year in matches:
                years.add(int(year))
        
        if not years:
            return ""
        
        min_year = min(years)
        max_year = max(years)
        
        if min_year == max_year:
            return str(min_year)
        else:
            return f"{min_year}-{max_year}"

    def generate_index(self) -> Path:
        """
        Execute the index generation process.

        Returns:
            Path to the generated index file.
        """
        logger.info(f"Reading master data from {self.input_file}...")
        try:
            df = pd.read_csv(self.input_file)
        except FileNotFoundError:
            logger.error(f"Input file not found: {self.input_file}")
            raise

        logger.info(f"Loaded {len(df)} rows. Generating Table Index...")

        # 1. Identify Unique Tables (Section + Table Title)
        # We need to preserve order.
        # Create a temporary 'GroupKey' for identification
        df['GroupKey'] = list(zip(df['Section'].fillna(''), df['Table Title'].fillna('')))
        
        # Get unique keys in order of appearance
        # using dict.fromkeys to preserve order (Python 3.7+)
        unique_keys = list(dict.fromkeys(df['GroupKey']))
        
        logger.info(f"Found {len(unique_keys)} unique tables.")

        index_records = []

        for i, (section, title) in enumerate(unique_keys, start=1):
            table_id = f"TBL_{i:03d}"
            
            # Filter original DF for this group to calculate metadata
            # Note: We filter by the original columns, treating NaNs as empty strings for comparison if needed,
            # but here strict filtering on the values we found is safer.
            # Using mask handles NaNs correctly if we matched on them.
            if section == '':
                section_mask = df['Section'].isna() | (df['Section'] == '')
            else:
                section_mask = df['Section'] == section
                
            if title == '':
                title_mask = df['Table Title'].isna() | (df['Table Title'] == '')
            else:
                title_mask = df['Table Title'] == title

            group_df = df[section_mask & title_mask]
            
            # Calculate Metadata
            source_file_str = self._clean_sources(group_df['Source'])
            years_str = self._extract_years(group_df['Dates'])
            product_count = group_df['Product/Entity'].nunique()
            record_count = len(group_df)
            csv_filename = f"{table_id}.csv"

            index_records.append({
                'Table_ID': table_id,
                'source_file': source_file_str,
                'Section': section,
                'Table Title': title,
                'Product count': product_count,
                'Years': years_str,
                'Record count': record_count,
                'csvfile': csv_filename
            })

        # Create Index DataFrame
        index_df = pd.DataFrame(index_records)
        
        # Columns in specific order
        output_columns = [
            'Table_ID', 'source_file', 'Section', 'Table Title', 
            'Product count', 'Years', 'Record count', 'csvfile'
        ]
        index_df = index_df[output_columns]

        output_path = self.output_dir / "Master_Table_Index.csv"
        index_df.to_csv(output_path, index=False)
        
        logger.info(f"Successfully generated Index with {len(index_df)} tables at: {output_path}")
        return output_path

if __name__ == "__main__":
    # Test execution
    import sys
    
    # Setup basic logging for standalone run
    logging.basicConfig(level=logging.INFO)
    
    try:
        base_dir = Path.cwd()
        input_path = base_dir / "data" / "consolidate" / "Master_Consolidated.csv"
        output_dir = base_dir / "data" / "table_views"
        
        if not input_path.exists():
            print(f"Error: {input_path} does not exist.")
            sys.exit(1)

        generator = MasterTableIndexGenerator(input_path, output_dir)
        generator.generate_index()
        
    except Exception as e:
        print(f"Execution failed: {e}")
        sys.exit(1)
