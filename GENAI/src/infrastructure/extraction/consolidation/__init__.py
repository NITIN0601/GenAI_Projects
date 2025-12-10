"""
Table consolidation module.

Consolidates extracted tables across multiple documents/periods.

This module provides tools for combining tables from different sources:
- TableConsolidator: Unified consolidator with filtering (recommended)
- ConsolidationResult: Dataclass for consolidated output

Usage:
    from src.infrastructure.extraction.consolidation import get_table_consolidator
    
    consolidator = get_table_consolidator()
    
    # Find tables with filters
    tables = consolidator.find_tables(
        title="Balance Sheet",
        years=[2020, 2021, 2022],
        quarters=["Q1", "Q4"]
    )
    
    # Consolidate
    result = consolidator.consolidate(tables, transpose=True)
    
    # Export
    consolidator.export(result, format="both")
"""

# Unified consolidator (recommended)
from .consolidator import (
    TableConsolidator,
    ConsolidationResult,
    get_table_consolidator,
    reset_table_consolidator,
)

# Multi-PDF consolidation engine (for complex scenarios)
from .multi_year import (
    TableConsolidationEngine,
    get_consolidation_engine,
)


# Backward compatibility aliases
MultiYearTableConsolidator = TableConsolidator
QuarterlyTableConsolidator = TableConsolidator
get_multi_year_consolidator = get_table_consolidator
get_quarterly_consolidator = lambda vs=None, em=None: get_table_consolidator(vs, em)
consolidate_and_transpose = lambda results, title, fmt='dataframe': (
    get_table_consolidator().consolidate(
        get_table_consolidator().find_tables(title) if not results else results,
        table_name=title,
        transpose=True
    ).dataframe if fmt == 'dataframe' else 
    get_table_consolidator().consolidate(
        get_table_consolidator().find_tables(title) if not results else results,
        table_name=title,
        transpose=True
    ).to_markdown()
)


__all__ = [
    # Unified consolidator (recommended)
    'TableConsolidator',
    'ConsolidationResult',
    'get_table_consolidator',
    'reset_table_consolidator',
    
    # Multi-PDF engine
    'TableConsolidationEngine',
    'get_consolidation_engine',
    
    # Backward compatibility
    'MultiYearTableConsolidator',
    'QuarterlyTableConsolidator',
    'get_multi_year_consolidator',
    'get_quarterly_consolidator',
    'consolidate_and_transpose',
]
