"""Data models for the RAG system."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class TableMetadata(BaseModel):
    """Metadata for extracted financial tables."""
    source_doc: str = Field(..., description="Source PDF filename")
    chunk_reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk ID")
    page_no: int = Field(..., description="Page number in PDF")
    table_title: str = Field(..., description="Extracted table title")
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Quarter (Q1, Q2, Q3, Q4) for 10-Q reports")
    report_type: str = Field(..., description="Report type: 10-K or 10-Q")
    table_type: Optional[str] = Field(None, description="Type: Balance Sheet, Income Statement, etc.")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period from table headers")
    extraction_date: datetime = Field(default_factory=datetime.now, description="When this was extracted")
    
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
                "table_type": "Balance Sheet",
                "fiscal_period": "June 30, 2025"
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
