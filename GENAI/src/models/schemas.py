"""Data models for the RAG system."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class TableMetadata(BaseModel):
    """Enhanced metadata for extracted financial tables."""
    
    # ============================================================================
    # DOCUMENT INFORMATION
    # ============================================================================
    source_doc: str = Field(..., description="Source PDF filename")
    chunk_reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk ID")
    page_no: int = Field(..., description="Page number in PDF")
    
    # ============================================================================
    # COMPANY INFORMATION
    # ============================================================================
    company_ticker: Optional[str] = Field(None, description="Company ticker symbol (e.g., MS)")
    company_name: Optional[str] = Field(None, description="Company name (e.g., Morgan Stanley)")
    
    # ============================================================================
    # FINANCIAL STATEMENT CONTEXT
    # ============================================================================
    statement_type: Optional[str] = Field(
        None,
        description="Type: balance_sheet, income_statement, cash_flow, footnotes"
    )
    filing_type: str = Field(..., description="SEC filing type: 10-Q, 10-K, 8-K")
    fiscal_period_end: Optional[str] = Field(None, description="Fiscal period end date (ISO format)")
    
    # ============================================================================
    # TABLE IDENTIFICATION
    # ============================================================================
    table_title: str = Field(..., description="Extracted table title")
    table_type: Optional[str] = Field(None, description="Type: summary, detail, reconciliation, segment")
    table_index: Optional[int] = Field(None, description="Table index in document")
    
    # ============================================================================
    # TEMPORAL INFORMATION
    # ============================================================================
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Quarter (Q1, Q2, Q3, Q4) for 10-Q reports")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period from table headers")
    comparative_periods: Optional[List[str]] = Field(None, description="Periods in multi-year tables")
    
    # ============================================================================
    # TABLE-SPECIFIC METADATA (CRITICAL FOR FINANCIAL ACCURACY)
    # ============================================================================
    units: Optional[str] = Field(None, description="Financial units: thousands, millions, billions")
    currency: Optional[str] = Field(None, description="Currency code: USD, EUR, GBP")
    is_consolidated: bool = Field(True, description="Consolidated vs segment data")
    
    # ============================================================================
    # TABLE STRUCTURE & DIMENSIONS
    # ============================================================================
    column_headers: Optional[str] = Field(None, description="Pipe-separated column headers")
    row_headers: Optional[str] = Field(None, description="Pipe-separated row headers")
    column_count: Optional[int] = Field(None, description="Number of columns")
    row_count: Optional[int] = Field(None, description="Number of rows")
    table_structure: Optional[str] = Field(None, description="Structure: simple, multi_header, nested")
    
    # ============================================================================
    # HIERARCHICAL INFORMATION
    # ============================================================================
    parent_section: Optional[str] = Field(None, description="Parent section (e.g., Assets, Liabilities)")
    subsection: Optional[str] = Field(None, description="Subsection (e.g., Current Assets)")
    footnote_references: Optional[List[str]] = Field(None, description="Footnote numbers referenced")
    
    # ============================================================================
    # MULTI-LEVEL HEADERS
    # ============================================================================
    has_multi_level_headers: bool = Field(False, description="Has spanning/multi-level headers")
    main_header: Optional[str] = Field(None, description="Main spanning header")
    sub_headers: Optional[str] = Field(None, description="Pipe-separated sub-headers")
    
    # ============================================================================
    # CONTENT ANALYSIS
    # ============================================================================
    has_currency: bool = Field(False, description="Contains currency values")
    has_subtotals: bool = Field(False, description="Contains subtotal rows")
    has_calculations: bool = Field(False, description="Contains calculated values")
    
    # ============================================================================
    # EXTRACTION METADATA
    # ============================================================================
    extraction_date: datetime = Field(default_factory=datetime.now, description="When extracted")
    extraction_backend: Optional[str] = Field(None, description="Backend: docling, pymupdf, etc.")
    quality_score: Optional[float] = Field(None, description="Extraction quality (0-100)")
    extraction_confidence: Optional[float] = Field(None, description="OCR/parsing confidence (0-1)")
    
    # ============================================================================
    # EMBEDDING METADATA (NEW - CRITICAL)
    # ============================================================================
    embedding_model: Optional[str] = Field(None, description="Model used for embeddings")
    embedding_dimension: Optional[int] = Field(None, description="Embedding vector dimension")
    embedding_provider: Optional[str] = Field(None, description="Provider: local, openai, custom")
    
    # ============================================================================
    # CHUNK MANAGEMENT
    # ============================================================================
    chunk_type: Optional[str] = Field(None, description="Type: header, data, footer, complete")
    table_start_page: Optional[int] = Field(None, description="Start page for multi-page tables")
    table_end_page: Optional[int] = Field(None, description="End page for multi-page tables")
    report_type: str = Field(..., description="Report type: 10-K or 10-Q")  # Keep for backward compatibility
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_doc": "10k1222-1-20.pdf",
                "page_no": 5,
                "company_ticker": "MS",
                "company_name": "Morgan Stanley",
                "statement_type": "balance_sheet",
                "filing_type": "10-K",
                "fiscal_period_end": "2022-12-31",
                "table_title": "Consolidated Balance Sheet",
                "table_type": "summary",
                "year": 2022,
                "quarter": None,
                "fiscal_period": "Year Ended December 31, 2022",
                "comparative_periods": ["2022", "2021"],
                "units": "millions",
                "currency": "USD",
                "is_consolidated": True,
                "column_headers": "Assets|Dec 31, 2022|Dec 31, 2021",
                "row_headers": "Cash|Securities|Loans|Total Assets",
                "column_count": 3,
                "row_count": 45,
                "table_structure": "multi_header",
                "parent_section": "Assets",
                "has_currency": True,
                "has_subtotals": True,
                "extraction_backend": "docling",
                "quality_score": 85.0,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "embedding_dimension": 384,
                "embedding_provider": "local",
                "chunk_type": "complete",
                "report_type": "10-K"
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


class SearchResult(BaseModel):
    """Result from vector search."""
    chunk_id: str = Field(..., description="Unique chunk ID")
    content: str = Field(..., description="Text content")
    metadata: TableMetadata = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Similarity score/distance")
    distance: Optional[float] = Field(None, description="Raw distance metric")


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
