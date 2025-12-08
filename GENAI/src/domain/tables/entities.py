"""
Table domain entities.

Core business entities for extracted financial tables.
These models represent the primary data structures in the RAG system.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    """Safely get a value from dict or object."""
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


class TableMetadata(BaseModel):
    """
    Metadata for extracted financial tables.
    
    This is the primary metadata structure attached to all table chunks
    in the vector database. Contains comprehensive information about:
    - Document source (file, page, extraction info)
    - Temporal context (year, quarter, fiscal period)
    - Table structure (headers, rows, hierarchy)
    - Financial context (units, currency)
    - Embedding information
    """
    
    # === Core Document Info ===
    table_id: str = Field(..., description="Unique identifier (e.g. filename_tableIndex)")
    source_doc: str = Field(..., description="Source PDF filename")
    chunk_reference_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), 
        description="Unique chunk ID (auto-generated if not provided)"
    )
    page_no: int = Field(..., description="Page number in PDF")
    table_title: str = Field(..., description="Extracted table title")
    original_table_title: Optional[str] = Field(
        None, 
        description="Original title without row ranges"
    )
    
    @field_validator('chunk_reference_id', mode='before')
    @classmethod
    def ensure_chunk_id(cls, v):
        """Replace None with UUID - fixes Pydantic validation when None is passed."""
        if v is None or v == '':
            return str(uuid.uuid4())
        return v

    # === Company Info ===
    company_name: Optional[str] = Field(None, description="Company name")
    company_ticker: Optional[str] = Field(None, description="Stock ticker symbol")
    
    # === Temporal Info ===
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Quarter (Q1, Q2, Q3, Q4)")
    quarter_number: Optional[int] = Field(None, description="Quarter as number (1-4)")
    month: Optional[int] = Field(None, description="Month (1-12)")
    report_type: str = Field(..., description="Report type: 10-K or 10-Q")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period from headers")
    extraction_date: datetime = Field(default_factory=datetime.now)
    
    # === Table Classification ===
    table_type: Optional[str] = Field(None, description="Balance Sheet, Income Statement, etc.")
    statement_type: Optional[str] = Field(None, description="Statement classification")
    chunk_table_index: Optional[int] = Field(None, description="Table index (0-based)")
    table_start_page: Optional[int] = Field(None, description="Start page for multi-page")
    table_end_page: Optional[int] = Field(None, description="End page for multi-page")
    
    # === Table Structure ===
    column_headers: Optional[str] = Field(None, description="Column headers (pipe-separated)")
    row_headers: Optional[str] = Field(None, description="Row headers (pipe-separated)")
    column_count: Optional[int] = Field(None, description="Number of columns")
    row_count: Optional[int] = Field(None, description="Number of rows")
    
    # === Multi-level Headers ===
    has_multi_level_headers: Optional[bool] = Field(None)
    main_header: Optional[str] = Field(None)
    sub_headers: Optional[str] = Field(None, description="Sub-headers (pipe-separated)")
    
    # === Hierarchical Structure ===
    parent_section: Optional[str] = Field(None, description="Parent section")
    has_hierarchy: Optional[bool] = Field(None)
    subsections: Optional[str] = Field(None, description="Subsections (pipe-separated)")
    table_structure: Optional[str] = Field(None, description="simple, multi_column, multi_header")
    footnote_references: Optional[List[str]] = Field(None, description="Footnote numbers")

    # === Financial Context ===
    units: Optional[str] = Field(None, description="millions, thousands, billions")
    currency: Optional[str] = Field(None, description="USD, EUR, GBP")
    has_currency: Optional[bool] = Field(None)
    currency_count: Optional[int] = Field(None)

    # === Extraction Info ===
    extraction_backend: Optional[str] = Field(None, description="docling, pymupdf, etc.")
    quality_score: Optional[float] = Field(None, description="Quality (0-100)")
    extraction_confidence: Optional[float] = Field(None, description="Confidence (0-1)")
    
    # === Embedding Metadata ===
    embedding_model: Optional[str] = Field(None, description="Embedding model used")
    embedding_dimension: Optional[int] = Field(None, description="Embedding dimension")
    embedding_provider: Optional[str] = Field(None, description="local, custom, openai")
    embedded_date: Optional[datetime] = Field(None, description="When embedded")

    class Config:
        json_schema_extra = {
            "example": {
                "table_id": "10q0625_0",
                "source_doc": "10q0625.pdf",
                "page_no": 5,
                "table_title": "Consolidated Balance Sheet",
                "year": 2025,
                "quarter": "Q2",
                "report_type": "10-Q"
            }
        }
    
    @classmethod
    def from_extraction(
        cls,
        table_meta: Any,
        doc_metadata: Dict[str, Any],
        filename: str,
        table_index: int,
        embedding: Optional[List[float]] = None,
        embedding_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
    ) -> "TableMetadata":
        """
        Create TableMetadata from extraction output.
        
        This is the single source of truth for mapping extraction data to VectorDB metadata.
        
        Args:
            table_meta: Table-level metadata (dict or object from extraction)
            doc_metadata: Document-level metadata dict
            filename: Source PDF filename
            table_index: Index of table in document
            embedding: Optional embedding vector (used to compute dimension)
            embedding_model: Embedding model name
            embedding_provider: Embedding provider name
            
        Returns:
            TableMetadata instance with all fields populated
        """
        # Parse quarter info
        quarter_str = doc_metadata.get('quarter')
        quarter_number = None
        month = None
        
        if quarter_str and str(quarter_str).upper().startswith('Q'):
            try:
                quarter_number = int(quarter_str[1])
                month = quarter_number * 3
            except (ValueError, IndexError):
                pass
        
        # Get table-level values with safe access
        page_no = _get_value(table_meta, 'page_no', 1)
        table_title = _get_value(table_meta, 'table_title', f'Table {table_index + 1}')
        table_id = _get_value(table_meta, 'table_id')
        
        if not table_id:
            table_id = f"{filename}_p{page_no}_{table_index}"
        
        return cls(
            # Core Document Info
            table_id=table_id,
            source_doc=filename,
            chunk_reference_id=_get_value(table_meta, 'chunk_reference_id'),
            page_no=page_no,
            table_title=table_title,
            original_table_title=_get_value(table_meta, 'original_table_title'),
            
            # Company Info
            company_name=doc_metadata.get('company_name'),
            company_ticker=doc_metadata.get('company_ticker'),
            
            # Temporal Info
            year=doc_metadata.get('year'),
            quarter=quarter_str,
            quarter_number=quarter_number,
            month=month,
            report_type=doc_metadata.get('report_type'),
            fiscal_period=_get_value(table_meta, 'fiscal_period'),
            
            # Table Classification
            table_type=_get_value(table_meta, 'table_type'),
            statement_type=_get_value(table_meta, 'statement_type'),
            chunk_table_index=table_index,
            table_start_page=_get_value(table_meta, 'table_start_page'),
            table_end_page=_get_value(table_meta, 'table_end_page'),
            
            # Table Structure
            column_headers=_get_value(table_meta, 'column_headers'),
            row_headers=_get_value(table_meta, 'row_headers'),
            column_count=_get_value(table_meta, 'column_count'),
            row_count=_get_value(table_meta, 'row_count'),
            
            # Multi-level Headers
            has_multi_level_headers=_get_value(table_meta, 'has_multi_level_headers'),
            main_header=_get_value(table_meta, 'main_header'),
            sub_headers=_get_value(table_meta, 'sub_headers'),
            
            # Hierarchical Structure
            parent_section=_get_value(table_meta, 'parent_section'),
            has_hierarchy=_get_value(table_meta, 'has_hierarchy'),
            subsections=_get_value(table_meta, 'subsections'),
            table_structure=_get_value(table_meta, 'table_structure'),
            footnote_references=_get_value(table_meta, 'footnote_references'),
            
            # Financial Context
            units=_get_value(table_meta, 'units'),
            currency=_get_value(table_meta, 'currency'),
            has_currency=_get_value(table_meta, 'has_currency'),
            currency_count=_get_value(table_meta, 'currency_count'),
            
            # Extraction Info
            extraction_backend=_get_value(table_meta, 'extraction_backend'),
            quality_score=_get_value(table_meta, 'quality_score'),
            extraction_confidence=_get_value(table_meta, 'extraction_confidence'),
            
            # Embedding Metadata
            embedding_model=embedding_model,
            embedding_dimension=len(embedding) if embedding else None,
            embedding_provider=embedding_provider,
            embedded_date=datetime.now() if embedding else None,
        )


class TableChunk(BaseModel):
    """
    A chunk of table data with embeddings.
    
    Represents a single searchable unit in the vector database.
    Contains the text content, associated metadata, and optional embedding.
    """
    
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str = Field(..., description="Text content of the chunk")
    metadata: TableMetadata = Field(..., description="Associated metadata")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    
    class Config:
        arbitrary_types_allowed = True


class FinancialTable(BaseModel):
    """
    Complete financial table structure.
    
    Represents a full table before chunking, with headers and all rows.
    """
    
    title: str = Field(..., description="Table title")
    page_number: int = Field(..., description="Page number")
    headers: List[str] = Field(..., description="Column headers")
    rows: List[List[Any]] = Field(..., description="Table rows")
    metadata: Optional[TableMetadata] = None
