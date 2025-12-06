"""
Embed Step - Generate embeddings with model-aware caching.

Enterprise features:
- Embedding cache (model-aware, invalidates on model change)
- Batch processing for efficiency
- Provider-agnostic (supports multiple vector DBs)
"""

import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def run_embed(
    extracted_data: List[Dict[str, Any]],
    store_in_vectordb: bool = True,
    embedding_cache=None,
):
    """
    Step 3: Generate embeddings and store in VectorDB.
    
    Args:
        extracted_data: List of extraction results from run_extract
        store_in_vectordb: Whether to store in vector DB
        embedding_cache: EmbeddingCache instance (optional)
        
    Returns:
        PipelineResult with embedding stats
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    from src.infrastructure.embeddings.manager import get_embedding_manager
    from src.infrastructure.vectordb.manager import get_vectordb_manager
    from src.domain.tables import TableChunk, TableMetadata
    
    embedding_manager = get_embedding_manager()
    vector_store = get_vectordb_manager() if store_in_vectordb else None
    
    vectordb_provider = settings.VECTORDB_PROVIDER if store_in_vectordb else "none"
    embedding_provider = settings.EMBEDDING_PROVIDER
    embedding_model = embedding_manager.get_model_name()
    
    all_chunks = []
    stats = {
        'total_embeddings': 0,
        'cache_hits': 0,
        'stored': 0,
        'vectordb_provider': vectordb_provider,
        'embedding_provider': embedding_provider,
        'embedding_model': embedding_model
    }
    
    try:
        for doc_result in extracted_data:
            filename = doc_result['file']
            content_hash = doc_result.get('content_hash')
            
            # Check embedding cache
            if embedding_cache and content_hash:
                cached_chunks = embedding_cache.get_embeddings(content_hash)
                if cached_chunks:
                    logger.info(f"Embedding cache hit: {filename}")
                    all_chunks.extend(cached_chunks)
                    stats['cache_hits'] += len(cached_chunks)
                    stats['total_embeddings'] += len(cached_chunks)
                    continue
            
            # Generate new embeddings
            doc_chunks = []
            pdf_hash = hashlib.md5(filename.encode()).hexdigest()
            
            for i, table in enumerate(doc_result.get('tables', [])):
                content = table.get('content', '')
                if not content:
                    continue
                
                # Generate embedding
                embedding = embedding_manager.generate_embedding(content)
                
                # Extract temporal info
                metadata_dict = doc_result.get('metadata', {})
                quarter_str = metadata_dict.get('quarter')
                quarter_number = None
                month = None
                
                if quarter_str and quarter_str.upper().startswith('Q'):
                    try:
                        quarter_number = int(quarter_str[1])
                        month = quarter_number * 3
                    except (ValueError, IndexError):
                        pass
                
                # Get or generate table_id
                table_meta = table.get('metadata', {})
                table_id = table_meta.get('table_id')
                if not table_id:
                    page = table_meta.get('page_no', 1)
                    table_id = f"{filename}_p{page}_{i}"
                
                # Create metadata using domain entity
                metadata = TableMetadata(
                    table_id=table_id,
                    source_doc=filename,
                    page_no=table_meta.get('page_no', 1),
                    table_title=table_meta.get('table_title', f'Table {i+1}'),
                    year=metadata_dict.get('year'),
                    quarter=quarter_str,
                    quarter_number=quarter_number,
                    month=month,
                    report_type=metadata_dict.get('report_type'),
                    embedding_model=embedding_model,
                    embedding_provider=embedding_provider,
                    embedded_date=datetime.now()
                )
                
                chunk = TableChunk(
                    chunk_id=f"{pdf_hash}_{i}",
                    content=content,
                    embedding=embedding,
                    metadata=metadata
                )
                
                doc_chunks.append(chunk)
                stats['total_embeddings'] += 1
            
            # Cache embeddings for this document
            if embedding_cache and content_hash and doc_chunks:
                embedding_cache.set_embeddings(content_hash, doc_chunks)
            
            all_chunks.extend(doc_chunks)
        
        # Store in vector DB
        if store_in_vectordb and all_chunks:
            vector_store.add_chunks(all_chunks)
            stats['stored'] = len(all_chunks)
        
        return PipelineResult(
            step=PipelineStep.EMBED,
            success=True,
            data=all_chunks,
            message=(
                f"Generated {stats['total_embeddings']} embeddings "
                f"({stats['cache_hits']} cached), stored {stats['stored']} in {vectordb_provider.upper()}"
            ),
            metadata=stats
        )
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return PipelineResult(
            step=PipelineStep.EMBED,
            success=False,
            error=str(e)
        )
