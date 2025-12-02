"""Data models for the RAG system."""

# Import enhanced schemas
from src.models.enhanced_schemas import (
    ColumnHeader,
    RowHeader,
    DataCell,
    Footnote,
    Period,
    DocumentMetadata,
    EnhancedFinancialTable,
    PageLayout,
    EnhancedDocument,
    ProcessingQueueItem
)

# Direct file import to bypass schemas/ package conflict
# Load SearchResult from schemas.py file directly
import importlib.util
import os

_schemas_file_path = os.path.join(os.path.dirname(__file__), 'schemas.py')
_spec = importlib.util.spec_from_file_location('_schemas_root', _schemas_file_path)
_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas)

# Re-export all from root schemas file
TableMetadata = _schemas.TableMetadata
TableChunk = _schemas.TableChunk
FinancialTable = _schemas.FinancialTable
RAGQuery = _schemas.RAGQuery
RAGResponse = _schemas.RAGResponse
SearchResult = _schemas.SearchResult  # This is the problematic one
DocumentProcessingResult = _schemas.DocumentProcessingResult

__all__ = [
    'TableMetadata',
    'TableChunk',
    'FinancialTable',
    'RAGQuery',
    'RAGResponse',
    'SearchResult',
    'DocumentProcessingResult',
]
