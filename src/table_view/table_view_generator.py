"""
Table View Generator.

This module is responsible for physically materializing distinct time-series CSV files 
for every unique table identified in the Master_Table_Index.

Key Logic:
1.  **Reads Index**: Iterates through each table defined in Master_Table_Index.csv.
2.  **Filters**: Selects rows from Master_Consolidated.csv matching the table.
3.  **Pivots**: Transforms data into a wide matrix (Time-Series View).
    - Rows: Source, Dates, Header
    - Cols: Category - Product/Entity
    - Vals: Data Value
4.  **Saves**: Writes [Table_ID].csv.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

# Configure logger
logger = logging.getLogger(__name__)

class TableViewGenerator:
    """Generates individual CSV views for each table."""

    def __init__(self, master_file: Path, index_file: Path, output_dir: Path):
        """
        Initialize the generator.

        Args:
            master_file: Path to Master_Consolidated.csv
            index_file: Path to Master_Table_Index.csv
            output_dir: Directory to save individual [Table_ID].csv files
        """
        self.master_file = master_file
        self.index_file = index_file
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _pivot_table_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform filtering data into the Time-Series View matrix.
        
        Args:
            df: Filtered DataFrame for a single table.
            
        Returns:
            Pivoted DataFrame.
        """
        # Create a combined column for columns if Category exists
        def make_col_header(row):
            cat = row['Category'] if pd.notna(row['Category']) and str(row['Category']).strip() != '' else ''
            prod = row['Product/Entity']
            if cat:
                return f"{cat} - {prod}"
            return prod

        # Use .apply with axis=1 for row-wise operation
        # Assign to a new column safely
        df = df.copy()
        df['ColumnLabel'] = df.apply(make_col_header, axis=1)

        # Pivot
        # Index: Source, Dates, Header
        # Columns: ColumnLabel
        # Values: Data Value
        
        # We need to handle potential duplicates strictly. 
        # Ideally, (Source, Dates, Header, Product) is unique.
        # If not, pivot will fail or we need aggregation. 
        # Assuming uniqueness logic from Step 6 holds, but safe to use pivot_table with aggfunc 'first' just in case.
        
        pivot_df = df.pivot_table(
            index=['Source', 'Dates', 'Header'],
            columns='ColumnLabel',
            values='Data Value',
            aggfunc='first' # Should be unique, but take first if dupe exists to avoid error
        )
        
        # Reset index to make Source, Dates, Header regular columns
        pivot_df = pivot_df.reset_index()
        
        return pivot_df

    def generate_views(self):
        """Execute the generation of all table views."""
        logger.info(f"Loading Master Data: {self.master_file}")
        try:
            master_df = pd.read_csv(self.master_file)
            # Ensure keys handles NaNs consistently
            master_df['Section'] = master_df['Section'].fillna('')
            master_df['Table Title'] = master_df['Table Title'].fillna('')
            master_df['Header'] = master_df['Header'].fillna('')
        except FileNotFoundError:
            logger.error(f"Master file not found: {self.master_file}")
            raise

        logger.info(f"Loading Index: {self.index_file}")
        try:
            index_df = pd.read_csv(self.index_file)
            index_df['Section'] = index_df['Section'].fillna('')
            index_df['Table Title'] = index_df['Table Title'].fillna('')
        except FileNotFoundError:
            logger.error(f"Index file not found: {self.index_file}")
            raise

        logger.info(f"Generating views for {len(index_df)} tables...")

        for _, row in index_df.iterrows():
            table_id = row['Table_ID']
            section = row['Section']
            title = row['Table Title']
            
            # Filter Master Data
            # Note: Explicit filtering using the same logic as Index Generator
            # We match empty strings for NaNs as standardized above
            mask = (master_df['Section'] == section) & (master_df['Table Title'] == title)
            table_data = master_df[mask]

            if table_data.empty:
                logger.warning(f"No data found for {table_id} ({title}). Skipping.")
                continue

            # Pivot Data
            view_df = self._pivot_table_data(table_data)

            # Save
            output_path = self.output_dir / row['csvfile']
            view_df.to_csv(output_path, index=False)
            
            # logger.debug(f"Generated {output_path}")

        logger.info(f"Completed generation of {len(index_df)} views in {self.output_dir}")

if __name__ == "__main__":
    # Test execution
    import sys
    
    # Setup basic logging for standalone run
    logging.basicConfig(level=logging.INFO)
    
    try:
        base_dir = Path.cwd()
        master_path = base_dir / "data" / "consolidate" / "Master_Consolidated.csv"
        index_path = base_dir / "data" / "table_views" / "Master_Table_Index.csv"
        output_dir = base_dir / "data" / "table_views"
        
        if not master_path.exists() or not index_path.exists():
            print(f"Error: Required files do not exist.")
            sys.exit(1)

        generator = TableViewGenerator(master_path, index_path, output_dir)
        generator.generate_views()
        
    except Exception as e:
        print(f"Execution failed: {e}")
        sys.exit(1)
