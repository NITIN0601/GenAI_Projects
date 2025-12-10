"""
Unified Table Consolidator.

Consolidates tables across multiple quarters/years by table title.
Combines features from both QuarterlyTableConsolidator and MultiYearTableConsolidator.

Features:
- Hybrid search (semantic + fuzzy matching)
- Year and quarter filtering
- Horizontal merge (same rows, columns per period)
- Optional transpose (dates as rows)
- Data validation
- CSV/Excel export
- Currency value cleaning

Usage:
    from src.infrastructure.extraction.consolidation import get_table_consolidator
    
    consolidator = get_table_consolidator()
    
    # Find and filter tables
    tables = consolidator.find_tables(
        title="Balance Sheet",
        years=[2020, 2021, 2022],
        quarters=["Q1", "Q4"]
    )
    
    # Consolidate
    result = consolidator.consolidate(tables, transpose=True)
    
    # Export
    consolidator.export(result, format="both")
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from dataclasses import dataclass, field

from src.utils import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class ConsolidationResult:
    """Result of table consolidation."""
    
    dataframe: pd.DataFrame
    table_title: str
    periods_included: List[str] = field(default_factory=list)
    years: List[int] = field(default_factory=list)
    quarters: List[str] = field(default_factory=list)
    total_rows: int = 0
    total_columns: int = 0
    validation: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        return self.validation.get('status') == 'valid'
    
    def to_markdown(self) -> str:
        """Convert to markdown table with metadata header."""
        header = f"# {self.table_title}\n\n"
        
        if self.metadata.get('company_name'):
            header += f"**Company**: {self.metadata['company_name']}\n"
        if self.metadata.get('units'):
            header += f"**Units**: {self.metadata['units']}\n"
        if self.years:
            header += f"**Years**: {', '.join(map(str, self.years))}\n"
        if self.quarters:
            header += f"**Quarters**: {', '.join(self.quarters)}\n"
        
        header += "\n"
        
        return header + self.dataframe.to_markdown(index=True)


class TableConsolidator:
    """
    Unified table consolidator for multi-period financial data.
    
    Combines the best of QuarterlyTableConsolidator and MultiYearTableConsolidator:
    - Hybrid search with fuzzy matching
    - Year/quarter filtering
    - Deduplication
    - Transpose option
    - Data validation
    - CSV/Excel export
    
    Follows singleton pattern consistent with other managers.
    """
    
    def __init__(self, vector_store=None, embedding_manager=None):
        """
        Initialize table consolidator.
        
        Args:
            vector_store: Vector store instance (lazy loaded if None)
            embedding_manager: Embedding manager (lazy loaded if None)
        """
        self._vector_store = vector_store
        self._embedding_manager = embedding_manager
        self.similarity_threshold = getattr(settings, 'TABLE_SIMILARITY_THRESHOLD', 0.6)
    
    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            from src.infrastructure.vectordb import get_vectordb_manager
            self._vector_store = get_vectordb_manager()
        return self._vector_store
    
    @property
    def embedding_manager(self):
        """Lazy load embedding manager."""
        if self._embedding_manager is None:
            from src.infrastructure.embeddings import get_embedding_manager
            self._embedding_manager = get_embedding_manager()
        return self._embedding_manager
    
    def find_tables(
        self,
        title: str,
        years: Optional[List[int]] = None,
        quarters: Optional[List[str]] = None,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find all tables matching title with optional year/quarter filtering.
        
        Uses hybrid search:
        1. Semantic similarity on title
        2. Fuzzy string matching
        3. Metadata filtering for years/quarters
        4. Deduplication
        
        Args:
            title: Table title to search for
            years: Optional list of years to filter (e.g., [2020, 2021, 2022])
            quarters: Optional list of quarters to filter (e.g., ["Q1", "Q4"])
            top_k: Maximum results to retrieve
            
        Returns:
            List of table dictionaries sorted by date
        """
        logger.info(f"Searching for tables: '{title}' (years={years}, quarters={quarters})")
        
        try:
            # Step 1: Semantic similarity search
            results = self.vector_store.search(query=title, top_k=top_k)
            
            candidates = []
            for result in results:
                metadata = result.metadata if hasattr(result, 'metadata') else {}
                if isinstance(metadata, dict):
                    pass  # Already a dict
                elif hasattr(metadata, 'model_dump'):
                    metadata = metadata.model_dump()
                elif hasattr(metadata, '__dict__'):
                    metadata = vars(metadata)
                
                # Get table title from metadata
                actual_title = (
                    metadata.get('table_title') or 
                    metadata.get('actual_table_title') or 
                    ''
                )
                
                if not actual_title:
                    continue
                
                # Step 2: Fuzzy matching on title
                fuzzy_score = self._fuzzy_match(title, actual_title)
                
                if fuzzy_score < self.similarity_threshold:
                    continue
                
                # Step 3: Year filtering
                year = metadata.get('year')
                if years and year not in years:
                    continue
                
                # Step 4: Quarter filtering
                quarter = metadata.get('quarter', '')
                if quarters:
                    quarter_upper = quarter.upper() if quarter else ''
                    if not any(q.upper() in quarter_upper or quarter_upper in q.upper() 
                              for q in quarters):
                        continue
                
                candidates.append({
                    'content': result.content if hasattr(result, 'content') else str(result),
                    'metadata': metadata,
                    'title': actual_title,
                    'year': year,
                    'quarter': quarter,
                    'source_doc': metadata.get('source_doc'),
                    'page_no': metadata.get('page_no'),
                    'score': result.score if hasattr(result, 'score') else 0,
                    'fuzzy_score': fuzzy_score
                })
            
            # Step 5: Deduplicate (keep best per year/quarter)
            unique_tables = self._deduplicate(candidates)
            
            # Step 6: Sort chronologically
            sorted_tables = sorted(
                unique_tables,
                key=lambda t: (t['year'] or 0, self._quarter_to_num(t['quarter']))
            )
            
            logger.info(f"Found {len(sorted_tables)} matching tables")
            return sorted_tables
            
        except Exception as e:
            logger.error(f"Error searching for tables: {e}", exc_info=True)
            return []
    
    def consolidate(
        self,
        tables: List[Dict[str, Any]],
        table_name: Optional[str] = None,
        transpose: bool = False
    ) -> ConsolidationResult:
        """
        Consolidate tables into unified structure.
        
        Merges tables horizontally:
        - Row headers stay the same (metrics)
        - Columns are added per period (dates)
        
        Args:
            tables: List of table dictionaries from find_tables()
            table_name: Name for consolidated table
            transpose: If True, dates become rows and metrics become columns
            
        Returns:
            ConsolidationResult with DataFrame and metadata
        """
        if not tables:
            return ConsolidationResult(
                dataframe=pd.DataFrame(),
                table_title=table_name or "No Data",
                validation={'status': 'error', 'message': 'No tables provided'}
            )
        
        table_name = table_name or tables[0].get('title', 'Consolidated Table')
        logger.info(f"Consolidating {len(tables)} tables for '{table_name}'")
        
        dataframes = []
        period_labels = []
        years_set = set()
        quarters_set = set()
        
        for table in tables:
            # Parse table content
            df = self._parse_table_content(table['content'])
            
            if df.empty:
                continue
            
            year = table.get('year')
            quarter = table.get('quarter', '')
            
            if year:
                years_set.add(year)
            if quarter:
                quarters_set.add(quarter)
            
            # Get period date label
            date_str = self._get_period_date(year, quarter)
            period_labels.append(date_str)
            
            # Set first column as index (row headers / metrics)
            if len(df.columns) > 0:
                df = df.set_index(df.columns[0])
            
            # Rename columns with date
            df.columns = [f"{col} ({date_str})" if col else date_str for col in df.columns]
            
            dataframes.append(df)
        
        if not dataframes:
            return ConsolidationResult(
                dataframe=pd.DataFrame(),
                table_title=table_name,
                validation={'status': 'error', 'message': 'No valid tables to consolidate'}
            )
        
        # Merge all DataFrames (outer join to keep all rows)
        consolidated = dataframes[0]
        for df in dataframes[1:]:
            consolidated = consolidated.join(df, how='outer')
        
        # Fill missing values
        consolidated = consolidated.fillna('N/A')
        
        # Transpose if requested (dates as rows, metrics as columns)
        if transpose:
            consolidated = consolidated.T
            consolidated.index.name = 'Period'
        else:
            consolidated.index.name = 'Metric'
        
        # Validate data integrity
        validation = self._validate(tables, consolidated)
        
        # Extract metadata
        metadata = self._extract_metadata(tables)
        
        return ConsolidationResult(
            dataframe=consolidated,
            table_title=table_name,
            periods_included=sorted(period_labels),
            years=sorted(years_set),
            quarters=sorted(quarters_set),
            total_rows=len(consolidated),
            total_columns=len(consolidated.columns),
            validation=validation,
            metadata=metadata
        )
    
    def export(
        self,
        result: ConsolidationResult,
        output_dir: Optional[str] = None,
        format: str = "both"
    ) -> Dict[str, str]:
        """
        Export consolidated table to CSV and/or Excel.
        
        Args:
            result: ConsolidationResult from consolidate()
            output_dir: Output directory (defaults to settings.OUTPUT_DIR)
            format: "csv", "excel", or "both"
            
        Returns:
            Dictionary with export paths
        """
        if result.dataframe.empty:
            logger.warning("Empty DataFrame, nothing to export")
            return {}
        
        output_dir = Path(output_dir or getattr(settings, 'OUTPUT_DIR', 'outputs/consolidated_tables'))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y_%m")
        safe_name = result.table_title.replace(' ', '_').replace('/', '_').lower()
        
        year_range = ""
        if result.years:
            if len(result.years) == 1:
                year_range = f"_{result.years[0]}"
            else:
                year_range = f"_{result.years[0]}_{result.years[-1]}"
        
        base_filename = f"{safe_name}{year_range}_{timestamp}"
        
        export_paths = {}
        
        # Export CSV
        if format in ["csv", "both"]:
            csv_path = output_dir / f"{base_filename}.csv"
            result.dataframe.to_csv(csv_path)
            export_paths['csv'] = str(csv_path)
            logger.info(f"Exported CSV: {csv_path}")
        
        # Export Excel
        if format in ["excel", "both"]:
            excel_path = output_dir / f"{base_filename}.xlsx"
            result.dataframe.to_excel(excel_path, engine='openpyxl')
            export_paths['excel'] = str(excel_path)
            logger.info(f"Exported Excel: {excel_path}")
        
        return export_paths
    
    def _parse_table_content(self, content: str) -> pd.DataFrame:
        """Parse markdown/text table to DataFrame with currency cleaning."""
        from src.utils.table_utils import parse_markdown_table
        return parse_markdown_table(content, handle_colon_separator=True)
    
    def _fuzzy_match(self, query: str, target: str) -> float:
        """Calculate fuzzy string similarity (0.0-1.0)."""
        return SequenceMatcher(None, query.lower(), target.lower()).ratio()
    
    def _deduplicate(self, candidates: List[Dict]) -> List[Dict]:
        """Keep best scoring table per (year, quarter)."""
        groups = {}
        for candidate in candidates:
            key = (candidate['year'], candidate['quarter'])
            
            if key not in groups:
                groups[key] = candidate
            else:
                current_score = candidate.get('fuzzy_score', 0) + candidate.get('score', 0)
                existing_score = groups[key].get('fuzzy_score', 0) + groups[key].get('score', 0)
                if current_score > existing_score:
                    groups[key] = candidate
        
        return list(groups.values())
    
    def _get_period_date(self, year: Optional[int], quarter: Optional[str]) -> str:
        """Get standard period end date (YYYY-MM-DD)."""
        if not year:
            return "Unknown"
        
        if not quarter:
            return f"{year}-12-31"
        
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
            return f"{year}-12-31"
    
    def _quarter_to_num(self, quarter: Optional[str]) -> int:
        """Convert quarter to number for sorting."""
        if not quarter:
            return 5
        
        quarter = quarter.upper()
        if 'Q1' in quarter:
            return 1
        elif 'Q2' in quarter:
            return 2
        elif 'Q3' in quarter:
            return 3
        elif 'Q4' in quarter or '10K' in quarter:
            return 4
        return 5
    
    def _validate(
        self,
        original_tables: List[Dict],
        consolidated: pd.DataFrame
    ) -> Dict[str, Any]:
        """Validate data integrity."""
        validation = {
            'status': 'valid',
            'errors': [],
            'warnings': [],
            'stats': {
                'tables_processed': len(original_tables),
                'final_rows': len(consolidated),
                'final_columns': len(consolidated.columns)
            }
        }
        
        if consolidated.empty:
            validation['status'] = 'error'
            validation['errors'].append('Consolidated table is empty')
        
        return validation
    
    def _extract_metadata(self, tables: List[Dict]) -> Dict[str, Any]:
        """Extract common metadata from tables."""
        if not tables:
            return {}
        
        first_meta = tables[0].get('metadata', {})
        
        return {
            'company_ticker': first_meta.get('company_ticker'),
            'company_name': first_meta.get('company_name'),
            'statement_type': first_meta.get('statement_type'),
            'units': first_meta.get('units'),
            'currency': first_meta.get('currency')
        }


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_table_consolidator: Optional[TableConsolidator] = None


def get_table_consolidator(
    vector_store=None,
    embedding_manager=None
) -> TableConsolidator:
    """
    Get or create global table consolidator instance.
    
    Follows same pattern as:
    - get_vectordb_manager()
    - get_embedding_manager()
    - get_llm_manager()
    
    Args:
        vector_store: Optional vector store (lazy loaded if None)
        embedding_manager: Optional embedding manager (lazy loaded if None)
        
    Returns:
        TableConsolidator singleton instance
    """
    global _table_consolidator
    
    if _table_consolidator is None or vector_store is not None:
        _table_consolidator = TableConsolidator(vector_store, embedding_manager)
    
    return _table_consolidator


def reset_table_consolidator() -> None:
    """Reset the consolidator singleton (for testing)."""
    global _table_consolidator
    _table_consolidator = None
