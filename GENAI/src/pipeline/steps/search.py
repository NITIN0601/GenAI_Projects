"""
Search Step - Vector search and DB inspection.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def run_search(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
):
    """
    Step 6: Perform search on VectorDB (without LLM).
    
    Args:
        query: Search query
        top_k: Number of results
        filters: Optional metadata filters
        
    Returns:
        PipelineResult with search results
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    from src.infrastructure.vectordb.manager import get_vectordb_manager
    
    try:
        vector_store = get_vectordb_manager()
        vectordb_provider = settings.VECTORDB_PROVIDER
        
        results = vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters
        )
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                'chunk_id': r.chunk_id,
                'content': r.content,
                'score': r.score,
                'metadata': {
                    'title': r.metadata.table_title if r.metadata else 'N/A',
                    'year': r.metadata.year if r.metadata else 'N/A',
                    'quarter': r.metadata.quarter if r.metadata else 'N/A',
                    'source': r.metadata.source_doc if r.metadata else 'N/A',
                    'page': r.metadata.page_no if r.metadata else 'N/A'
                }
            })
        
        return PipelineResult(
            step=PipelineStep.SEARCH,
            success=True,
            data=formatted_results,
            message=f"Found {len(results)} results for '{query}' in {vectordb_provider.upper()}",
            metadata={'query': query, 'top_k': top_k, 'provider': vectordb_provider}
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return PipelineResult(
            step=PipelineStep.SEARCH,
            success=False,
            error=str(e)
        )


def run_view_db(
    show_sample: bool = True,
    sample_count: int = 5
):
    """
    Step 5: View VectorDB contents and schema.
    
    Args:
        show_sample: Whether to show sample entries
        sample_count: Number of samples to show
        
    Returns:
        PipelineResult with DB info
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    from src.infrastructure.vectordb.manager import get_vectordb_manager
    
    try:
        vector_store = get_vectordb_manager()
        stats = vector_store.get_stats()
        vectordb_provider = stats.get('provider', settings.VECTORDB_PROVIDER)
        
        # Get sample entries
        samples = []
        if show_sample:
            try:
                results = vector_store.search(query="financial", top_k=sample_count)
                for r in results:
                    samples.append({
                        'chunk_id': r.chunk_id,
                        'table_id': r.metadata.table_id if r.metadata and hasattr(r.metadata, 'table_id') else 'N/A',
                        'title': r.metadata.table_title if r.metadata else 'N/A',
                        'year': r.metadata.year if r.metadata else 'N/A',
                        'quarter': r.metadata.quarter if r.metadata else 'N/A',
                        'source': r.metadata.source_doc if r.metadata else 'N/A',
                        'content_preview': r.content[:100] + '...' if len(r.content) > 100 else r.content
                    })
            except Exception:
                pass
        
        # Get unique documents and titles
        unique_docs = set()
        unique_titles = set()
        years = set()
        quarters = set()
        
        try:
            all_results = vector_store.search(query="", top_k=1000)
            for r in all_results:
                if r.metadata:
                    if r.metadata.source_doc:
                        unique_docs.add(r.metadata.source_doc)
                    if r.metadata.table_title:
                        unique_titles.add(r.metadata.table_title)
                    if r.metadata.year:
                        years.add(r.metadata.year)
                    if r.metadata.quarter:
                        quarters.add(r.metadata.quarter)
        except Exception:
            pass
        
        db_info = {
            'provider': vectordb_provider,
            'total_chunks': stats.get('total_chunks', 0),
            'unique_documents': len(unique_docs),
            'unique_tables': len(unique_titles),
            'years': sorted(years) if years else [],
            'quarters': sorted(quarters) if quarters else [],
            'table_titles': sorted(list(unique_titles))[:20],
            'samples': samples
        }
        
        return PipelineResult(
            step=PipelineStep.VIEW_DB,
            success=True,
            data=db_info,
            message=f"{vectordb_provider.upper()} DB: {db_info['total_chunks']} chunks, {db_info['unique_documents']} docs",
            metadata=stats
        )
    except Exception as e:
        logger.error(f"View DB failed: {e}")
        return PipelineResult(
            step=PipelineStep.VIEW_DB,
            success=False,
            error=str(e)
        )
