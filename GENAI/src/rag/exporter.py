"""
RAG Query Exporter

Handles exporting RAG query results to:
- CSV/Excel (retrieved table chunks)
- Text logs (query + answer + sources)
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import pandas as pd
import re

from src.models import RAGResponse, SearchResult
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAGExporter:
    """Export RAG query results to files."""
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize exporter.
        
        Args:
            output_dir: Override default output directory
        """
        self.output_dir = Path(output_dir or settings.RAG_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_query_results(
        self,
        query: str,
        response: RAGResponse,
        retrieved_chunks: List[SearchResult],
        session_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Export RAG query results.
        
        Args:
            query: User question
            response: RAG response object
            retrieved_chunks: List of retrieved SearchResult objects
            session_id: Optional session identifier for grouping
            
        Returns:
            Dictionary with paths: {'tables_csv': '...', 'tables_excel': '...', 'log': '...'}
        """
        export_paths = {}
        
        # Generate base filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = self._sanitize_filename(query)
        
        if session_id:
            # Session-based export
            session_dir = self.output_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            base_path = session_dir / f"query_{timestamp}"
        else:
            # Standalone export
            base_path = self.output_dir / f"{safe_query}_{timestamp}"
        
        # 1. Export tables (priority)
        if settings.SAVE_RAG_TABLES and retrieved_chunks:
            table_paths = self._export_tables(retrieved_chunks, base_path)
            export_paths.update(table_paths)
        
        # 2. Export text log
        if settings.SAVE_RAG_RESPONSES:
            log_path = self._export_log(
                query=query,
                response=response,
                retrieved_chunks=retrieved_chunks,
                base_path=base_path,
                table_paths=export_paths
            )
            export_paths['log'] = log_path
        
        return export_paths
    
    def _export_tables(
        self,
        retrieved_chunks: List[SearchResult],
        base_path: Path
    ) -> Dict[str, str]:
        """
        Export retrieved table chunks to CSV/Excel.
        
        Args:
            retrieved_chunks: List of SearchResult objects
            base_path: Base file path (without extension)
            
        Returns:
            Dictionary with paths {'tables_csv': '...', 'tables_excel': '...'}
        """
        export_paths = {}
        
        try:
            # Parse and consolidate tables
            df = self._consolidate_retrieved_tables(retrieved_chunks)
            
            if df.empty:
                logger.warning("No table data to export")
                return export_paths
            
            # Export CSV
            if settings.EXPORT_FORMAT in ["csv", "both"]:
                csv_path = f"{base_path}_tables.csv"
                df.to_csv(csv_path, index=False)
                export_paths['tables_csv'] = csv_path
                logger.info(f"Exported tables to CSV: {csv_path}")
            
            # Export Excel
            if settings.EXPORT_FORMAT in ["excel", "both"]:
                excel_path = f"{base_path}_tables.xlsx"
                df.to_excel(excel_path, index=False, engine='openpyxl')
                export_paths['tables_excel'] = excel_path
                logger.info(f"Exported tables to Excel: {excel_path}")
        
        except Exception as e:
            logger.error(f"Failed to export tables: {e}")
        
        return export_paths
    
    def _consolidate_retrieved_tables(
        self,
        retrieved_chunks: List[SearchResult]
    ) -> pd.DataFrame:
        """
        Consolidate retrieved table chunks into single DataFrame.
        
        Args:
            retrieved_chunks: List of SearchResult objects
            
        Returns:
            Consolidated DataFrame
        """
        all_dataframes = []
        
        for i, chunk in enumerate(retrieved_chunks, 1):
            try:
                # Parse markdown table from content
                df = self._parse_markdown_table(chunk.content)
                
                if not df.empty:
                    # Add source columns
                    # Get or generate table_id
                    table_id = chunk.metadata.table_id
                    if not table_id:
                        doc = chunk.metadata.source_doc or 'unknown'
                        page = chunk.metadata.page_no or 0
                        table_id = f"{doc}_p{page}_{i}"

                    df['_table_id'] = table_id
                    df['_source'] = chunk.metadata.source_doc
                    df['_page'] = chunk.metadata.page_no
                    df['_table'] = chunk.metadata.table_title
                    df['_score'] = chunk.score
                    df['_rank'] = i
                    
                    all_dataframes.append(df)
            
            except Exception as e:
                logger.warning(f"Failed to parse chunk {i}: {e}")
                continue
        
        if not all_dataframes:
            return pd.DataFrame()
        
        # Concatenate all tables
        consolidated = pd.concat(all_dataframes, ignore_index=True)
        
        # Reorder columns: metadata last
        metadata_cols = ['_rank', '_score', '_source', '_page', '_table']
        data_cols = [c for c in consolidated.columns if c not in metadata_cols]
        consolidated = consolidated[data_cols + metadata_cols]
        
        return consolidated
    
    def _parse_markdown_table(self, markdown: str) -> pd.DataFrame:
        """Parse markdown table to DataFrame."""
        try:
            lines = [l.strip() for l in markdown.split('\n') if l.strip()]
            
            # Remove separator lines (|---|---|)
            lines = [l for l in lines if not all(c in '|-: ' for c in l)]
            
            if not lines:
                return pd.DataFrame()
            
            # Parse header
            header_line = lines[0]
            headers = [h.strip() for h in header_line.split('|') if h.strip()]
            
            # Parse data rows
            data_rows = []
            for line in lines[1:]:
                if '|' in line:
                    cells = [c.strip() for c in line.split('|') if c.strip()]
                    if cells:
                        data_rows.append(cells)
            
            if not data_rows:
                return pd.DataFrame()
            
            # Create DataFrame
            df = pd.DataFrame(data_rows, columns=headers)
            return df
        
        except Exception as e:
            logger.warning(f"Failed to parse markdown table: {e}")
            return pd.DataFrame()
    
    def _export_log(
        self,
        query: str,
        response: RAGResponse,
        retrieved_chunks: List[SearchResult],
        base_path: Path,
        table_paths: Dict[str, str]
    ) -> str:
        """
        Export text log with query, answer, and sources.
        
        Args:
            query: User question
            response: RAG response
            retrieved_chunks: Retrieved chunks
            base_path: Base file path
            table_paths: Paths to exported tables
            
        Returns:
            Log file path
        """
        log_path = f"{base_path}_log.txt"
        
        try:
            with open(log_path, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("RAG QUERY LOG\n")
                f.write("=" * 80 + "\n\n")
                
                # Timestamp
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Query
                f.write(f"QUERY:\n{query}\n\n")
                
                # Answer
                f.write(f"ANSWER:\n{response.answer}\n\n")
                
                # Sources
                f.write(f"SOURCES ({len(retrieved_chunks)} chunks retrieved):\n")
                for i, chunk in enumerate(retrieved_chunks, 1):
                    meta = chunk.metadata
                    f.write(f"  {i}. {meta.source_doc}, Page {meta.page_no}, \"{meta.table_title}\"\n")
                    f.write(f"     Score: {chunk.score:.4f}\n")
                
                # Metadata
                f.write(f"\nMETADATA:\n")
                f.write(f"  Confidence: {response.confidence:.2f}\n")
                f.write(f"  Retrieved Chunks: {response.retrieved_chunks}\n")
                
                # Table file references
                if table_paths:
                    f.write(f"\nEXPORTED TABLES:\n")
                    for format_type, path in table_paths.items():
                        f.write(f"  {format_type}: {path}\n")
                
                f.write("\n" + "=" * 80 + "\n")
            
            logger.info(f"Exported log: {log_path}")
            return log_path
        
        except Exception as e:
            logger.error(f"Failed to export log: {e}")
            return ""
    
    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """
        Sanitize text for use in filename.
        
        Args:
            text: Input text
            max_length: Maximum filename length
            
        Returns:
            Safe filename string
        """
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces and special chars with underscore
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '_', text)
        
        # Truncate
        text = text[:max_length]
        
        # Remove leading/trailing underscores
        text = text.strip('_')
        
        return text or "query"
