"""Data models for the RAG system."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class TableMetadata(BaseModel):
    """Metadata for extracted financial tables with comprehensive structure information."""
    
    # === Core Document Info ===
    source_doc: str = Field(..., description="Source PDF filename")
    chunk_reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk ID")
    page_no: int = Field(..., description="Page number in PDF")
    table_title: str = Field(..., description="Extracted table title")
    
    # === Temporal Info ===
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Quarter (Q1, Q2, Q3, Q4) for 10-Q reports")
    quarter_number: Optional[int] = Field(None, description="Quarter as number (1, 2, 3, 4) for filtering")
    month: Optional[int] = Field(None, description="Month (1-12) for precise date filtering")
    report_type: str = Field(..., description="Report type: 10-K or 10-Q")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period from table headers")
    extraction_date: datetime = Field(default_factory=datetime.now, description="When this was extracted")
    
    # === Table Classification ===
    table_type: Optional[str] = Field(None, description="Type: Balance Sheet, Income Statement, etc.")
    statement_type: Optional[str] = Field(None, description="Statement classification from enrichment")
    
    # === Table Structure ===
    column_headers: Optional[str] = Field(None, description="Column headers (pipe-separated)")
    row_headers: Optional[str] = Field(None, description="Row headers (pipe-separated, first 10)")
    column_count: Optional[int] = Field(None, description="Number of columns")
    row_count: Optional[int] = Field(None, description="Number of rows")
    
    # === Multi-level Headers ===
    has_multi_level_headers: Optional[bool] = Field(None, description="Has multi-level column headers")
    main_header: Optional[str] = Field(None, description="Main header for multi-level tables")
    sub_headers: Optional[str] = Field(None, description="Sub-headers (pipe-separated)")
    
    # === Hierarchical Structure ===
    has_hierarchy: Optional[bool] = Field(None, description="Has hierarchical row structure")
    subsections: Optional[str] = Field(None, description="Subsection names (pipe-separated)")
    table_structure: Optional[str] = Field(None, description="Structure type: simple, multi_column, multi_header")
    
    # === Financial Context ===
    units: Optional[str] = Field(None, description="Financial units: millions, thousands, billions")
    currency: Optional[str] = Field(None, description="Currency: USD, EUR, GBP")
    has_currency: Optional[bool] = Field(None, description="Whether currency symbols are present")
    currency_count: Optional[int] = Field(None, description="Number of currency symbols")
    
    # === Embedding Metadata ===
    embedding_model: Optional[str] = Field(None, description="Embedding model used (e.g., all-MiniLM-L6-v2)")
    embedded_date: Optional[datetime] = Field(None, description="When the embedding was created")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_doc": "10q0625.pdf",
                "chunk_reference_id": "abc123",
                "page_no": 5,
                "table_title": "Consolidated Balance Sheet",
                "year": 2025,
                "quarter": "Q2",
                "report_type": "10-Q",
                "fiscal_period": "June 30, 2025",
                "table_type": "Balance Sheet",
                "statement_type": "balance_sheet",
                "column_headers": "Assets|Liabilities|Equity",
                "row_headers": "Total Assets|Total Liabilities|Total Equity",
                "column_count": 3,
                "row_count": 25,
                "has_multi_level_headers": True,
                "main_header": "Three Months Ended",
                "sub_headers": "March 31, 2025|June 30, 2025",
                "has_hierarchy": True,
                "subsections": "Current Assets|Non-current Assets",
                "units": "millions",
                "currency": "USD",
                "has_currency": True,
                "currency_count": 150
            }
        }



class TableChunk(BaseModel):
    """A chunk of table data with embeddings."""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str = Field(..., description="Text content of the chunk")
    metadata: TableMetadata
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    
    class Config:
        arbitrary_types_allowed = True


class FinancialTable(BaseModel):
    """Complete financial table structure."""
    title: str = Field(..., description="Table title")
    page_number: int = Field(..., description="Page number")
    headers: List[str] = Field(..., description="Column headers")
    rows: List[List[Any]] = Field(..., description="Table rows")
    metadata: Optional[TableMetadata] = None


class RAGQuery(BaseModel):
    """Query structure for RAG system."""
    query: str = Field(..., description="User question")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    top_k: int = Field(5, description="Number of results to retrieve")
    include_sources: bool = Field(True, description="Include source citations")


class RAGResponse(BaseModel):
    """Response from RAG system."""
    answer: str = Field(..., description="Generated answer")
    sources: List[TableMetadata] = Field(default_factory=list, description="Source tables used")
    confidence: float = Field(0.0, description="Confidence score")
    retrieved_chunks: int = Field(0, description="Number of chunks retrieved")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The total assets as of June 30, 2025 were $3.2 trillion.",
                "sources": [
                    {
                        "source_doc": "10q0625.pdf",
                        "page_no": 5,
                        "table_title": "Consolidated Balance Sheet"
                    }
                ],
                "confidence": 0.95,
                "retrieved_chunks": 3
            }
        }


class DocumentProcessingResult(BaseModel):
    """Result of processing a PDF document."""
    filename: str
    total_tables: int
    total_chunks: int
    processing_time: float
    success: bool
    error_message: Optional[str] = None


class SearchResult(BaseModel):
    """Result from vector search."""
    chunk_id: str = Field(..., description="Unique chunk ID")
    content: str = Field(..., description="Text content")
    metadata: TableMetadata = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Similarity score/distance")
    distance: Optional[float] = Field(None, description="Raw distance metric")
