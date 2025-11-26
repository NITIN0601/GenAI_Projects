"""Embedding generation and management using free local models."""

from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from tqdm import tqdm

from config.settings import settings


class EmbeddingManager:
    """
    Manages embedding generation using sentence-transformers (FREE & LOCAL).
    No API keys required!
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding model.
        
        Args:
            model_name: Model name (default: all-MiniLM-L6-v2 - fast and efficient)
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        print(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.dimension = settings.EMBEDDING_DIMENSION
        
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            List of floats representing the embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of input texts
            show_progress: Show progress bar
            
        Returns:
            List of embedding vectors
        """
        batch_size = settings.EMBEDDING_BATCH_SIZE
        
        if show_progress:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=True,
                convert_to_numpy=True
            )
        else:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True
            )
        
        return embeddings.tolist()
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        return float(similarity)
    
    def create_table_chunk_text(
        self,
        table_title: str,
        headers: List[str],
        rows: List[List[str]],
        max_rows: int = 10
    ) -> List[str]:
        """
        Create text chunks from table data for embedding.
        Each chunk contains context (title + headers) plus a subset of rows.
        
        Args:
            table_title: Title of the table
            headers: Column headers
            rows: Table rows
            max_rows: Maximum rows per chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        
        # Create context (title + headers)
        context = f"Table: {table_title}\n"
        context += f"Columns: {', '.join(headers)}\n\n"
        
        # Split rows into chunks
        for i in range(0, len(rows), max_rows):
            chunk_rows = rows[i:i + max_rows]
            
            chunk_text = context
            chunk_text += "Data:\n"
            
            for row in chunk_rows:
                # Create row text
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
        """
        Create a semantic chunk for a single table row with full context.
        This is ideal for RAG as each chunk is self-contained.
        
        Args:
            table_title: Title of the table
            headers: Column headers
            row: Single table row
            metadata_str: Optional metadata string (e.g., "Q2 2025, Page 5")
            
        Returns:
            Formatted text chunk
        """
        chunk = f"Table: {table_title}\n"
        
        if metadata_str:
            chunk += f"Source: {metadata_str}\n"
        
        chunk += "\n"
        
        # Add row data with headers
        for header, value in zip(headers, row):
            if value and str(value).strip():
                chunk += f"{header}: {value}\n"
        
        return chunk


# Global embedding manager instance
_embedding_manager: Optional[EmbeddingManager] = None


def get_embedding_manager() -> EmbeddingManager:
    """Get or create global embedding manager instance."""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager
