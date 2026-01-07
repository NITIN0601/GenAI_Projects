"""
Metadata Labels and Data Classes for Excel Export.

Centralized labels and dataclasses for consistent metadata structure.
Used throughout the pipeline for metadata row labeling.
"""

from typing import List
from dataclasses import dataclass, field


class MetadataLabels:
    """Centralized labels for metadata rows."""
    
    # Navigation
    BACK_LINK = '← Back to Index'
    
    # Row headers
    CATEGORY_PARENT = 'Category (Parent):'
    LINE_ITEMS = 'Line Items:'
    PRODUCT_ENTITY = 'Product/Entity:'
    
    # Column headers (3 levels)
    COLUMN_HEADER_L1 = 'Column Header L1:'  # Main Header
    COLUMN_HEADER_L2 = 'Column Header L2:'  # Period Type
    COLUMN_HEADER_L3 = 'Column Header L3:'  # Years/Dates
    
    # Period info
    YEAR_QUARTER = 'Year/Quarter:'
    
    # Table info
    TABLE_TITLE = 'Table Title:'
    SOURCES = 'Source(s):'  # Works for one or many
    SOURCES_PER_COLUMN = 'Source per Column:'  # Per-column source tracking
    
    # --- Row Index Constants (1-indexed for Excel) ---
    # NOTE: L1 (Main Header) is OPTIONAL - some tables have it, some don't
    # Structure varies, so code should detect by LABEL TEXT, not row index
    #
    # With L1 (13 metadata rows):
    #   R01: ← Back to Index
    #   R02: Category (Parent):
    #   R03: Line Items:
    #   R04: Product/Entity:
    #   R05: Column Header L1: (Main Header - OPTIONAL)
    #   R06: Column Header L2: (Period Type)
    #   R07: Column Header L3: (Years/Dates)
    #   R08: Year/Quarter:
    #   R09: [blank]
    #   R10: Table Title:
    #   R11: Source(s):
    #   R12: [blank]
    #   R13+: Data
    #
    # Without L1 (12 metadata rows):
    #   R01: ← Back to Index
    #   R02: Category (Parent):
    #   R03: Line Items:
    #   R04: Product/Entity:
    #   R05: Column Header L2: (Period Type)
    #   R06: Column Header L3: (Years/Dates)
    #   R07: Year/Quarter:
    #   R08: [blank]
    #   R09: Table Title:
    #   R10: Source(s):
    #   R11: [blank]
    #   R12+: Data
    
    # Minimum expected metadata rows (without L1)
    MIN_METADATA_ROWS = 11  
    # Maximum metadata rows (with L1)
    MAX_METADATA_ROWS = 12
    
    # For dynamic detection, use is_metadata_row() instead of row indices
    
    # --- Helper methods for pattern matching ---
    
    @staticmethod
    def is_sources(text: str) -> bool:
        """Check if text starts with any source label pattern."""
        if not text:
            return False
        return text.startswith(MetadataLabels.SOURCES) or text.startswith('Source:') or text.startswith('Sources:')
    
    @staticmethod
    def is_column_header_l1(text: str) -> bool:
        """Check if text starts with Column Header L1/Main Header pattern."""
        if not text:
            return False
        return text.startswith(MetadataLabels.COLUMN_HEADER_L1) or text.startswith('Main Header:')
    
    @staticmethod
    def is_column_header_l2(text: str) -> bool:
        """Check if text starts with Column Header L2/Period Type pattern."""
        if not text:
            return False
        return text.startswith(MetadataLabels.COLUMN_HEADER_L2) or text.startswith('Period Type:')
    
    @staticmethod
    def is_column_header_l3(text: str) -> bool:
        """Check if text starts with Column Header L3/Year(s) pattern."""
        if not text:
            return False
        return text.startswith(MetadataLabels.COLUMN_HEADER_L3) or text.startswith('Year(s):') or text.startswith('Years:')
    
    @staticmethod
    def is_metadata_row(text: str) -> bool:
        """Check if text starts with any metadata label."""
        if not text:
            return False
        prefixes = (
            MetadataLabels.SOURCES, MetadataLabels.BACK_LINK,
            MetadataLabels.CATEGORY_PARENT, MetadataLabels.LINE_ITEMS,
            MetadataLabels.PRODUCT_ENTITY, MetadataLabels.COLUMN_HEADER_L1,
            MetadataLabels.COLUMN_HEADER_L2, MetadataLabels.COLUMN_HEADER_L3,
            MetadataLabels.YEAR_QUARTER, MetadataLabels.TABLE_TITLE,
            'Source:', 'Sources:', 'Main Header:', 'Period Type:', 'Year(s):', 'Years:'
        )
        return any(text.startswith(p) for p in prefixes)


@dataclass
class TableMetadata:
    """Container for table metadata."""
    
    # Row headers
    category_parent: List[str] = field(default_factory=list)  # Section headers
    line_items: List[str] = field(default_factory=list)       # Data row labels
    product_entity: List[str] = field(default_factory=list)   # Unique entities
    
    # Column headers (per-column values)
    column_header_l1: List[str] = field(default_factory=list)  # Level 0 - Main Header
    column_header_l2: List[str] = field(default_factory=list)  # Level 1 - Period Type
    column_header_l3: List[str] = field(default_factory=list)  # Level 2 - Years/Dates
    
    # Year/Quarter (per-column, derived from L2+L3)
    year_quarter: List[str] = field(default_factory=list)
    
    # Source tracking per column (e.g., ["10q0624_p45", "10k1224_p32", ...])
    sources_per_column: List[str] = field(default_factory=list)
    
    # Table info
    table_title: str = ""
    sources: List[str] = field(default_factory=list)
    section: str = ""

