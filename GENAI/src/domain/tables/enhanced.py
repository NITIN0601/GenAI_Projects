"""
Enhanced table entities for advanced table structure extraction.

Contains enhanced Pydantic models for detailed table structure
including cell-level metadata, hierarchical headers, and footnotes.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import uuid


class ColumnHeader(BaseModel):
    """Column header with multi-level support."""
    row_index: int = Field(..., description="Row index in header section")
    column_index: int = Field(..., description="Column index")
    text: str = Field(..., description="Header text")
    column_span: int = Field(1, description="Number of columns this header spans")
    parent_header: Optional[str] = Field(None, description="Parent header text for multi-level headers")
    units: Optional[str] = Field(None, description="Units specified in header (millions, billions, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "row_index": 0,
                "column_index": 1,
                "text": "March 31, 2025",
                "column_span": 1,
                "parent_header": "Three Months Ended",
                "units": "millions_usd"
            }
        }


class RowHeader(BaseModel):
    """Row header (stub column) with hierarchy support."""
    row_index: int = Field(..., description="Row index")
    text: str = Field(..., description="Original row header text")
    indent_level: int = Field(0, description="Indentation level (0=top level, 1=sub-item, etc.)")
    parent_row: Optional[str] = Field(None, description="Parent row header text")
    canonical_label: Optional[str] = Field(None, description="Standardized canonical label")
    is_subtotal: bool = Field(False, description="Whether this is a subtotal row")
    is_total: bool = Field(False, description="Whether this is a total row")
    
    class Config:
        json_schema_extra = {
            "example": {
                "row_index": 5,
                "text": "Investment banking",
                "indent_level": 1,
                "parent_row": "Revenues",
                "canonical_label": "investment_banking_revenue",
                "is_subtotal": False,
                "is_total": False
            }
        }


class DataCell(BaseModel):
    """Individual data cell with full metadata."""
    row: int = Field(..., description="Row index")
    column: int = Field(..., description="Column index")
    row_header: str = Field(..., description="Row header this cell belongs to")
    column_header: str = Field(..., description="Column header this cell belongs to")
    raw_text: str = Field(..., description="Raw text as it appears in PDF")
    parsed_value: Optional[float] = Field(None, description="Parsed numeric value")
    data_type: str = Field(..., description="Data type: number, currency, percentage, text, date")
    units: Optional[str] = Field(None, description="Units for this cell")
    original_unit: Optional[str] = Field(None, description="Original unit (millions, billions)")
    base_value: Optional[float] = Field(None, description="Value converted to base unit")
    display_value: Optional[str] = Field(None, description="Formatted display value")
    alignment: Optional[str] = Field(None, description="Text alignment: left, center, right")
    footnote_refs: List[str] = Field(default_factory=list, description="Footnote markers in this cell")
    
    class Config:
        json_schema_extra = {
            "example": {
                "row": 1,
                "column": 1,
                "row_header": "Net revenues",
                "column_header": "Q1 2025",
                "raw_text": "$ 17,739",
                "parsed_value": 17739.0,
                "data_type": "currency",
                "units": "millions_usd",
                "original_unit": "millions",
                "base_value": 17739000000.0,
                "display_value": "$ 17,739 million",
                "alignment": "right",
                "footnote_refs": ["1"]
            }
        }


class Footnote(BaseModel):
    """Footnote with bidirectional cell references."""
    marker: str = Field(..., description="Footnote marker (1, 2, *, etc.)")
    text: str = Field(..., description="Full footnote text")
    cell_references: List[Tuple[int, int]] = Field(
        default_factory=list, 
        description="List of (row, column) tuples that reference this footnote"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "marker": "1",
                "text": "Includes advisory, equity underwriting and debt underwriting.",
                "cell_references": [(1, 1), (1, 2)]
            }
        }


class EnhancedFinancialTable(BaseModel):
    """Enhanced table with complete structure and metadata."""
    original_title: str = Field(..., description="Original table title")
    canonical_title: Optional[str] = Field(None, description="Standardized table title")
    
    # Table structure
    column_headers: List[ColumnHeader] = Field(default_factory=list, description="Column headers")
    row_headers: List[RowHeader] = Field(default_factory=list, description="Row headers")
    data_cells: List[DataCell] = Field(default_factory=list, description="Data cells")
    footnotes: List[Footnote] = Field(default_factory=list, description="Footnotes")
    
    # Periods (import from domain.documents if needed)
    periods: List[Dict[str, Any]] = Field(default_factory=list, description="Periods covered")
    
    # Document hierarchy (for hierarchical metadata)
    section_heading: Optional[str] = Field(None, description="Main section heading")
    subsection_heading: Optional[str] = Field(None, description="Subsection heading")
    subsubsection_heading: Optional[str] = Field(None, description="Sub-subsection heading")
    heading_path: Optional[str] = Field(None, description="Full heading path")
    section_keywords: List[str] = Field(default_factory=list, description="Keywords from headings")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        arbitrary_types_allowed = True


class EnhancedDocument(BaseModel):
    """Complete document structure with enhanced tables."""
    # Use Dict for metadata to avoid import cycle - callers can use DocumentMetadata
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    pages: List[Dict[str, Any]] = Field(default_factory=list, description="Page-level data")
    tables: List[EnhancedFinancialTable] = Field(default_factory=list, description="All extracted tables")
    
    class Config:
        arbitrary_types_allowed = True


class ProcessingQueueItem(BaseModel):
    """Item in the PDF processing queue."""
    path: str = Field(..., description="Full path to PDF file")
    filename: str = Field(..., description="PDF filename")
    file_hash: str = Field(..., description="File hash for change detection")
    priority: int = Field(..., description="Priority: 1=new, 2=modified, 3=processed")
    size: int = Field(..., description="File size in bytes")
    modified: float = Field(..., description="Last modified timestamp")
    retry_count: int = Field(0, description="Number of retry attempts")
    status: str = Field("pending", description="Status: pending, processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
