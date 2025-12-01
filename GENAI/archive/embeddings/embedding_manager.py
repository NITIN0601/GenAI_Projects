"""
Embedding generation and management with multi-provider support.

This module provides a backward-compatible interface while using the new
provider abstraction layer underneath.

Supports:
- OpenAI (text-embedding-3-small, text-embedding-ada-002)
- Local (sentence-transformers)
"""

from typing import List, Optional
import warnings

# Import new provider system
from embeddings.providers import (
    EmbeddingManager as NewEmbeddingManager,
    get_embedding_manager as get_new_embedding_manager
)


class EmbeddingManager:
    """
    DEPRECATED: Use embeddings.providers.EmbeddingManager instead.
    
    This class is kept for backward compatibility and wraps the new
    provider-based system.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding model.
        
        Args:
            model_name: Model name (deprecated, use provider system instead)
        """
        warnings.warn(
            "This EmbeddingManager is deprecated. "
            "Use 'from embeddings.providers import get_embedding_manager' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Use new provider system
        from config.settings import settings
        
        # Determine provider from model name or settings
        if model_name and "openai" in model_name.lower():
            provider = "openai"
        else:
            provider = settings.EMBEDDING_PROVIDER
        
        self._manager = NewEmbeddingManager(
            provider=provider,
            model=model_name
        )
        
        # Backward compatibility attributes
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = self._manager.get_dimension()
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self._manager.generate_embedding(text)
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently."""
        return self._manager.generate_embeddings_batch(texts, show_progress)
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        return float(similarity)
    
    def create_table_chunk_text(
        self,
        table_title: str,
        headers: List[str],
        rows: List[List[str]],
        max_rows: int = 10
    ) -> List[str]:
        """Create text chunks from table data for embedding."""
        chunks = []
        
        context = f"Table: {table_title}\n"
        context += f"Columns: {', '.join(headers)}\n\n"
        
        for i in range(0, len(rows), max_rows):
            chunk_rows = rows[i:i + max_rows]
            
            chunk_text = context
            chunk_text += "Data:\n"
            
            for row in chunk_rows:
                row_text = " | ".join([f"{h}: {v}" for h, v in zip(headers, row)])
                chunk_text += row_text + "\n"
            
            chunks.append(chunk_text)
        
        return chunks
    
    def create_semantic_chunk(
        self,
        table_title: str,
        headers: List[str],
        row: List[str],
        metadata_str: Optional[str] = None
    ) -> str:
        """Create a semantic chunk for a single table row with full context."""
        chunk = f"Table: {table_title}\n"
        
        if metadata_str:
            chunk += f"Source: {metadata_str}\n"
        
        chunk += "\n"
        
        for header, value in zip(headers, row):
            if value and str(value).strip():
                chunk += f"{header}: {value}\n"
        
        return chunk


# Global embedding manager instance
_embedding_manager: Optional[EmbeddingManager] = None


def get_embedding_manager(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None
) -> EmbeddingManager:
    """
    Get or create global embedding manager instance.
    
    RECOMMENDED: Use the new provider system instead:
        from embeddings.providers import get_embedding_manager
    
    Args:
        model_name: Model name (deprecated)
        provider: Provider name ("openai" or "local")
        api_key: API key for cloud providers
    """
    global _embedding_manager
    
    # If using new provider system
    if provider is not None:
        return get_new_embedding_manager(provider=provider, model=model_name, api_key=api_key)
    
    # Backward compatibility
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager(model_name=model_name)
    
    return _embedding_manager

