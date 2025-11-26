"""
Multi-level embedding generator for financial tables.
Creates embeddings at table, row, and cell levels with complete metadata.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
from models.enhanced_schemas import (
    EnhancedFinancialTable, EnhancedDocument, RowHeader, 
    ColumnHeader, DataCell, Period
)


class MultiLevelEmbeddingGenerator:
    """Generate embeddings at table, row, and cell levels."""
    
    def __init__(self, embedding_model=None):
        """
        Initialize with embedding model.
        
        Args:
            embedding_model: Model for generating embeddings (sentence-transformers, OpenAI, etc.)
        """
        self.embedding_model = embedding_model
        self.embedding_cache = {}
    
    def generate_document_embeddings(
        self, 
        document: EnhancedDocument,
        levels: List[str] = ["table", "row"]
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for entire document at specified levels.
        
        Args:
            document: Enhanced document with tables
            levels: Which levels to generate ("table", "row", "cell")
        
        Returns:
            List of embedding objects with text, vector, and metadata
        """
        all_embeddings = []
        
        for table in document.tables:
            if "table" in levels:
                table_embeddings = self.generate_table_level_embeddings(table, document.metadata)
                all_embeddings.extend(table_embeddings)
            
            if "row" in levels:
                row_embeddings = self.generate_row_level_embeddings(table, document.metadata)
                all_embeddings.extend(row_embeddings)
            
            if "cell" in levels:
                cell_embeddings = self.generate_cell_level_embeddings(table, document.metadata)
                all_embeddings.extend(cell_embeddings)
        
        return all_embeddings
    
    def generate_table_level_embeddings(
        self, 
        table: EnhancedFinancialTable,
        doc_metadata: Any
    ) -> List[Dict[str, Any]]:
        """
        Generate table-level embedding.
        
        Level 1: Entire table summarized
        Use case: "Find all income statements for Q1 2025"
        """
        # Build comprehensive text representation
        text_parts = []
        
        # Document context
        text_parts.append(f"Document: {doc_metadata.filename}")
        if doc_metadata.company_name:
            text_parts.append(f"Company: {doc_metadata.company_name}")
        if doc_metadata.filing_date:
            text_parts.append(f"Filing Date: {doc_metadata.filing_date}")
        if doc_metadata.document_type:
            text_parts.append(f"Document Type: {doc_metadata.document_type}")
        
        # Table information
        text_parts.append(f"Table Type: {table.table_type}")
        text_parts.append(f"Title: {table.original_title}")
        
        # Periods
        if table.periods:
            period_labels = [p.display_label for p in table.periods]
            text_parts.append(f"Periods: {', '.join(period_labels)}")
        
        # Key row items (top-level only)
        top_level_rows = [rh.text for rh in table.row_headers if rh.indent_level == 0]
        if top_level_rows:
            text_parts.append(f"Key Items: {', '.join(top_level_rows[:10])}")
        
        # Summary
        text_parts.append(f"Summary: {table.table_type} with {len(table.row_headers)} line items across {len(table.column_headers)} periods")
        
        text = "\n".join(text_parts)
        
        # Generate embedding
        vector = self._get_embedding(text)
        
        # Build metadata
        metadata = self._build_table_metadata(table, doc_metadata)
        metadata["embedding_level"] = "table"
        metadata["text_content"] = text
        
        return [{
            "id": f"{doc_metadata.file_hash}_{table.table_id}_table",
            "text": text,
            "vector": vector,
            "metadata": metadata
        }]
    
    def generate_row_level_embeddings(
        self,
        table: EnhancedFinancialTable,
        doc_metadata: Any
    ) -> List[Dict[str, Any]]:
        """
        Generate row-level embeddings.
        
        Level 2: Individual row/line item
        Use case: "Show me net revenues across all documents"
        """
        embeddings = []
        
        for row_header in table.row_headers:
            # Build text representation
            text_parts = []
            
            # Document context
            text_parts.append(f"Document: {doc_metadata.filename}")
            if doc_metadata.company_name:
                text_parts.append(f"Company: {doc_metadata.company_name}")
            
            # Table context
            text_parts.append(f"Table: {table.original_title}")
            text_parts.append(f"Table Type: {table.table_type}")
            
            # Row information
            text_parts.append(f"Row: {row_header.text}")
            if row_header.canonical_label:
                text_parts.append(f"Canonical Label: {row_header.canonical_label}")
            
            # Hierarchy
            if row_header.parent_row:
                text_parts.append(f"Parent: {row_header.parent_row}")
            if row_header.indent_level > 0:
                text_parts.append(f"Indent Level: {row_header.indent_level}")
            
            # Values across periods
            row_cells = [cell for cell in table.data_cells if cell.row_header == row_header.text]
            if row_cells:
                value_strs = []
                for cell in row_cells:
                    if cell.parsed_value is not None:
                        value_str = f"{cell.column_header}: {cell.display_value or cell.raw_text}"
                        value_strs.append(value_str)
                
                if value_strs:
                    text_parts.append(f"Values: {', '.join(value_strs)}")
            
            # Data type
            if row_cells and row_cells[0].data_type:
                text_parts.append(f"Data Type: {row_cells[0].data_type}")
            
            text = "\n".join(text_parts)
            
            # Generate embedding
            vector = self._get_embedding(text)
            
            # Build metadata
            metadata = self._build_row_metadata(table, doc_metadata, row_header)
            metadata["embedding_level"] = "row"
            metadata["text_content"] = text
            
            embeddings.append({
                "id": f"{doc_metadata.file_hash}_{table.table_id}_row_{row_header.row_index}",
                "text": text,
                "vector": vector,
                "metadata": metadata
            })
        
        return embeddings
    
    def generate_cell_level_embeddings(
        self,
        table: EnhancedFinancialTable,
        doc_metadata: Any
    ) -> List[Dict[str, Any]]:
        """
        Generate cell-level embeddings.
        
        Level 3: Individual cell value
        Use case: "Find all values greater than $1 billion in Q1 2025"
        """
        embeddings = []
        
        for cell in table.data_cells:
            # Skip empty cells
            if cell.parsed_value is None:
                continue
            
            # Build text representation
            text_parts = []
            
            # Document context
            text_parts.append(f"Document: {doc_metadata.filename}")
            if doc_metadata.company_name:
                text_parts.append(f"Company: {doc_metadata.company_name}")
            
            # Table context
            text_parts.append(f"Table: {table.original_title}")
            
            # Cell location
            text_parts.append(f"Row: {cell.row_header}")
            text_parts.append(f"Column: {cell.column_header}")
            
            # Value
            text_parts.append(f"Value: {cell.display_value or cell.raw_text}")
            if cell.base_value:
                text_parts.append(f"Base Value: ${cell.base_value:,.0f}")
            
            # Period
            matching_period = next((p for p in table.periods if p.display_label in cell.column_header), None)
            if matching_period:
                text_parts.append(f"Period: {matching_period.display_label}")
            
            # Data type
            text_parts.append(f"Data Type: {cell.data_type}")
            
            text = "\n".join(text_parts)
            
            # Generate embedding
            vector = self._get_embedding(text)
            
            # Build metadata
            metadata = self._build_cell_metadata(table, doc_metadata, cell)
            metadata["embedding_level"] = "cell"
            metadata["text_content"] = text
            
            embeddings.append({
                "id": f"{doc_metadata.file_hash}_{table.table_id}_cell_{cell.row_index}_{cell.column_index}",
                "text": text,
                "vector": vector,
                "metadata": metadata
            })
        
        return embeddings
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text with caching.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        # Create cache key
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Check cache
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]
        
        # Generate embedding
        if self.embedding_model:
            vector = self.embedding_model.encode(text).tolist()
        else:
            # Placeholder for development
            import numpy as np
            vector = np.random.rand(384).tolist()
        
        # Cache it
        self.embedding_cache[text_hash] = vector
        
        return vector
    
    def _build_table_metadata(
        self,
        table: EnhancedFinancialTable,
        doc_metadata: Any
    ) -> Dict[str, Any]:
        """Build complete metadata for table-level embedding."""
        metadata = {
            # Document identification
            "document_id": doc_metadata.file_hash[:12],
            "document_name": doc_metadata.filename,
            "filename": doc_metadata.filename,
            
            # Company information
            "company": doc_metadata.company_name or "Unknown",
            
            # Filing information
            "filing_type": doc_metadata.document_type or "Unknown",
            "filing_date": str(doc_metadata.filing_date) if doc_metadata.filing_date else None,
            
            # Table identification
            "table_id": table.table_id,
            "table_type": table.table_type,
            "table_title": table.original_title,
            "canonical_title": table.canonical_title,
            "page_number": table.metadata.get("page_no"),
            
            # Period information (first period)
            "periods": [p.display_label for p in table.periods] if table.periods else [],
            
            # Embedding metadata
            "embedding_date": datetime.utcnow().isoformat()
        }
        
        # Add first period details if available
        if table.periods:
            first_period = table.periods[0]
            metadata.update({
                "period_type": first_period.period_type,
                "period_year": first_period.year,
                "period_quarter": first_period.quarter,
                "period_label": first_period.display_label
            })
        
        return metadata
    
    def _build_row_metadata(
        self,
        table: EnhancedFinancialTable,
        doc_metadata: Any,
        row_header: RowHeader
    ) -> Dict[str, Any]:
        """Build complete metadata for row-level embedding."""
        # Start with table metadata
        metadata = self._build_table_metadata(table, doc_metadata)
        
        # Add row-specific metadata
        metadata.update({
            "row_id": f"row_{row_header.row_index}",
            "row_label": row_header.text,
            "canonical_label": row_header.canonical_label,
            "indent_level": row_header.indent_level,
            "is_subtotal": row_header.is_subtotal,
            "is_total": row_header.is_total,
            "parent_row": row_header.parent_row
        })
        
        return metadata
    
    def _build_cell_metadata(
        self,
        table: EnhancedFinancialTable,
        doc_metadata: Any,
        cell: DataCell
    ) -> Dict[str, Any]:
        """Build complete metadata for cell-level embedding."""
        # Start with table metadata
        metadata = self._build_table_metadata(table, doc_metadata)
        
        # Add cell-specific metadata
        metadata.update({
            "row_label": cell.row_header,
            "column_label": cell.column_header,
            "value_numeric": cell.base_value,
            "value_display": cell.display_value or cell.raw_text,
            "data_type": cell.data_type,
            "units": cell.units
        })
        
        return metadata


def get_embedding_generator(embedding_model=None):
    """Get singleton embedding generator."""
    global _embedding_generator
    if '_embedding_generator' not in globals():
        _embedding_generator = MultiLevelEmbeddingGenerator(embedding_model)
    return _embedding_generator
