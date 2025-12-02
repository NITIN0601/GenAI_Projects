"""
Table consolidation module.

Consolidates extracted tables across multiple documents/periods.

This module provides tools for combining tables from different sources:
- Quarterly consolidation: Merge tables across quarters (Q1, Q2, Q3, Q4)
- Multi-year consolidation: Merge tables across years with transposition
- Consolidation engine: Advanced multi-PDF consolidation scenarios

Usage:
    # Multi-year consolidation (recommended)
    from src.extraction.consolidation import MultiYearTableConsolidator
    consolidator = MultiYearTableConsolidator()
    result = consolidator.consolidate_multi_year_tables(search_results, "Total Assets")
    
    # Quarterly consolidation
    from src.extraction.consolidation import QuarterlyTableConsolidator
    consolidator = QuarterlyTableConsolidator(vector_store, embedding_manager)
    tables = consolidator.find_tables_by_title("Balance Sheet")
"""

# Multi-year consolidation (recommended for most use cases)
from .table_consolidator import (
    MultiYearTableConsolidator,
    get_multi_year_consolidator,
    consolidate_and_transpose
)

# Quarterly/period consolidation
from .quarterly import (
    QuarterlyTableConsolidator,
    get_quarterly_consolidator
)

# Multi-PDF consolidation engine
from .multi_year import (
    TableConsolidationEngine,
    get_consolidation_engine
)


# Backward compatibility - default to multi-year
TableConsolidator = MultiYearTableConsolidator
get_table_consolidator = get_multi_year_consolidator


__all__ = [
    # Multi-year consolidation (recommended)
    'MultiYearTableConsolidator',
    'get_multi_year_consolidator',
    'consolidate_and_transpose',
    
    # Quarterly consolidation
    'QuarterlyTableConsolidator',
    'get_quarterly_consolidator',
    
    # Multi-PDF engine
    'TableConsolidationEngine',
    'get_consolidation_engine',
    
    # Backward compatibility
    'TableConsolidator',
    'get_table_consolidator',
]
