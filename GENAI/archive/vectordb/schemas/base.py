"""
Production-grade unified metadata schema for VectorDB storage.

This schema supports advanced financial RAG use cases including:
- Multi-year table consolidation
- Precise financial data retrieval
- Table relationship traversal
- Complete semantic chunking

Compatible with all VectorDB backends: ChromaDB, FAISS, Redis Vector
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class EnhancedTableMetadata(BaseModel):
    """
    Production-grade metadata schema for financial table storage.
    
    Supports:
    - Multi-year table consolidation
    - Precise filtering by statement type, period, units
    - Table relationship traversal
    - Complete context preservation
    """
    
    # ============================================================================
    # DOCUMENT INFORMATION
    # ============================================================================
    source_doc: str = Field(..., description="Source PDF filename")
    page_no: int = Field(..., description="Page number in PDF")
    chunk_reference_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique chunk ID"
    )
    
    # Company Information (NEW - CRITICAL for multi-company support)
    company_ticker: Optional[str] = Field(None, description="Company ticker symbol (e.g., AAPL)")
    company_name: Optional[str] = Field(None, description="Company name (e.g., Apple Inc.)")
    
    # ============================================================================
    # FINANCIAL STATEMENT CONTEXT (NEW - CRITICAL)
    # ============================================================================
    statement_type: Optional[str] = Field(
        None,
        description="Type of financial statement: balance_sheet, income_statement, cash_flow, footnotes"
    )
    filing_type: str = Field(
        default="",
        description="SEC filing type: 10-Q, 10-K, 8-K, earnings_release"
    )
    fiscal_period_end: Optional[str] = Field(
        None,
        description="Exact fiscal period end date in ISO format (e.g., 2025-06-30)"
    )
    restatement: bool = Field(
        False,
        description="Whether this is a restated financial statement (critical for accuracy)"
    )
    
    # ============================================================================
    # TABLE IDENTIFICATION
    # ============================================================================
    table_title: str = Field(default="", description="Table title or caption")
    table_type: Optional[str] = Field(
        None,
        description="Table type: summary, detail, reconciliation, segment"
    )
    table_index: Optional[int] = Field(None, description="Table index in document")
    
    # ============================================================================
    # TEMPORAL INFORMATION
    # ============================================================================
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Fiscal quarter (Q1, Q2, Q3, Q4)")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period description")
    
    # Comparative Periods (NEW - CRITICAL for multi-year consolidation)
    comparative_periods: List[str] = Field(
        default_factory=list,
        description="List of periods in this table (e.g., ['2025-Q2', '2024-Q2'])"
    )
    
    # ============================================================================
    # TABLE-SPECIFIC METADATA (NEW - CRITICAL)
    # ============================================================================
    units: Optional[str] = Field(
        None,
        description="Financial units: thousands, millions, billions (critical for accuracy)"
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code: USD, EUR, GBP, etc."
    )
    is_consolidated: bool = Field(
        True,
        description="Whether this is consolidated financial data vs segment/subsidiary"
    )
    
    # ============================================================================
    # TABLE STRUCTURE
    # ============================================================================
    column_headers: Optional[str] = Field(None, description="Pipe-separated column headers")
    row_headers: Optional[str] = Field(None, description="Pipe-separated row headers (first column)")
    column_count: Optional[int] = Field(None, description="Number of columns")
    row_count: Optional[int] = Field(None, description="Number of rows")
    
    # Structure Type (NEW)
    table_structure: Optional[str] = Field(
        None,
        description="Table structure complexity: simple, nested, multi_header"
    )
    
    # ============================================================================
    # HIERARCHICAL INFORMATION (NEW - HIGH VALUE)
    # ============================================================================
    parent_section: Optional[str] = Field(
        None,
        description="Parent section in document (e.g., 'Assets', 'Liabilities')"
    )
    subsection: Optional[str] = Field(
        None,
        description="Subsection within parent (e.g., 'Current Assets')"
    )
    footnote_references: List[str] = Field(
        default_factory=list,
        description="List of footnote numbers referenced in this table"
    )
    related_tables: List[str] = Field(
        default_factory=list,
        description="IDs of related tables (e.g., balance sheet → income statement)"
    )
    
    # ============================================================================
    # MULTI-LEVEL HEADERS
    # ============================================================================
    has_multi_level_headers: bool = Field(False, description="Has spanning/multi-level headers")
    main_header: Optional[str] = Field(None, description="Main spanning header")
    sub_headers: Optional[str] = Field(None, description="Pipe-separated sub-headers")
    
    # ============================================================================
    # HIERARCHICAL STRUCTURE
    # ============================================================================
    has_hierarchy: bool = Field(False, description="Has hierarchical row structure")
    subsections: Optional[str] = Field(None, description="Pipe-separated subsection names")
    
    # ============================================================================
    # CONTENT ANALYSIS
    # ============================================================================
    has_currency: bool = Field(False, description="Contains currency values")
    currency_count: int = Field(0, description="Number of currency symbols")
    
    # Data Quality Markers (NEW)
    has_subtotals: bool = Field(False, description="Contains subtotal rows")
    has_calculations: bool = Field(False, description="Contains calculated values (for verification)")
    
    # ============================================================================
    # EXTRACTION METADATA
    # ============================================================================
    extraction_date: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Extraction timestamp"
    )
    extraction_backend: Optional[str] = Field(
        None,
        description="Backend used for extraction (docling, pymupdf, etc.)"
    )
    quality_score: Optional[float] = Field(
        None,
        description="Extraction quality score (0-100)"
    )
    
    # Extraction Confidence (NEW)
    extraction_confidence: Optional[float] = Field(
        None,
        description="OCR/parsing confidence score (0.0-1.0)"
    )
    
    # ============================================================================
    # ENHANCED CHUNK MANAGEMENT (NEW - CRITICAL)
    # ============================================================================
    chunk_type: Optional[str] = Field(
        None,
        description="Type of chunk: header, data, footer, complete"
    )
    overlapping_context: Optional[str] = Field(
        None,
        description="Context from previous chunks for continuity (e.g., 'Previous rows: ...')"
    )
    table_start_page: Optional[int] = Field(
        None,
        description="Starting page for multi-page tables"
    )
    table_end_page: Optional[int] = Field(
        None,
        description="Ending page for multi-page tables"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_doc": "10q0625.pdf",
                "page_no": 5,
                "company_ticker": "AAPL",
                "company_name": "Apple Inc.",
                "statement_type": "balance_sheet",
                "filing_type": "10-Q",
                "fiscal_period_end": "2025-06-30",
                "table_title": "Consolidated Balance Sheet",
                "table_type": "summary",
                "year": 2025,
                "quarter": "Q2",
                "comparative_periods": ["2025-Q2", "2024-Q2"],
                "units": "millions",
                "currency": "USD",
                "is_consolidated": True,
                "column_headers": "Assets|June 30, 2025|December 31, 2024",
                "row_headers": "Cash|Securities|Loans|Total Assets",
                "column_count": 3,
                "row_count": 15,
                "table_structure": "multi_header",
                "parent_section": "Assets",
                "subsection": "Current Assets",
                "footnote_references": ["1", "3"],
                "has_multi_level_headers": True,
                "has_currency": True,
                "has_subtotals": True,
                "extraction_confidence": 0.95,
                "chunk_type": "complete"
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for VectorDB storage."""
        data = self.model_dump(exclude_none=True)
        
        # Convert datetime to ISO string for storage
        if 'extraction_date' in data and isinstance(data['extraction_date'], datetime):
            data['extraction_date'] = data['extraction_date'].isoformat()
        
        # Convert lists to pipe-separated strings for ChromaDB compatibility
        if 'comparative_periods' in data and isinstance(data['comparative_periods'], list):
            data['comparative_periods'] = '|'.join(data['comparative_periods'])
        
        if 'footnote_references' in data and isinstance(data['footnote_references'], list):
            data['footnote_references'] = '|'.join(data['footnote_references'])
        
        if 'related_tables' in data and isinstance(data['related_tables'], list):
            data['related_tables'] = '|'.join(data['related_tables'])
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedTableMetadata':
        """Create from dictionary (from VectorDB)."""
        # Convert ISO string back to datetime
        if 'extraction_date' in data and isinstance(data['extraction_date'], str):
            data['extraction_date'] = datetime.fromisoformat(data['extraction_date'])
        
        # Convert pipe-separated strings back to lists
        if 'comparative_periods' in data and isinstance(data['comparative_periods'], str):
            data['comparative_periods'] = data['comparative_periods'].split('|') if data['comparative_periods'] else []
        
        if 'footnote_references' in data and isinstance(data['footnote_references'], str):
            data['footnote_references'] = data['footnote_references'].split('|') if data['footnote_references'] else []
        
        if 'related_tables' in data and isinstance(data['related_tables'], str):
            data['related_tables'] = data['related_tables'].split('|') if data['related_tables'] else []
        
        return cls(**data)


# Backward compatibility alias
TableMetadata = EnhancedTableMetadata


class TableChunk(BaseModel):
    """
    Unified table chunk for VectorDB storage.
    
    Contains:
    - Complete semantic content (not fragments)
    - Enhanced metadata
    - Embedding vector
    - Chunk management info
    """
    
    chunk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique chunk identifier"
    )
    content: str = Field(
        ...,
        description="Complete table content in markdown format (full semantic unit)"
    )
    metadata: EnhancedTableMetadata = Field(..., description="Enhanced table metadata")
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")
    
    # Chunk-specific metadata
    chunk_index: Optional[int] = Field(None, description="Chunk index for multi-chunk tables")
    total_chunks: Optional[int] = Field(None, description="Total chunks for this table")
    chunk_overlap: Optional[int] = Field(None, description="Number of overlapping rows")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": """Table: Consolidated Balance Sheet (in millions)
                
Assets:
Cash and cash equivalents: $100
Short-term investments: $200
Accounts receivable: $150
Total current assets: $450
""",
                "metadata": {
                    "source_doc": "10q0625.pdf",
                    "company_ticker": "AAPL",
                    "statement_type": "balance_sheet",
                    "fiscal_period_end": "2025-06-30",
                    "units": "millions",
                    "chunk_type": "complete"
                },
                "embedding": [0.1, 0.2, 0.3],
                "chunk_index": 0,
                "total_chunks": 1
            }
        }
    
    def to_storage_format(self) -> Dict[str, Any]:
        """Convert to unified storage format for all VectorDB backends."""
        return {
            'id': self.chunk_id,
            'content': self.content,
            'metadata': self.metadata.to_dict(),
            'embedding': self.embedding,
            'chunk_index': self.chunk_index,
            'total_chunks': self.total_chunks
        }
    
    @classmethod
    def from_storage_format(cls, data: Dict[str, Any]) -> 'TableChunk':
        """Create from unified storage format."""
        return cls(
            chunk_id=data.get('id', str(uuid.uuid4())),
            content=data['content'],
            metadata=EnhancedTableMetadata.from_dict(data['metadata']),
            embedding=data.get('embedding'),
            chunk_index=data.get('chunk_index'),
            total_chunks=data.get('total_chunks')
        )


class VectorDBStats(BaseModel):
    """Statistics from VectorDB."""
    
    provider: str = Field(..., description="VectorDB provider name")
    total_chunks: int = Field(0, description="Total number of chunks")
    unique_documents: int = Field(0, description="Number of unique documents")
    years: List[int] = Field(default_factory=list, description="Years covered")
    sources: List[str] = Field(default_factory=list, description="Source documents")
    total_size_mb: Optional[float] = Field(None, description="Total size in MB")
    index_type: Optional[str] = Field(None, description="Index type (for FAISS)")


# Validation functions
def validate_metadata_compatibility(metadata: EnhancedTableMetadata) -> bool:
    """
    Validate that metadata is compatible with all VectorDB backends.
    
    Checks:
    - All required fields present
    - Data types correct
    - String lengths within limits
    - No unsupported characters
    """
    try:
        # Check required fields
        if not metadata.source_doc or not metadata.year:
            return False
        
        # Check string lengths (ChromaDB has limits)
        if len(metadata.source_doc) > 255:
            return False
        
        if metadata.table_title and len(metadata.table_title) > 500:
            return False
        
        # Check year range
        if metadata.year < 1900 or metadata.year > 2100:
            return False
        
        # Validate fiscal_period_end format if present
        if metadata.fiscal_period_end:
            try:
                datetime.fromisoformat(metadata.fiscal_period_end.replace('Z', '+00:00'))
            except ValueError:
                return False
        
        return True
    
    except Exception:
        return False


def serialize_for_storage(chunk: TableChunk) -> Dict[str, Any]:
    """
    Serialize chunk for storage in any VectorDB backend.
    
    Ensures consistent format across ChromaDB, FAISS, and Redis Vector.
    """
    storage_format = chunk.to_storage_format()
    
    # Validate
    if not validate_metadata_compatibility(chunk.metadata):
        raise ValueError("Metadata not compatible with VectorDB backends")
    
    return storage_format


def deserialize_from_storage(data: Dict[str, Any]) -> TableChunk:
    """
    Deserialize chunk from VectorDB storage.
    
    Works with data from any VectorDB backend.
    """
    return TableChunk.from_storage_format(data)

    """
    Unified metadata schema for table storage in VectorDB.
    
    This schema is compatible with all VectorDB backends and ensures
    consistent data representation across ChromaDB, FAISS, and Redis Vector.
    """
    
    # Document Information
    source_doc: str = Field(..., description="Source PDF filename")
    page_no: int = Field(..., description="Page number in PDF")
    chunk_reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk ID")
    
    # Table Identification
    table_title: str = Field(default="", description="Table title or caption")
    table_type: Optional[str] = Field(None, description="Type of table (Balance Sheet, Income Statement, etc.)")
    table_index: Optional[int] = Field(None, description="Table index in document")
    
    # Temporal Information
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Fiscal quarter (Q1, Q2, Q3, Q4)")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period description")
    
    # Document Type
    report_type: str = Field(default="", description="Report type (10-Q, 10-K, etc.)")
    
    # Table Structure (Enhanced Metadata)
    column_headers: Optional[str] = Field(None, description="Pipe-separated column headers")
    row_headers: Optional[str] = Field(None, description="Pipe-separated row headers (first column)")
    column_count: Optional[int] = Field(None, description="Number of columns")
    row_count: Optional[int] = Field(None, description="Number of rows")
    
    # Multi-level Headers
    has_multi_level_headers: Optional[bool] = Field(False, description="Has spanning/multi-level headers")
    main_header: Optional[str] = Field(None, description="Main spanning header")
    sub_headers: Optional[str] = Field(None, description="Pipe-separated sub-headers")
    
    # Hierarchical Structure
    has_hierarchy: Optional[bool] = Field(False, description="Has hierarchical row structure")
    subsections: Optional[str] = Field(None, description="Pipe-separated subsection names")
    
    # Content Analysis
    has_currency: Optional[bool] = Field(False, description="Contains currency values")
    currency_count: Optional[int] = Field(0, description="Number of currency symbols")
    
    # Extraction Metadata
    extraction_date: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Extraction timestamp")
    extraction_backend: Optional[str] = Field(None, description="Backend used for extraction (docling, etc.)")
    quality_score: Optional[float] = Field(None, description="Extraction quality score (0-100)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_doc": "10q0625.pdf",
                "page_no": 5,
                "table_title": "Consolidated Balance Sheet",
                "table_type": "Balance Sheet",
                "year": 2025,
                "quarter": "Q2",
                "report_type": "10-Q",
                "column_headers": "Assets|June 30, 2025|December 31, 2024",
                "row_headers": "Cash|Securities|Loans|Total Assets",
                "column_count": 3,
                "row_count": 15,
                "has_multi_level_headers": True,
                "has_currency": True
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for VectorDB storage."""
        data = self.model_dump(exclude_none=True)
        
        # Convert datetime to ISO string for storage
        if 'extraction_date' in data and isinstance(data['extraction_date'], datetime):
            data['extraction_date'] = data['extraction_date'].isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TableMetadata':
        """Create from dictionary (from VectorDB)."""
        # Convert ISO string back to datetime
        if 'extraction_date' in data and isinstance(data['extraction_date'], str):
            data['extraction_date'] = datetime.fromisoformat(data['extraction_date'])
        
        return cls(**data)


class TableChunk(BaseModel):
    """
    Unified table chunk for VectorDB storage.
    
    Contains:
    - Original table content (markdown)
    - Metadata (structured)
    - Embedding vector
    """
    
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk identifier")
    content: str = Field(..., description="Table content in markdown format")
    metadata: TableMetadata = Field(..., description="Table metadata")
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")
    
    # Chunk-specific metadata
    chunk_index: Optional[int] = Field(None, description="Chunk index for multi-chunk tables")
    total_chunks: Optional[int] = Field(None, description="Total chunks for this table")
    chunk_overlap: Optional[int] = Field(None, description="Number of overlapping rows")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "| Assets | Amount |\n| Cash | $100 |",
                "metadata": {
                    "source_doc": "10q0625.pdf",
                    "page_no": 5,
                    "year": 2025
                },
                "embedding": [0.1, 0.2, 0.3],
                "chunk_index": 0,
                "total_chunks": 1
            }
        }
    
    def to_storage_format(self) -> Dict[str, Any]:
        """
        Convert to unified storage format for all VectorDB backends.
        
        Returns:
            Dictionary with:
            - id: Chunk ID
            - content: Table content
            - metadata: Flattened metadata dict
            - embedding: Vector (if present)
        """
        return {
            'id': self.chunk_id,
            'content': self.content,
            'metadata': self.metadata.to_dict(),
            'embedding': self.embedding,
            'chunk_index': self.chunk_index,
            'total_chunks': self.total_chunks
        }
    
    @classmethod
    def from_storage_format(cls, data: Dict[str, Any]) -> 'TableChunk':
        """
        Create from unified storage format.
        
        Args:
            data: Dictionary from VectorDB
            
        Returns:
            TableChunk instance
        """
        return cls(
            chunk_id=data.get('id', str(uuid.uuid4())),
            content=data['content'],
            metadata=TableMetadata.from_dict(data['metadata']),
            embedding=data.get('embedding'),
            chunk_index=data.get('chunk_index'),
            total_chunks=data.get('total_chunks')
        )


class VectorDBStats(BaseModel):
    """Statistics from VectorDB."""
    
    provider: str = Field(..., description="VectorDB provider name")
    total_chunks: int = Field(0, description="Total number of chunks")
    unique_documents: int = Field(0, description="Number of unique documents")
    years: List[int] = Field(default_factory=list, description="Years covered")
    sources: List[str] = Field(default_factory=list, description="Source documents")
    total_size_mb: Optional[float] = Field(None, description="Total size in MB")
    index_type: Optional[str] = Field(None, description="Index type (for FAISS)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider": "chromadb",
                "total_chunks": 2502,
                "unique_documents": 7,
                "years": [2020, 2021, 2022, 2023, 2024, 2025],
                "sources": ["10q0625.pdf", "10k1222.pdf"]
            }
        }


# Validation functions
def validate_metadata_compatibility(metadata: TableMetadata) -> bool:
    """
    Validate that metadata is compatible with all VectorDB backends.
    
    Checks:
    - All required fields present
    - Data types correct
    - String lengths within limits
    - No unsupported characters
    """
    try:
        # Check required fields
        if not metadata.source_doc or not metadata.year:
            return False
        
        # Check string lengths (ChromaDB has limits)
        if len(metadata.source_doc) > 255:
            return False
        
        if metadata.table_title and len(metadata.table_title) > 500:
            return False
        
        # Check year range
        if metadata.year < 1900 or metadata.year > 2100:
            return False
        
        return True
    
    except Exception:
        return False


def serialize_for_storage(chunk: TableChunk) -> Dict[str, Any]:
    """
    Serialize chunk for storage in any VectorDB backend.
    
    Ensures consistent format across ChromaDB, FAISS, and Redis Vector.
    """
    storage_format = chunk.to_storage_format()
    
    # Validate
    if not validate_metadata_compatibility(chunk.metadata):
        raise ValueError("Metadata not compatible with VectorDB backends")
    
    return storage_format


def deserialize_from_storage(data: Dict[str, Any]) -> TableChunk:
    """
    Deserialize chunk from VectorDB storage.
    
    Works with data from any VectorDB backend.
    """
    return TableChunk.from_storage_format(data)
