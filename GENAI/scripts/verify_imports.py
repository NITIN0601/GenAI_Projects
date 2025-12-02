import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_imports")

def verify_imports():
    logger.info("Verifying imports...")
    
    try:
        # Config
        logger.info("Importing config...")
        from config.settings import settings
        
        # Models
        logger.info("Importing models...")
        from src.models.schemas import TableMetadata, TableChunk
        from src.models.enhanced_schemas import EnhancedFinancialTable
        
        # Utils
        logger.info("Importing utils...")
        from src.utils.extraction_utils import PDFMetadataExtractor, DoclingHelper
        from src.utils.logger import get_logger
        
        # Embeddings
        logger.info("Importing embeddings...")
        from src.embeddings.manager import get_embedding_manager
        
        # Vector Store
        logger.info("Importing vector store...")
        from src.vector_store.manager import get_vectordb_manager
        from src.vector_store.stores.chromadb_store import VectorStore
        from src.vector_store.stores.faiss_store import FAISSVectorStore
        from src.vector_store.stores.redis_store import RedisVectorStore
        
        # LLM
        logger.info("Importing LLM...")
        from src.llm.manager import get_llm_manager
        
        # Prompts
        logger.info("Importing prompts...")
        from src.prompts.base import FINANCIAL_ANALYSIS_PROMPT
        from src.prompts.search_strategies import HYDE_PROMPT, MULTI_QUERY_PROMPT
        from src.prompts.few_shot import get_few_shot_manager
        
        # Extraction
        logger.info("Importing extraction...")
        from src.extraction import Extractor
        from src.extraction.consolidation import MultiYearTableConsolidator, QuarterlyTableConsolidator
        
        # Retrieval
        logger.info("Importing retrieval...")
        from src.retrieval.retriever import get_retriever
        from src.retrieval.query_processor import get_query_processor
        from src.retrieval.search.orchestrator import get_search_orchestrator
        
        # RAG Pipeline
        logger.info("Importing RAG pipeline...")
        from src.rag import RAGPipeline
        
        logger.info("✅ All imports successful!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    if verify_imports():
        sys.exit(0)
    else:
        sys.exit(1)
