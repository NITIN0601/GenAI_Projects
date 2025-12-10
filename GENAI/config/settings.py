"""
Enhanced configuration system with provider selection.

Supports:
- Environment-specific configs (dev, staging, prod)
- Provider selection (OpenAI, local, etc.)
- API key management
- Feature flags
"""

from pydantic_settings import BaseSettings
from pydantic import SecretStr
from typing import Optional, Literal, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # ============================================================================
    # PROJECT PATHS
    # ============================================================================
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # New structure paths
    SRC_DIR: str = os.path.join(PROJECT_ROOT, "src")
    SCRIPTS_DIR: str = os.path.join(PROJECT_ROOT, "scripts")
    ARCHIVE_DIR: str = os.path.join(PROJECT_ROOT, "archive")
    
    # Data directories
    DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
    PROCESSED_DATA_DIR: str = os.path.join(DATA_DIR, "processed")
    CACHE_DATA_DIR: str = os.path.join(DATA_DIR, "cache")
    
    # Raw data directory (downloaded PDFs)
    # Now uses data/raw/ for consistent data folder structure
    RAW_DATA_DIR: str = os.path.join(DATA_DIR, "raw")

    
    # ============================================================================
    # EMBEDDING PROVIDER SETTINGS
    # ============================================================================
    EMBEDDING_PROVIDER: Literal["local", "custom", "openai"] = "local"  # Default: local (FREE)
    
    # Local Embeddings (sentence-transformers - FREE)
    EMBEDDING_MODEL_LOCAL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION_LOCAL: int = 384
    
    # OpenAI Embeddings
    EMBEDDING_MODEL_OPENAI: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION_OPENAI: int = 1536
    
    # Custom API Embeddings (YOUR WORKING API)
    EB_URL: Optional[str] = None
    EB_MODEL: Optional[str] = None
    EB_DIMENSION: Optional[int] = None  # Dimension for custom embeddings
    UNIQUE_ID: Optional[str] = None
    BEARER_TOKEN: Optional[SecretStr] = None  # SecretStr prevents accidental logging
    
    # Batch settings
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Dynamic properties based on provider
    @property
    def EMBEDDING_MODEL(self) -> str:
        """Get embedding model based on provider."""
        if self.EMBEDDING_PROVIDER == "openai":
            return self.EMBEDDING_MODEL_OPENAI
        elif self.EMBEDDING_PROVIDER == "custom":
            return self.EB_MODEL or "custom-embedding-model"
        return self.EMBEDDING_MODEL_LOCAL
    
    @property
    def EMBEDDING_DIMENSION(self) -> int:
        """Get embedding dimension based on provider."""
        if self.EMBEDDING_PROVIDER == "openai":
            return self.EMBEDDING_DIMENSION_OPENAI
        elif self.EMBEDDING_PROVIDER == "custom":
            return self.EB_DIMENSION or 384  # Use configured dimension or default
        return self.EMBEDDING_DIMENSION_LOCAL
    
    # ============================================================================
    # LLM PROVIDER SETTINGS
    # ============================================================================
    LLM_PROVIDER: Literal["local", "ollama", "custom", "openai"] = "local"  # Default: local (FREE)
    
    # Local LLM (HuggingFace transformers - FREE)
    LLM_MODEL_LOCAL: str = "google/flan-t5-base"  # Lightweight model for CPU
    
    # Ollama (Local - FREE)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2"
    
    # OpenAI Settings
    OPENAI_API_KEY: Optional[SecretStr] = None  # SecretStr prevents accidental logging
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Custom API LLM (YOUR WORKING API)
    LLM_URL: Optional[str] = None
    LLM_MODEL_CUSTOM: Optional[str] = None  # Renamed to avoid conflict with property
    # Uses same UNIQUE_ID and BEARER_TOKEN as embeddings
    
    # LLM Generation Settings
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2000
    
    @property
    def LLM_MODEL(self) -> str:
        """Get LLM model based on provider."""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_MODEL
        elif self.LLM_PROVIDER == "custom":
            return self.LLM_MODEL_CUSTOM or "custom-llm-model"
        elif self.LLM_PROVIDER == "local":
            return self.LLM_MODEL_LOCAL
        return self.OLLAMA_MODEL
    
    # ============================================================================
    # VECTOR DATABASE SETTINGS
    # ============================================================================
    # Vector DB
    VECTORDB_PROVIDER: Literal["chromadb", "faiss", "redis"] = "faiss"  # chromadb, faiss, redis
    
    # ChromaDB Settings (FREE & OPEN SOURCE)
    CHROMA_PERSIST_DIR: str = os.path.join(PROJECT_ROOT, "chroma_db")
    CHROMA_COLLECTION_NAME: str = "financial_data"
    
    # Search Configuration
    SEARCH_TOP_K: int = 5
    SEARCH_FETCH_K: int = 20  # Fetch more for filtering/reranking
    HYBRID_SEARCH_ALPHA: float = 0.5  # Weight for vector search (0.0 to 1.0)
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    
    # FAISS Settings (FREE & HIGH PERFORMANCE)
    FAISS_PERSIST_DIR: str = os.path.join(PROJECT_ROOT, "faiss_db")
    FAISS_INDEX_TYPE: str = "flat"  # flat, ivf, hnsw
    
    # Redis Vector Settings (OPTIONAL - for distributed systems)
    REDIS_VECTOR_HOST: str = "localhost"
    REDIS_VECTOR_PORT: int = 6379
    REDIS_VECTOR_INDEX: str = "financial_tables_idx"
    REDIS_VECTOR_PREFIX: str = "table:"
    
    # ============================================================================
    # EXTRACTION BACKEND SETTINGS
    # ============================================================================
    EXTRACTION_BACKEND: Literal["docling", "pymupdf", "pdfplumber", "camelot"] = "docling"  # Default: docling (BEST)
    
    # Backend priority order (for fallback)
    EXTRACTION_BACKENDS: List[str] = ["docling"]  # Can add multiple: ["docling", "pymupdf"]
    
    # Quality threshold for extraction
    EXTRACTION_MIN_QUALITY: float = 60.0
    
    # Caching
    EXTRACTION_CACHE_ENABLED: bool = True
    EXTRACTION_CACHE_TTL_HOURS: int = 168  # 7 days
    
    # ============================================================================
    # REDIS CACHE SETTINGS (Optional - for caching)
    # ============================================================================
    REDIS_ENABLED: bool = False  # Set to True if Redis installed
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None  # SecretStr prevents accidental logging
    REDIS_DB: int = 0
    CACHE_TTL: int = 86400  # 24 hours
    
    # ============================================================================
    # CHUNKING SETTINGS
    # ============================================================================
    CHUNK_SIZE: int = 10  # rows per chunk for tables
    CHUNK_OVERLAP: int = 3  # overlapping rows
    MIN_CHUNK_SIZE: int = 3  # minimum rows per chunk
    
    # ============================================================================
    # RETRIEVAL SETTINGS
    # ============================================================================
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.7
    
    # ============================================================================
    # PDF PROCESSING SETTINGS
    # ============================================================================
    HANDLE_TWO_COLUMN: bool = True
    EXTRACT_TABLES: bool = True
    PDF_MAX_SIZE_MB: int = 500
    
    # NOTE: EXTRACTION_CACHE_* settings are defined in EXTRACTION BACKEND SETTINGS section above
    
    # ============================================================================
    # FEATURE FLAGS
    # ============================================================================
    ENABLE_CHUNKING: bool = True
    ENABLE_DEDUPLICATION: bool = True
    ENABLE_PROGRESS_BARS: bool = True
    
    # ============================================================================
    # ENVIRONMENT
    # ============================================================================
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"
    DEBUG: bool = True
    
    # ============================================================================
    # LANGSMITH TRACING (Observability)
    # ============================================================================
    LANGSMITH_TRACING: bool = False  # Enable LangSmith tracing
    LANGSMITH_API_KEY: Optional[SecretStr] = None  # SecretStr prevents accidental logging
    LANGSMITH_PROJECT: str = "genai-rag"  # Project name in LangSmith
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    # Trace sampling rate (1.0 = all traces, 0.1 = 10% of traces)
    LANGSMITH_SAMPLE_RATE: float = 1.0
    
    # ============================================================================
    # SCHEDULER SETTINGS
    # ============================================================================
    SCHEDULER_ENABLED: bool = False  # Enable automatic filing scheduler
    SCHEDULER_AUTO_EXTRACT: bool = True  # Auto-extract after download
    SCHEDULER_LOOKAHEAD_DAYS: int = 180  # Days to look ahead for filings
    SCHEDULER_CHECK_INTERVAL_HOURS: int = 24  # Periodic check interval
    
    # ============================================================================
    # DOWNLOAD SETTINGS
    # ============================================================================
    DOWNLOAD_ENABLED: bool = True  # Enable/disable PDF download (Step 1)
    DOWNLOAD_BASE_URL: str = "https://www.morganstanley.com/content/dam/msdotcom/en/about-us-ir/shareholder"
    
    # ============================================================================
    # TABLE EXPORT SETTINGS
    # ============================================================================
    OUTPUT_DIR: str = "outputs/tables"  # Directory for exported tables
    EXPORT_FORMAT: Literal["csv", "excel", "both"] = "both"  # Export format
    TABLE_SIMILARITY_THRESHOLD: float = 0.85  # Threshold for table title matching
    
    # ============================================================================
    # EVALUATION SETTINGS
    # ============================================================================
    EVALUATION_ENABLED: bool = True  # Enable/disable evaluation on queries
    EVALUATION_PROVIDER: Literal["heuristic", "ragas", "hybrid"] = "heuristic"  # Default: heuristic (no LLM)
    EVALUATION_AUTO_RUN: bool = False  # Auto-evaluate on every query (prod: True)
    EVALUATION_LOG_SCORES: bool = True  # Log evaluation scores to file
    EVALUATION_MIN_CONFIDENCE: float = 0.5  # Minimum confidence threshold
    EVALUATION_BLOCK_HALLUCINATIONS: bool = False  # Block responses with hallucinations
    
    # Note: RAGAS uses the system's LLM_PROVIDER setting automatically
    # (local, custom, openai) - no separate RAGAS config needed
    
    # ============================================================================
    # RAG OUTPUT SETTINGS
    # ============================================================================
    SAVE_RAG_TABLES: bool = True  # Save retrieved tables to CSV/Excel
    SAVE_RAG_RESPONSES: bool = True  # Save text responses to log files
    RAG_OUTPUT_DIR: str = "output/rag_queries"  # Directory for RAG outputs
    
    # ============================================================================
    # EXTRACTION REPORT SETTINGS
    # ============================================================================
    EXTRACTION_REPORT_DIR: str = "outputs/extraction_reports"  # Directory for extraction reports
    EXTRACTION_REPORT_FORMAT: Literal["csv", "excel", "both"] = "both"  # Report format
    
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Helper functions
def get_provider_config() -> dict:
    """Get current provider configuration."""
    return {
        "embedding": {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
            "dimension": settings.EMBEDDING_DIMENSION
        },
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL
        },
        "vectordb": {
            "provider": settings.VECTORDB_PROVIDER
        }
    }


def print_config():
    """Print current configuration."""
    config = get_provider_config()
    
    print("=" * 80)
    print("CURRENT CONFIGURATION")
    print("=" * 80)
    print(f"\n Embedding Provider: {config['embedding']['provider']}")
    print(f"   Model: {config['embedding']['model']}")
    print(f"   Dimension: {config['embedding']['dimension']}")
    
    print(f"\n LLM Provider: {config['llm']['provider']}")
    print(f"   Model: {config['llm']['model']}")
    
    print(f"\n VectorDB Provider: {config['vectordb']['provider']}")
    
    print(f"\n Features:")
    print(f"  Chunking: {'enabled' if settings.ENABLE_CHUNKING else 'disabled'}")
    print(f"  Deduplication: {'enabled' if settings.ENABLE_DEDUPLICATION else 'disabled'}")
    print(f"  Cache: {'enabled' if settings.EXTRACTION_CACHE_ENABLED else 'disabled'}")
    
    print("\n" + "=" * 80)
