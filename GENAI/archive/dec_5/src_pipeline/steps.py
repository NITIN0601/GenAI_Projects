"""
Pipeline Steps - Core functions for each pipeline stage.

Each step can be called independently or chained together.
All steps return a PipelineResult for consistent handling.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStep(Enum):
    """Pipeline step identifiers."""
    DOWNLOAD = "download"
    EXTRACT = "extract"
    CACHE = "cache"
    EMBED = "embed"
    VIEW_DB = "view_db"
    SEARCH = "search"
    QUERY = "query"
    CONSOLIDATE = "consolidate"
    EXPORT = "export"


@dataclass
class PipelineResult:
    """Result from a pipeline step."""
    step: PipelineStep
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def run_download(
    year_range: str,
    month: Optional[str] = None,
    output_dir: Optional[str] = None,
    timeout: int = 30,
    max_retries: int = 3
) -> PipelineResult:
    """
    Step 1: Download PDF files.
    
    Args:
        year_range: Year or range (e.g., "25" or "20-25")
        month: Optional month filter (03, 06, 09, 12)
        output_dir: Output directory (defaults to settings)
        timeout: Download timeout
        max_retries: Max retry attempts
        
    Returns:
        PipelineResult with downloaded file paths
    """
    from config.settings import settings
    from scripts.download_documents import download_files, get_file_names_to_download
    
    # Check if download is enabled
    if hasattr(settings, 'DOWNLOAD_ENABLED') and not settings.DOWNLOAD_ENABLED:
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=False,
            message="Download disabled in settings (DOWNLOAD_ENABLED=False)",
            error="Download disabled"
        )
    
    base_url = settings.DOWNLOAD_BASE_URL
    
    if output_dir is None:
        output_dir = settings.RAW_DATA_DIR
    
    try:
        file_urls = get_file_names_to_download(base_url, month, year_range)
        
        results = download_files(
            file_urls=file_urls,
            download_dir=output_dir,
            timeout=timeout,
            max_retries=max_retries
        )
        
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=True,
            data=results['successful'],
            message=f"Downloaded {len(results['successful'])} files",
            metadata={
                'failed': results['failed'],
                'output_dir': output_dir
            }
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=False,
            error=str(e)
        )


def run_extract(
    source_dir: Optional[str] = None,
    force: bool = False
) -> PipelineResult:
    """
    Step 2: Extract tables from PDFs.
    
    Args:
        source_dir: Directory with PDF files
        force: Force re-extraction
        
    Returns:
        PipelineResult with extracted tables
    """
    from config.settings import settings
    from src.extraction.extractor import UnifiedExtractor as Extractor
    
    if source_dir is None:
        source_dir = settings.RAW_DATA_DIR
    
    source_path = Path(source_dir)
    if not source_path.exists():
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=f"Directory {source_dir} does not exist"
        )
    
    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=f"No PDF files found in {source_dir}"
        )
    
    all_results = []
    stats = {'processed': 0, 'failed': 0, 'total_tables': 0}
    
    try:
        extractor = Extractor(enable_caching=True)
        
        for pdf_path in pdf_files:
            result = extractor.extract(str(pdf_path))
            
            if result.is_successful():
                all_results.append({
                    'file': pdf_path.name,
                    'tables': result.tables,
                    'metadata': result.metadata,
                    'quality_score': result.quality_score
                })
                stats['processed'] += 1
                stats['total_tables'] += len(result.tables)
            else:
                stats['failed'] += 1
                logger.error(f"Failed to extract {pdf_path.name}: {result.error}")
        
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=True,
            data=all_results,
            message=f"Extracted {stats['total_tables']} tables from {stats['processed']} files",
            metadata=stats
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=str(e)
        )


def run_embed(
    extracted_data: List[Dict[str, Any]],
    store_in_vectordb: bool = True
) -> PipelineResult:
    """
    Step 4: Generate embeddings and store in VectorDB.
    
    Supports any VectorDB provider configured in settings:
    - FAISS (default, high-performance)
    - ChromaDB (persistent, open-source)
    - Redis Vector (distributed)
    
    Args:
        extracted_data: List of extraction results from run_extract
        store_in_vectordb: Whether to store in vector DB
        
    Returns:
        PipelineResult with embedding stats
    """
    import hashlib
    from config.settings import settings
    from src.embeddings.manager import get_embedding_manager
    from src.vector_store.manager import get_vectordb_manager
    from src.models.schemas import TableChunk, TableMetadata
    
    embedding_manager = get_embedding_manager()
    vector_store = get_vectordb_manager() if store_in_vectordb else None
    
    # Get provider info
    vectordb_provider = settings.VECTORDB_PROVIDER if store_in_vectordb else "none"
    embedding_provider = settings.EMBEDDING_PROVIDER
    
    all_chunks = []
    stats = {
        'total_embeddings': 0, 
        'stored': 0,
        'vectordb_provider': vectordb_provider,
        'embedding_provider': embedding_provider
    }
    
    try:
        for doc_result in extracted_data:
            filename = doc_result['file']
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
                    quarter_number = int(quarter_str[1])
                    month = quarter_number * 3
                
                # Get or generate table_id
                table_meta = table.get('metadata', {})
                table_id = table_meta.get('table_id')
                if not table_id:
                    # Generate stable ID
                    page = table_meta.get('page_no', 1)
                    table_id = f"{filename}_p{page}_{i}"

                # Create metadata
                metadata = TableMetadata(
                    table_id=table_id,
                    source_doc=filename,
                    page_no=table.get('metadata', {}).get('page_no', 1),
                    table_title=table.get('metadata', {}).get('table_title', f'Table {i+1}'),
                    year=metadata_dict.get('year'),
                    quarter=quarter_str,
                    quarter_number=quarter_number,
                    month=month,
                    report_type=metadata_dict.get('report_type'),
                    embedding_model=embedding_manager.get_model_name(),
                    embedding_provider=embedding_provider,
                    embedded_date=datetime.now()
                )
                
                chunk = TableChunk(
                    chunk_id=f"{pdf_hash}_{i}",
                    content=content,
                    embedding=embedding,
                    metadata=metadata
                )
                
                all_chunks.append(chunk)
                stats['total_embeddings'] += 1
        
        # Store in vector DB
        if store_in_vectordb and all_chunks:
            vector_store.add_chunks(all_chunks)
            stats['stored'] = len(all_chunks)
        
        return PipelineResult(
            step=PipelineStep.EMBED,
            success=True,
            data=all_chunks,
            message=f"Generated {stats['total_embeddings']} embeddings, stored {stats['stored']} in {vectordb_provider.upper()}",
            metadata=stats
        )
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return PipelineResult(
            step=PipelineStep.EMBED,
            success=False,
            error=str(e)
        )


def run_view_db(
    show_sample: bool = True,
    sample_count: int = 5
) -> PipelineResult:
    """
    Step 5: View VectorDB contents and schema.
    
    Supports any VectorDB provider configured in settings:
    - FAISS (default, high-performance)
    - ChromaDB (persistent, open-source)
    - Redis Vector (distributed)
    
    Args:
        show_sample: Whether to show sample entries
        sample_count: Number of samples to show
        
    Returns:
        PipelineResult with DB info
    """
    from config.settings import settings
    from src.vector_store.manager import get_vectordb_manager
    
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
                    unique_docs.add(r.metadata.source_doc)
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
            'table_titles': sorted(list(unique_titles))[:20],  # First 20
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


def run_search(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> PipelineResult:
    """
    Step 6: Perform search on VectorDB (without LLM).
    
    Supports any VectorDB provider configured in settings:
    - FAISS (default, high-performance)
    - ChromaDB (persistent, open-source)
    - Redis Vector (distributed)
    
    Args:
        query: Search query
        top_k: Number of results
        filters: Optional metadata filters
        
    Returns:
        PipelineResult with search results
    """
    from config.settings import settings
    from src.vector_store.manager import get_vectordb_manager
    
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


def run_query(
    question: str,
    top_k: int = 5,
    use_cache: bool = True
) -> PipelineResult:
    """
    Step 7: Query with LLM response.
    
    Args:
        question: User question
        top_k: Number of context chunks
        use_cache: Whether to use cache
        
    Returns:
        PipelineResult with LLM response
    """
    try:
        from src.retrieval.query_processor import get_query_processor
        
        processor = get_query_processor()
        result = processor.process_query(question)
        
        return PipelineResult(
            step=PipelineStep.QUERY,
            success=True,
            data={'answer': result},
            message="Query processed successfully",
            metadata={'question': question}
        )
    except ImportError as e:
        return PipelineResult(
            step=PipelineStep.QUERY,
            success=False,
            error=f"Query processor not available: {e}"
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return PipelineResult(
            step=PipelineStep.QUERY,
            success=False,
            error=str(e)
        )


def run_consolidate(
    table_title: str,
    output_format: str = "both",  # "csv", "excel", or "both"
    output_dir: Optional[str] = None,
    transpose: bool = True
) -> PipelineResult:
    """
    Steps 8-9: Consolidate tables and export as timeseries.
    
    Args:
        table_title: Table title to search for
        output_format: Export format ("csv", "excel", or "both")
        output_dir: Output directory
        transpose: Transpose to timeseries format
        
    Returns:
        PipelineResult with consolidated data and export paths
    """
    from config.settings import settings
    
    try:
        from src.extraction.consolidation import get_quarterly_consolidator
        from src.embeddings.manager import get_embedding_manager
        from src.vector_store.manager import get_vectordb_manager
        
        vector_store = get_vectordb_manager()
        embedding_manager = get_embedding_manager()
        
        if output_dir is None:
            output_dir = getattr(settings, 'OUTPUT_DIR', 'outputs/consolidated_tables')
        
        # Initialize consolidator
        consolidator = get_quarterly_consolidator(vector_store, embedding_manager)
        
        # Find matching tables
        tables = consolidator.find_tables_by_title(table_title, top_k=50)
        
        if not tables:
            return PipelineResult(
                step=PipelineStep.CONSOLIDATE,
                success=False,
                error=f"No matching tables found for '{table_title}'"
            )
        
        # Consolidate
        df, metadata = consolidator.consolidate_tables(tables, table_name=table_title)
        
        if df.empty:
            return PipelineResult(
                step=PipelineStep.CONSOLIDATE,
                success=False,
                error="Failed to consolidate tables"
            )
        
        # Export
        export_paths = consolidator.export(df, table_title, metadata.get('date_range'))
        
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=True,
            data={
                'dataframe': df,
                'tables_found': len(tables),
                'export_paths': export_paths
            },
            message=f"Consolidated {len(tables)} tables, exported to {output_format}",
            metadata={
                'quarters_included': metadata.get('quarters_included', []),
                'total_rows': metadata.get('total_rows', 0),
                'total_columns': metadata.get('total_columns', 0)
            }
        )
    except ImportError as e:
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=False,
            error=f"Consolidator not available: {e}"
        )
    except Exception as e:
        logger.error(f"Consolidation failed: {e}")
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=False,
            error=str(e)
        )
