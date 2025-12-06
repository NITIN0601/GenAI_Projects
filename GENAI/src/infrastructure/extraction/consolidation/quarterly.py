"""
Quarterly/period table consolidation service.

Consolidates tables with similar titles from multiple quarters/periods 
and exports to CSV/Excel.

For multi-year consolidation with transposition, use MultiYearTableConsolidator instead.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import logging
from difflib import SequenceMatcher

from config.settings import settings

logger = logging.getLogger(__name__)


class QuarterlyTableConsolidator:
    """
    Consolidate tables across multiple quarters/periods by table title.
    
    Features:
    - Hybrid search (semantic + fuzzy + metadata filtering)
    - Horizontal table merging (same rows, additional columns per quarter)
    - Handles missing data (N/A)
    - Exports to both CSV and Excel
    """
    
    def __init__(self, vector_store, embedding_manager=None):
        """
        Initialize table consolidator.
        
        Args:
            vector_store: Vector store instance
            embedding_manager: Embedding manager for semantic search
        """
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.similarity_threshold = settings.TABLE_SIMILARITY_THRESHOLD
    
    def find_tables_by_title(
        self, 
        title_query: str, 
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find all tables matching title using hybrid search.
        
        Strategy (Best Search Logic):
        1. Semantic similarity search on actual_table_title
        2. Fuzzy string matching for title variations
        3. Metadata filtering (table_content contains table structure)
        4. Deduplicate and rank by relevance
        
        Args:
            title_query: Table title to search for
            top_k: Maximum results to retrieve
            
        Returns:
            List of table dictionaries with metadata
        """
        logger.info(f"Searching for tables: '{title_query}'")
        
        # Step 1: Semantic similarity search
        try:
            results = self.vector_store.similarity_search_with_score(
                query=title_query,
                k=top_k
            )
            
            candidates = []
            for doc, score in results:
                # Extract metadata
                metadata = doc.metadata
                
                # Check if it's a table (has table structure)
                if not metadata.get('actual_table_title'):
                    continue
                
                actual_title = metadata.get('actual_table_title', '')
                
                # Step 2: Fuzzy matching on title
                fuzzy_score = self._fuzzy_match(title_query, actual_title)
                
                # Combined score (semantic + fuzzy)
                combined_score = (score + fuzzy_score) / 2
                
                if fuzzy_score >= self.similarity_threshold:
                    candidates.append({
                        'content': doc.page_content,
                        'metadata': metadata,
                        'title': actual_title,
                        'year': metadata.get('year'),
                        'quarter': metadata.get('quarter'),
                        'source_doc': metadata.get('source_doc'),
                        'page_no': metadata.get('page_no'),
                        'similarity_score': combined_score,
                        'fuzzy_score': fuzzy_score
                    })
            
            # Step 3: Deduplicate (same table might appear multiple times)
            unique_tables = self._deduplicate_tables(candidates)
            
            # Step 4: Sort by year/quarter
            sorted_tables = sorted(
                unique_tables,
                key=lambda t: (t['year'] or 0, self._quarter_to_num(t['quarter']))
            )
            
            logger.info(f"Found {len(sorted_tables)} matching tables")
            
            return sorted_tables
            
        except Exception as e:
            logger.error(f"Error searching for tables: {e}", exc_info=True)
            return []
    
    def consolidate_tables(
        self, 
        tables: List[Dict[str, Any]],
        table_name: str = "consolidated"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Consolidate tables horizontally (merge by rows, add columns).
        
        Args:
            tables: List of table dictionaries
            table_name: Name for the consolidated table
            
        Returns:
            Tuple of (consolidated DataFrame, metadata)
        """
        if not tables:
            return pd.DataFrame(), {}
        
        logger.info(f"Consolidating {len(tables)} tables")
        
        dataframes = []
        quarter_labels = []
        
        for table in tables:
            # Parse markdown table to DataFrame
            df = self._parse_markdown_table(table['content'])
            
            if df.empty:
                continue
            
            # Create quarter label (Time Series Format)
            year = table['year']
            quarter = table['quarter']
            
            # Convert to date
            date_str = self._get_period_date(year, quarter)
            quarter_labels.append(date_str)
            
            # Set first column as index (row headers)
            if len(df.columns) > 0:
                df = df.set_index(df.columns[0])
            
            # Rename columns with date label
            # We use the date as the column name for time series
            df.columns = [f"{col} ({date_str})" for col in df.columns]
            
            dataframes.append(df)
        
        if not dataframes:
            return pd.DataFrame(), {}
        
        # Merge all DataFrames
        # Strategy: outer join to keep all row headers (even if missing in some quarters)
        consolidated = dataframes[0]
        for df in dataframes[1:]:
            consolidated = consolidated.join(df, how='outer')
        
        # Fill missing values with N/A
        consolidated = consolidated.fillna('N/A')
        
        # Reset index to make row headers a column
        consolidated = consolidated.reset_index()
        consolidated.columns.name = None  # Remove index name
        
        # Metadata
        metadata = {
            'table_name': table_name,
            'quarters_included': quarter_labels,
            'total_quarters': len(quarter_labels),
            'total_rows': len(consolidated),
            'total_columns': len(consolidated.columns),
            'date_range': f"{tables[0]['year']}-{tables[-1]['year']}" if tables else ""
        }
        
        logger.info(f"Consolidated table: {len(consolidated)} rows x {len(consolidated.columns)} columns")
        
        return consolidated, metadata
    
    def export(
        self, 
        df: pd.DataFrame, 
        table_name: str,
        year_range: str = None
    ) -> Dict[str, str]:
        """
        Export consolidated table to CSV and Excel.
        
        Args:
            df: DataFrame to export
            table_name: Name of the table
            year_range: Year range string (e.g., "2023-2024")
            
        Returns:
            Dictionary with export paths
        """
        if df.empty:
            logger.warning("Empty DataFrame, nothing to export")
            return {}
        
        # Create output directory
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: tablename_yr_month
        timestamp = datetime.now().strftime("%Y_%m")
        safe_name = table_name.replace(' ', '_').replace('/', '_').lower()
        
        if year_range:
            base_filename = f"{safe_name}_{year_range}_{timestamp}"
        else:
            base_filename = f"{safe_name}_{timestamp}"
        
        export_paths = {}
        
        # Export CSV
        if settings.EXPORT_FORMAT in ["csv", "both"]:
            csv_path = output_dir / f"{base_filename}.csv"
            df.to_csv(csv_path, index=False)
            export_paths['csv'] = str(csv_path)
            logger.info(f"Exported CSV: {csv_path}")
        
        # Export Excel
        if settings.EXPORT_FORMAT in ["excel", "both"]:
            excel_path = output_dir / f"{base_filename}.xlsx"
            df.to_excel(excel_path, index=False, engine='openpyxl')
            export_paths['excel'] = str(excel_path)
            logger.info(f"Exported Excel: {excel_path}")
        
        return export_paths
    
    def _parse_markdown_table(self, markdown: str) -> pd.DataFrame:
        """Parse markdown table to DataFrame."""
        try:
            lines = [l.strip() for l in markdown.split('\n') if l.strip()]
            
            # Remove separator lines (|---|---|)
            lines = [l for l in lines if not all(c in '|-: ' for c in l)]
            
            if not lines:
                return pd.DataFrame()
            
            # Parse rows
            rows = []
            for line in lines:
                # Split by | and clean
                cells = [c.strip() for c in line.split('|')]
                # Remove empty cells at start/end
                cells = [c for c in cells if c]
                if cells:
                    rows.append(cells)
            
            if not rows or len(rows) < 2:
                return pd.DataFrame()
            
            # First row is header
            header = rows[0]
            data = rows[1:]
            
            # Create DataFrame
            df = pd.DataFrame(data, columns=header)
            
            return df
            
        except Exception as e:
            logger.error(f"Error parsing markdown table: {e}")
            return pd.DataFrame()
    
    def _fuzzy_match(self, query: str, target: str) -> float:
        """
        Calculate fuzzy string similarity.
        
        Returns:
            Similarity score 0.0-1.0
        """
        return SequenceMatcher(None, query.lower(), target.lower()).ratio()
    
    def _deduplicate_tables(self, candidates: List[Dict]) -> List[Dict]:
        """
        Deduplicate tables that appear multiple times.
        
        Strategy: Keep highest scoring version per (year, quarter)
        """
        # Group by (year, quarter)
        groups = {}
        for candidate in candidates:
            key = (candidate['year'], candidate['quarter'])
            
            if key not in groups:
                groups[key] = candidate
            else:
                # Keep higher scoring version
                if candidate['similarity_score'] > groups[key]['similarity_score']:
                    groups[key] = candidate
        
        return list(groups.values())
    
    def _get_period_date(self, year: Optional[int], quarter: Optional[str]) -> str:
        """
        Get standard period end date for quarter.
        
        Args:
            year: Year (e.g., 2024)
            quarter: Quarter (e.g., "Q1", "10-K")
            
        Returns:
            Date string YYYY-MM-DD
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

    def _quarter_to_num(self, quarter: Optional[str]) -> int:
        """Convert quarter string to number for sorting."""
        if not quarter:
            return 5  # Put non-quarter items at end
        
        if 'Q1' in quarter:
            return 1
        elif 'Q2' in quarter:
            return 2
        elif 'Q3' in quarter:
            return 3
        elif 'Q4' in quarter or '10K' in quarter:
            return 4
        else:
            return 5

# Global instance
_quarterly_consolidator: Optional[QuarterlyTableConsolidator] = None

def get_quarterly_consolidator(vector_store=None, embedding_manager=None) -> QuarterlyTableConsolidator:
    """Get global quarterly table consolidator instance."""
    global _quarterly_consolidator
    if _quarterly_consolidator is None or vector_store is not None:
        _quarterly_consolidator = QuarterlyTableConsolidator(vector_store, embedding_manager)
    return _quarterly_consolidator
