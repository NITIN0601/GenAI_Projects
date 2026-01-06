"""
Embed Step - Generate embeddings and store in VectorDB.

Implements StepInterface following system architecture pattern.
Uses infrastructure managers (same pattern as rest of system).
"""

import hashlib
from typing import Dict, Any
from tqdm import tqdm

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class EmbedStep(StepInterface):
    """
    Generate embeddings and store in VectorDB.
    
    Implements StepInterface (like VectorDBInterface pattern).
    Uses infrastructure managers (EmbeddingManager, VectorDBManager).
    
    Reads: context.extracted_data
    Writes: context.chunks
    """
    
    name = "embed"
    
    def __init__(self, store_in_vectordb: bool = True):
        self.store_in_vectordb = store_in_vectordb
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate extracted data exists."""
        if not context.extracted_data:
            logger.error("No extracted data - run ExtractStep first")
            return False
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        from config.settings import settings
        return {
            "name": self.name,
            "description": "Generate embeddings and store in VectorDB",
            "reads": ["context.extracted_data"],
            "writes": ["context.chunks"],
            "store_in_vectordb": self.store_in_vectordb,
            "vectordb_provider": settings.VECTORDB_PROVIDER,
            "embedding_provider": settings.EMBEDDING_PROVIDER
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Generate embeddings and store."""
        from config.settings import settings
        from src.infrastructure.embeddings.manager import get_embedding_manager
        from src.infrastructure.vectordb.manager import get_vectordb_manager
        from src.domain.tables import TableChunk, TableMetadata
        
        # Use infrastructure managers (standard pattern)
        embedding_manager = get_embedding_manager()
        vector_store = get_vectordb_manager() if self.store_in_vectordb else None
        
        vectordb_provider = settings.VECTORDB_PROVIDER
        embedding_model = embedding_manager.get_model_name()
        embedding_provider = settings.EMBEDDING_PROVIDER
        
        all_chunks = []
        stats = {
            'total_embeddings': 0,
            'stored': 0,
            'vectordb_provider': vectordb_provider,
            'embedding_model': embedding_model
        }
        
        total_tables = sum(len(doc.get('tables', [])) for doc in context.extracted_data)
        
        try:
            pbar = tqdm(
                total=total_tables,
                desc="Embedding",
                unit="table",
                ncols=80,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
            
            for doc_result in context.extracted_data:
                filename = doc_result['file']
                pbar.set_description(f"{filename[:25]}")
                
                pdf_hash = hashlib.md5(filename.encode()).hexdigest()
                
                for i, table in enumerate(doc_result.get('tables', [])):
                    # Handle table formats
                    if hasattr(table, 'content'):
                        content = table.content
                        table_meta = table.metadata if hasattr(table, 'metadata') else {}
                        if hasattr(table_meta, 'model_dump'):
                            table_meta = table_meta.model_dump()
                    else:
                        content = table.get('content', '')
                        table_meta = table.get('metadata', {})
                    
                    if not content:
                        pbar.update(1)
                        continue
                    
                    # Use embedding manager
                    embedding = embedding_manager.generate_embedding(content)
                    
                    metadata_dict = doc_result.get('metadata', {})
                    
                    metadata = TableMetadata.from_extraction(
                        table_meta=table_meta,
                        doc_metadata=metadata_dict,
                        filename=filename,
                        table_index=i,
                        embedding=embedding,
                        embedding_model=embedding_model,
                        embedding_provider=embedding_provider,
                    )
                    
                    chunk = TableChunk(
                        chunk_id=f"{pdf_hash}_{i}",
                        content=content,
                        embedding=embedding,
                        metadata=metadata
                    )
                    
                    all_chunks.append(chunk)
                    stats['total_embeddings'] += 1
                    pbar.update(1)
            
            pbar.set_description("Embedding Complete")
            pbar.close()
            
            # Store using vectordb manager
            if self.store_in_vectordb and all_chunks:
                store_pbar = tqdm(
                    total=1,
                    desc=f"Storing in {vectordb_provider.upper()}",
                    ncols=80,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
                )
                vector_store.add_chunks(all_chunks)
                stats['stored'] = len(all_chunks)
                store_pbar.update(1)
                store_pbar.set_description(f"Stored {len(all_chunks)} chunks")
                store_pbar.close()
            
            # Write to context
            context.chunks = all_chunks
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data=all_chunks,
                message=f"Generated {stats['total_embeddings']} embeddings, stored {stats['stored']}",
                metadata=stats
            )
            
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py
def run_embed(
    extracted_data: list = None,
    source_dir: str = None,
    store_in_vectordb: bool = True
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    from src.pipeline.steps.extract import ExtractStep
    
    # If no extracted_data, run extract first
    ctx = PipelineContext(source_dir=source_dir)
    if extracted_data:
        ctx.extracted_data = extracted_data
    else:
        extract_step = ExtractStep()
        if extract_step.validate(ctx):
            extract_result = extract_step.execute(ctx)
            if extract_result.failed:
                return PipelineResult(
                    step=PipelineStep.EMBED,
                    success=False,
                    error=f"Extract failed: {extract_result.error}"
                )
    
    step = EmbedStep(store_in_vectordb=store_in_vectordb)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="embed",
        status=StepStatus.FAILED,
        error="No extracted data available"
    )
    
    return PipelineResult(
        step=PipelineStep.EMBED,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
