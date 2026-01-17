"""
Merge CSV Pipeline - Consolidates normalized CSV files.

This pipeline performs two stages of merging:
1. Individual Merge: Consolidates table CSVs within each source directory (e.g., 10q0925).
2. Master Merge: Consolidates all individual source CSVs into a single master dataset.
"""

import os
import glob
import pandas as pd
from typing import List, Optional
from src.utils import get_logger

logger = get_logger(__name__)

class MergeCSVPipeline:
    """
    Pipeline for merging normalized CSV files into consolidated datasets.
    """
    
    def __init__(self, base_dir: str):
        """
        Initialize the merge pipeline.
        
        Args:
            base_dir: Base directory containing source folders (e.g., data/csv_output_normalized)
        """
        self.base_dir = base_dir
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, output_dir: Optional[str] = None):
        """
        Execute the merge pipeline.
        
        Args:
            output_dir: Directory to save the final master file. Defaults to base_dir/consolidated.
        """
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(self.base_dir), "consolidate")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: Merge individual folders
        consolidated_files = self._merge_individual_folders()
        
        if not consolidated_files:
            self.logger.warning("No consolidated files to merge into master.")
            return

        # Step 2: Create master consolidated file
        self._create_master_consolidated(consolidated_files, output_dir)

    def _merge_individual_folders(self) -> List[str]:
        """
        Merge CSVs in each source subdirectory into a consolidated file.
        
        Returns:
            List of paths to the generated consolidated CSV files.
        """
        consolidated_files = []
        
        # Iterate over all source directories (e.g., 10q0925, 10k1224)
        for source_dir in glob.glob(os.path.join(self.base_dir, "*")):
            if not os.path.isdir(source_dir):
                continue
                
            source_name = os.path.basename(source_dir)
            self.logger.info(f"Processing source directory: {source_name}")
            
            # Collect all CSV files
            csv_files = glob.glob(os.path.join(source_dir, "*.csv"))
            
            dfs = []
            for csv_file in csv_files:
                filename = os.path.basename(csv_file)
                
                # Exclude Index.csv and any existing consolidated files
                if filename == "Index.csv" or "_consolidated.csv" in filename:
                    continue
                    
                # Skip empty or header-only files
                try:
                    # Check for emptiness using utf-8-sig to handle BOM
                    if os.path.getsize(csv_file) == 0:
                        self.logger.debug(f"Skipping empty file: {filename}")
                        continue
                        
                    # Use utf-8-sig to handle Byte Order Mark (BOM)
                    df = pd.read_csv(csv_file, encoding='utf-8-sig')
                    
                    if df.empty:
                        self.logger.debug(f"Skipping empty DataFrame: {filename}")
                        continue
                        
                    dfs.append(df)
                    
                except Exception as e:
                    self.logger.error(f"Failed to read {filename}: {e}")
                    continue
            
            if not dfs:
                self.logger.warning(f"No valid CSV files found in {source_name}")
                continue
                
            # Concatenate all tables for this source
            try:
                consolidated_df = pd.concat(dfs, ignore_index=True)
                
                # Save consolidated file in the source directory
                output_path = os.path.join(source_dir, f"{source_name}_consolidated.csv")
                consolidated_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                
                self.logger.info(f"Created consolidated file: {output_path} ({len(consolidated_df)} rows)")
                consolidated_files.append(output_path)
                
            except Exception as e:
                self.logger.error(f"Failed to consolidate {source_name}: {e}")
                
        return consolidated_files

    def _create_master_consolidated(self, file_list: List[str], output_dir: str):
        """
        Merge multiple consolidated files into a single master file.
        
        Args:
            file_list: List of paths to consolidated CSV files.
            output_dir: Directory to save the master file.
        """
        self.logger.info("Creating Master Consolidated file...")
        
        all_dfs = []
        for file_path in file_list:
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                all_dfs.append(df)
            except Exception as e:
                self.logger.error(f"Failed to read consolidated file {file_path}: {e}")
                
        if not all_dfs:
            self.logger.error("No data to create Master Consolidated file.")
            return
            
        try:
            master_df = pd.concat(all_dfs, ignore_index=True)

            # Consolidate rows with identical values except Source
            self.logger.info("Consolidating identical rows...")
            
            # Columns to group by (all except Source)
            # We assume these are the standard columns. We should dynamically check or use fixed list.
            # Using fixed list based on plan to be safe, or difference.
            # Safe approach: all columns except 'Source'.
            group_cols = [c for c in master_df.columns if c != 'Source']
            
            if group_cols:
                # Fill NaNs in grouping columns to ensure they are included in the group
                # Using dropna=False in groupby is also an option, but filling ensures consistency
                master_df[group_cols] = master_df[group_cols].fillna('')
                
                # Aggregate Source by joining unique values
                master_df = master_df.groupby(group_cols, as_index=False).agg({
                    'Source': lambda x: ', '.join(sorted([str(s) for s in (pd.unique(x)) if pd.notna(s) and str(s).strip() != '']))
                })
                
                # Reorder columns to put Source first (if it got moved or just to be safe)
                cols = ['Source'] + group_cols
                master_df = master_df[cols]
                
            output_path = os.path.join(output_dir, "Master_Consolidated.csv")
            master_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"Successfully created: {output_path}")
            self.logger.info(f"Total rows: {len(master_df)}")
            
        except Exception as e:
            self.logger.error(f"Failed to create Master Consolidated file: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Merge normalized CSV files.")
    parser.add_argument("--base-dir", default="data/csv_output_normalized", help="Base directory of normalized CSVs")
    parser.add_argument("--output-dir", help="Directory for master output")
    
    args = parser.parse_args()
    
    pipeline = MergeCSVPipeline(args.base_dir)
    pipeline.run(args.output_dir)
