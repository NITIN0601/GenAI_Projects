from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Project paths
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RAW_DATA_DIR: str = os.path.join(os.path.dirname(PROJECT_ROOT), "raw_data")
    
    # LLM Settings (Ollama - Free & Local)
    LLM_MODEL: str = "llama3.2"  # Free Ollama model
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2000
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Embedding Settings (sentence-transformers - Free & Local)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Vector Database Settings (ChromaDB - Free & Open Source)
    CHROMA_PERSIST_DIR: str = os.path.join(PROJECT_ROOT, "chroma_db")
    CHROMA_COLLECTION_NAME: str = "financial_tables"
    DISTANCE_METRIC: str = "cosine"
    
    # Redis Settings (Optional - for caching)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = True  # Set to False if Redis not installed
    CACHE_TTL: int = 86400  # 24 hours
    
    # Chunking Settings
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    # Retrieval Settings
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.7
    
    # PDF Processing
    HANDLE_TWO_COLUMN: bool = True
    EXTRACT_TABLES: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
