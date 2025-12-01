"""
Redis Vector backend for distributed VectorDB deployment.

Requires: redis-py, redis-om
Install: pip install redis redis-om
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from embeddings.unified_vectordb import UnifiedVectorDBInterface
from models.vectordb_schemas import (
    TableChunk,
    VectorDBStats,
    serialize_for_storage
)


class RedisVectorBackend(UnifiedVectorDBInterface):
    """
    Redis Vector backend for distributed deployment.
    
    Features:
    - Distributed storage
    - Horizontal scaling
    - Real-time updates
    - High availability
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        index_name: str = "financial_tables",
        dimension: int = 384
    ):
        """
        Initialize Redis Vector backend.
        
        Args:
            host: Redis host
            port: Redis port
            index_name: Index name
            dimension: Vector dimension
        """
        try:
            import redis
            from redis.commands.search.field import VectorField, TextField, NumericField, TagField
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        except ImportError:
            raise ImportError(
                "Redis packages not installed. "
                "Install with: pip install redis redis-om"
            )
        
        self.host = host
        self.port = port
        self.index_name = index_name
        self.dimension = dimension
        
        # Connect to Redis
        self.client = redis.Redis(
            host=host,
            port=port,
            decode_responses=False  # We'll handle encoding
        )
        
        # Test connection
        try:
            self.client.ping()
            print(f"✓ Redis Vector connected: {host}:{port}")
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")
        
        # Create index if not exists
        self._create_index()
    
    def _create_index(self):
        """Create Redis search index."""
        from redis.commands.search.field import VectorField, TextField, NumericField, TagField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        
        try:
            # Check if index exists
            self.client.ft(self.index_name).info()
            print(f"✓ Using existing index: {self.index_name}")
        except:
            # Create index
            schema = (
                TextField("content"),
                VectorField(
                    "embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.dimension,
                        "DISTANCE_METRIC": "COSINE"
                    }
                ),
                TextField("source_doc"),
                NumericField("page_no"),
                TextField("table_title"),
                NumericField("year"),
                TagField("quarter"),
                TagField("report_type"),
                NumericField("chunk_index"),
                NumericField("total_chunks")
            )
            
            definition = IndexDefinition(
                prefix=[f"{self.index_name}:"],
                index_type=IndexType.HASH
            )
            
            self.client.ft(self.index_name).create_index(
                schema,
                definition=definition
            )
            print(f"✓ Created index: {self.index_name}")
    
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ) -> None:
        """Add chunks to Redis Vector."""
        import numpy as np
        
        if not chunks:
            return
        
        for chunk in chunks:
            storage_format = serialize_for_storage(chunk)
            
            # Prepare document
            doc_id = f"{self.index_name}:{storage_format['id']}"
            
            # Prepare fields
            fields = {
                'content': storage_format['content'],
                'embedding': np.array(storage_format['embedding'] or [0.0] * self.dimension, dtype='float32').tobytes(),
                'source_doc': storage_format['metadata']['source_doc'],
                'page_no': storage_format['metadata']['page_no'],
                'table_title': storage_format['metadata'].get('table_title', ''),
                'year': storage_format['metadata']['year'],
                'quarter': storage_format['metadata'].get('quarter', ''),
                'report_type': storage_format['metadata'].get('report_type', ''),
                'chunk_index': storage_format.get('chunk_index', 0),
                'total_chunks': storage_format.get('total_chunks', 1),
                'metadata_json': json.dumps(storage_format['metadata'])
            }
            
            # Store in Redis
            self.client.hset(doc_id, mapping=fields)
        
        print(f"✓ Added {len(chunks)} chunks to Redis Vector")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search Redis Vector."""
        from redis.commands.search.query import Query
        import numpy as np
        
        # Convert query to bytes
        query_bytes = np.array(query_embedding, dtype='float32').tobytes()
        
        # Build query
        base_query = f"*=>[KNN {top_k} @embedding $vec AS score]"
        
        # Add filters
        if filters:
            filter_parts = []
            for key, value in filters.items():
                if key == 'year':
                    filter_parts.append(f"@year:[{value} {value}]")
                elif key == 'source_doc':
                    filter_parts.append(f"@source_doc:{value}")
            
            if filter_parts:
                base_query = "(" + " ".join(filter_parts) + ")=>[KNN " + str(top_k) + " @embedding $vec AS score]"
        
        q = Query(base_query).return_fields("content", "source_doc", "page_no", "metadata_json", "score").sort_by("score").dialect(2)
        
        # Execute search
        results = self.client.ft(self.index_name).search(
            q,
            query_params={"vec": query_bytes}
        )
        
        # Format results
        formatted_results = []
        for doc in results.docs:
            metadata = json.loads(doc.metadata_json) if hasattr(doc, 'metadata_json') else {}
            
            formatted_results.append({
                'id': doc.id.split(':')[-1],
                'content': doc.content,
                'metadata': metadata,
                'distance': float(doc.score) if hasattr(doc, 'score') else None
            })
        
        return formatted_results
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get by metadata from Redis Vector."""
        from redis.commands.search.query import Query
        
        # Build filter query
        filter_parts = []
        for key, value in filters.items():
            if key == 'year':
                filter_parts.append(f"@year:[{value} {value}]")
            elif key == 'source_doc':
                filter_parts.append(f"@source_doc:{value}")
        
        query_str = " ".join(filter_parts) if filter_parts else "*"
        q = Query(query_str).return_fields("content", "metadata_json").paging(0, limit)
        
        results = self.client.ft(self.index_name).search(q)
        
        formatted_results = []
        for doc in results.docs:
            metadata = json.loads(doc.metadata_json) if hasattr(doc, 'metadata_json') else {}
            
            formatted_results.append({
                'id': doc.id.split(':')[-1],
                'content': doc.content,
                'metadata': metadata
            })
        
        return formatted_results
    
    def delete_by_source(self, source_doc: str) -> None:
        """Delete by source from Redis Vector."""
        from redis.commands.search.query import Query
        
        # Find all documents from source
        q = Query(f"@source_doc:{source_doc}").return_fields("id")
        results = self.client.ft(self.index_name).search(q)
        
        # Delete each document
        for doc in results.docs:
            self.client.delete(doc.id)
        
        print(f"✓ Deleted {len(results.docs)} chunks from {source_doc}")
    
    def clear(self) -> None:
        """Clear Redis Vector index."""
        # Drop and recreate index
        try:
            self.client.ft(self.index_name).dropindex(delete_documents=True)
        except:
            pass
        
        self._create_index()
        print("✓ Redis Vector cleared")
    
    def get_stats(self) -> VectorDBStats:
        """Get Redis Vector statistics."""
        from redis.commands.search.query import Query
        
        # Get total count
        results = self.client.ft(self.index_name).search(Query("*").return_fields("source_doc", "year"))
        
        unique_sources = set()
        unique_years = set()
        
        for doc in results.docs:
            if hasattr(doc, 'source_doc'):
                unique_sources.add(doc.source_doc)
            if hasattr(doc, 'year'):
                unique_years.add(int(doc.year))
        
        return VectorDBStats(
            provider="redis",
            total_chunks=results.total,
            unique_documents=len(unique_sources),
            years=sorted(list(unique_years)),
            sources=sorted(list(unique_sources))
        )
    
    def export_data(self, output_path: str) -> None:
        """Export Redis Vector data."""
        from redis.commands.search.query import Query
        
        # Get all documents
        results = self.client.ft(self.index_name).search(
            Query("*").return_fields("content", "metadata_json").paging(0, 10000)
        )
        
        export_data = {
            'provider': 'redis',
            'index_name': self.index_name,
            'chunks': []
        }
        
        for doc in results.docs:
            metadata = json.loads(doc.metadata_json) if hasattr(doc, 'metadata_json') else {}
            
            export_data['chunks'].append({
                'id': doc.id.split(':')[-1],
                'content': doc.content,
                'metadata': metadata,
                'embedding': None
            })
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Exported {len(export_data['chunks'])} chunks to {output_path}")
    
    def import_data(self, input_path: str) -> None:
        """Import data to Redis Vector."""
        print("⚠️  Redis Vector import requires embeddings in source data")
