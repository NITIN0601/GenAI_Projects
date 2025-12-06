"""
Query domain entities.

Entities for RAG queries, responses, and search results.
These are the primary I/O models for the RAG pipeline.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Import TableMetadata for type reference
from src.domain.tables.entities import TableMetadata


class RAGQuery(BaseModel):
    """
    Query structure for the RAG system.
    
    Encapsulates user questions with optional filters and retrieval settings.
    """
    
    query: str = Field(..., description="User question")
    filters: Optional[Dict[str, Any]] = Field(
        None, 
        description="Metadata filters (year, quarter, table_type, etc.)"
    )
    top_k: int = Field(5, description="Number of results to retrieve")
    include_sources: bool = Field(True, description="Include source citations")
    use_cache: bool = Field(True, description="Use query cache if available")
    force_refresh: bool = Field(False, description="Force fresh search (ignore cache)")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What was revenue in Q1 2025?",
                "filters": {"year": 2025, "quarter": "Q1"},
                "top_k": 5,
                "include_sources": True
            }
        }


class RAGResponse(BaseModel):
    """
    Response from the RAG system.
    
    Contains the generated answer, source attributions, and optional
    evaluation scores and guardrail warnings.
    """
    
    answer: str = Field(..., description="Generated answer")
    sources: List[TableMetadata] = Field(
        default_factory=list, 
        description="Source tables used"
    )
    confidence: float = Field(0.0, description="Confidence score (0-1)")
    retrieved_chunks: int = Field(0, description="Number of chunks retrieved")
    
    # Optional evaluation and safety
    evaluation: Optional[Dict[str, Any]] = Field(
        None, 
        description="Evaluation scores (if enabled)"
    )
    warnings: Optional[List[str]] = Field(
        None, 
        description="Guardrail warnings"
    )
    
    # Cache indicator
    from_cache: bool = Field(False, description="Whether from query cache")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Total revenue in Q1 2025 was $17.7 billion.",
                "sources": [{"source_doc": "10q0625.pdf", "page_no": 5}],
                "confidence": 0.95,
                "retrieved_chunks": 3,
                "from_cache": False
            }
        }


class SearchResult(BaseModel):
    """
    Result from vector similarity search.
    
    Represents a single retrieved chunk with its similarity score.
    """
    
    chunk_id: str = Field(..., description="Unique chunk ID")
    content: str = Field(..., description="Text content")
    metadata: TableMetadata = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Similarity score")
    distance: Optional[float] = Field(None, description="Raw distance metric")
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence match (score > 0.8)."""
        return self.score > 0.8
