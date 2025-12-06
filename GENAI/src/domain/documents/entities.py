"""
Document domain entities.

Entities for PDF document processing, page layout, and processing results.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Period(BaseModel):
    """
    Standardized period information for financial reports.
    
    Represents a fiscal period (quarter, year, YTD) with
    date range and display formatting.
    """
    
    period_type: str = Field(..., description="Type: quarter, year, ytd, month")
    year: int = Field(..., description="Fiscal year")
    quarter: Optional[int] = Field(None, description="Quarter number (1-4)")
    start_date: Optional[str] = Field(None, description="Period start (ISO format)")
    end_date: Optional[str] = Field(None, description="Period end (ISO format)")
    display_label: str = Field(..., description="Human-readable label (e.g., 'Q1 2025')")

    class Config:
        json_schema_extra = {
            "example": {
                "period_type": "quarter",
                "year": 2025,
                "quarter": 1,
                "start_date": "2025-01-01",
                "end_date": "2025-03-31",
                "display_label": "Q1 2025"
            }
        }


class DocumentMetadata(BaseModel):
    """
    Document-level metadata for a processed PDF.
    
    Contains information about the source document before
    table extraction, including file hash for deduplication.
    """
    
    filename: str = Field(..., description="PDF filename")
    file_hash: str = Field(..., description="SHA256 hash of file")
    company_name: Optional[str] = Field(None, description="Company name")
    company_ticker: Optional[str] = Field(None, description="Stock ticker")
    report_type: Optional[str] = Field(None, description="10-K, 10-Q")
    reporting_period: Optional[str] = Field(None, description="Reporting period end date")
    total_pages: int = Field(..., description="Total number of pages")
    extraction_date: datetime = Field(default_factory=datetime.now)


class PageLayout(BaseModel):
    """
    Page layout information for a PDF page.
    
    Describes column structure for multi-column documents.
    """
    
    page_no: int = Field(..., description="Page number")
    layout_type: str = Field(
        ..., 
        description="Layout: single-column, two-column, multi-column, mixed"
    )
    columns: List[Dict[str, float]] = Field(
        default_factory=list,
        description="Column boundaries with left and right coordinates"
    )
    gaps: List[float] = Field(
        default_factory=list, 
        description="Vertical gap positions"
    )


class DocumentProcessingResult(BaseModel):
    """
    Result of processing a PDF document.
    
    Summary of the extraction run with timing and error info.
    """
    
    filename: str = Field(..., description="Processed filename")
    total_tables: int = Field(..., description="Number of tables extracted")
    total_chunks: int = Field(..., description="Number of chunks created")
    processing_time: float = Field(..., description="Processing time in seconds")
    success: bool = Field(..., description="Whether processing succeeded")
    error_message: Optional[str] = Field(None, description="Error if failed")
    
    @property
    def tables_per_second(self) -> float:
        """Calculate extraction speed."""
        if self.processing_time > 0:
            return self.total_tables / self.processing_time
        return 0.0
