"""
VectorDB-specific schema utilities.

Uses the comprehensive TableMetadata from src/models/schemas as the source of truth.
Provides provider-specific conversion utilities for each VectorDB backend.

Industry Best Practices:
- FAISS: In-memory with pickle serialization, supports full Python objects
- ChromaDB: Native metadata storage with type restrictions (str, int, float, bool only)
- Redis: Explicit schema with typed fields (TextField, TagField, NumericField)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Import the comprehensive schema from extraction
from src.models.schemas import TableMetadata, TableChunk


class VectorDBProvider(Enum):
    """Supported vector database providers."""
    FAISS = "faiss"
    CHROMADB = "chromadb"
    REDIS = "redis"


@dataclass
class VectorDBIndexConfig:
    """Vector index configuration for similarity search."""
    
    # Common settings
    dimension: int = 768
    distance_metric: str = "cosine"  # cosine, l2, ip (inner product)
    
    # FAISS-specific
    faiss_index_type: str = "flat"  # flat, ivf, hnsw, pq
    faiss_nlist: int = 100  # For IVF indexes
    faiss_nprobe: int = 10  # For IVF search
    
    # Redis-specific
    redis_algorithm: str = "FLAT"  # FLAT, HNSW
    redis_ef_construction: int = 200  # For HNSW
    redis_ef_runtime: int = 10  # For HNSW search


class VectorDBSchemaConverter:
    """
    Convert TableMetadata to provider-specific format.
    
    Uses the existing comprehensive TableMetadata schema from extraction
    and converts it to formats compatible with each VectorDB.
    """
    
    # Fields that must be indexed for filtering (used by Redis)
    INDEXED_FIELDS = {
        'source_doc', 'year', 'quarter', 'report_type', 'table_type',
        'company_ticker', 'statement_type', 'extraction_backend',
        'embedding_model', 'embedding_provider', 'units', 'currency'
    }
    
    # Fields that need full-text search (used by Redis)
    TEXT_SEARCH_FIELDS = {
        'content', 'table_title', 'company_name', 'column_headers', 'row_headers'
    }
    
    @classmethod
    def to_chromadb(cls, metadata: TableMetadata) -> Dict[str, Any]:
        """
        Convert TableMetadata to ChromaDB-compatible format.
        
        ChromaDB restrictions:
        - Only str, int, float, bool allowed
        - No nested objects, lists, or None values
        """
        data = metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        result = {}
        
        for key, value in data.items():
            if value is None:
                continue  # Skip None values
            if isinstance(value, (str, int, float, bool)):
                result[key] = value
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                # Convert lists to pipe-separated strings
                result[key] = "|".join(str(v) for v in value if v is not None)
            else:
                result[key] = str(value)
        
        return result
    
    @classmethod
    def to_redis(cls, metadata: TableMetadata) -> Dict[str, Any]:
        """
        Convert TableMetadata to Redis-compatible format.
        
        Redis requirements:
        - All values stored as strings for TagField/TextField
        - Numeric values can be kept as numbers for NumericField
        """
        data = metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        result = {}
        
        for key, value in data.items():
            if value is None:
                result[key] = ""  # Empty string for missing values
                continue
            if isinstance(value, bool):
                result[key] = "1" if value else "0"
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                result[key] = "|".join(str(v) for v in value if v is not None)
            elif isinstance(value, (int, float)):
                # Keep numeric for filtering
                result[key] = value
            else:
                result[key] = str(value)
        
        return result
    
    @classmethod
    def to_faiss(cls, metadata: TableMetadata) -> Dict[str, Any]:
        """
        Convert TableMetadata to FAISS-compatible format.
        
        FAISS uses pickle serialization, so most Python types are supported.
        We just ensure datetime is serializable.
        """
        data = metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        result = {}
        
        for key, value in data.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def from_chromadb(cls, metadata: Dict[str, Any]) -> TableMetadata:
        """Convert ChromaDB metadata back to TableMetadata."""
        # Handle pipe-separated lists
        processed = {}
        for key, value in metadata.items():
            if isinstance(value, str) and '|' in value and key in ['footnote_references', 'subsections']:
                processed[key] = value.split('|')
            else:
                processed[key] = value
        
        return TableMetadata(**processed)
    
    @classmethod
    def from_redis(cls, metadata: Dict[str, Any]) -> TableMetadata:
        """Convert Redis metadata back to TableMetadata."""
        processed = {}
        for key, value in metadata.items():
            if value == "":
                processed[key] = None
            elif isinstance(value, str) and '|' in value and key in ['footnote_references', 'subsections']:
                processed[key] = value.split('|')
            elif isinstance(value, str) and value in ('1', '0') and key.startswith('has_'):
                processed[key] = value == '1'
            else:
                processed[key] = value
        
        return TableMetadata(**processed)


@dataclass
class VectorDBStats:
    """Statistics for a vector database."""
    provider: VectorDBProvider
    total_documents: int
    index_size_bytes: int = 0
    dimension: int = 0
    index_type: str = ""
    unique_sources: int = 0
    years_covered: List[int] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider.value,
            "total_documents": self.total_documents,
            "index_size_bytes": self.index_size_bytes,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "unique_sources": self.unique_sources,
            "years_covered": self.years_covered,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


def get_redis_schema_fields():
    """
    Get Redis RediSearch schema fields based on TableMetadata.
    
    Uses the comprehensive TableMetadata to generate Redis index fields.
    """
    try:
        from redis.commands.search.field import VectorField, TagField, TextField, NumericField
    except ImportError:
        return None
    
    fields = [
        # Core text content
        TextField("content"),
        
        # Identity (Tag for exact match)
        TagField("source_doc"),
        TagField("table_id"),
        TagField("chunk_reference_id"),
        
        # Searchable text
        TextField("table_title"),
        TextField("company_name"),
        
        # Filtering fields (Tag for exact match)
        TagField("company_ticker"),
        TagField("year"),
        TagField("quarter"),
        TagField("report_type"),
        TagField("table_type"),
        TagField("statement_type"),
        TagField("units"),
        TagField("currency"),
        TagField("extraction_backend"),
        TagField("embedding_model"),
        TagField("embedding_provider"),
        
        # Numeric fields
        NumericField("page_no"),
        NumericField("quality_score"),
    ]
    
    return fields


def get_redis_vector_field(dimension: int = 768, algorithm: str = "FLAT"):
    """Get Redis vector field configuration."""
    try:
        from redis.commands.search.field import VectorField
    except ImportError:
        return None
    
    return VectorField(
        "embedding",
        algorithm,
        {
            "TYPE": "FLOAT32",
            "DIM": dimension,
            "DISTANCE_METRIC": "COSINE",
        }
    )


# Default configurations
DEFAULT_INDEX_CONFIG = VectorDBIndexConfig()

