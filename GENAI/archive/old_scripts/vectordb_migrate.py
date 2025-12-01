#!/usr/bin/env python3
"""
VectorDB Migration Tool

Migrate data between different VectorDB backends:
- ChromaDB → FAISS
- ChromaDB → Redis Vector
- FAISS → ChromaDB
- Redis Vector → ChromaDB

Usage:
    python3 vectordb_migrate.py --from chromadb --to faiss
    python3 vectordb_migrate.py --from faiss --to redis --host localhost
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

import argparse
from pathlib import Path
from embeddings.unified_vectordb import get_unified_vectordb
from embeddings.redis_vector_backend import RedisVectorBackend
from models.vectordb_schemas import TableChunk, TableMetadata
import json


def migrate_vectordb(
    source_provider: str,
    target_provider: str,
    source_config: dict = None,
    target_config: dict = None
):
    """
    Migrate data from one VectorDB to another.
    
    Args:
        source_provider: Source VectorDB (chromadb, faiss, redis)
        target_provider: Target VectorDB (chromadb, faiss, redis)
        source_config: Source configuration
        target_config: Target configuration
    """
    source_config = source_config or {}
    target_config = target_config or {}
    
    print("=" * 80)
    print("VECTORDB MIGRATION")
    print("=" * 80)
    print(f"\nSource: {source_provider}")
    print(f"Target: {target_provider}")
    print()
    
    # Initialize source
    print(f"1. Connecting to source ({source_provider})...")
    if source_provider == "redis":
        source_db = RedisVectorBackend(**source_config)
    else:
        source_db = get_unified_vectordb(source_provider, **source_config)
    
    # Get stats
    source_stats = source_db.get_stats()
    print(f"   ✓ Found {source_stats.total_chunks} chunks")
    print(f"   ✓ {source_stats.unique_documents} unique documents")
    
    # Export data
    print(f"\n2. Exporting data from {source_provider}...")
    export_path = f"./vectordb_export_{source_provider}.json"
    source_db.export_data(export_path)
    
    # Initialize target
    print(f"\n3. Connecting to target ({target_provider})...")
    if target_provider == "redis":
        target_db = RedisVectorBackend(**target_config)
    else:
        target_db = get_unified_vectordb(target_provider, **target_config)
    
    # Import data
    print(f"\n4. Importing data to {target_provider}...")
    
    # Load export file
    with open(export_path, 'r') as f:
        export_data = json.load(f)
    
    chunks_data = export_data['chunks']
    
    # Convert to TableChunk objects
    chunks = []
    for chunk_data in chunks_data:
        try:
            chunk = TableChunk(
                chunk_id=chunk_data['id'],
                content=chunk_data['content'],
                metadata=TableMetadata(**chunk_data['metadata']),
                embedding=chunk_data.get('embedding')
            )
            chunks.append(chunk)
        except Exception as e:
            print(f"   ⚠️  Skipping chunk {chunk_data.get('id')}: {e}")
    
    # Add to target
    if chunks:
        target_db.add_chunks(chunks, show_progress=True)
    
    # Verify
    print(f"\n5. Verifying migration...")
    target_stats = target_db.get_stats()
    print(f"   ✓ Target has {target_stats.total_chunks} chunks")
    
    # Cleanup
    Path(export_path).unlink()
    
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print(f"\nMigrated {len(chunks)} chunks from {source_provider} to {target_provider}")
    print(f"Source: {source_stats.total_chunks} chunks")
    print(f"Target: {target_stats.total_chunks} chunks")
    
    if source_stats.total_chunks == target_stats.total_chunks:
        print("\n✓ Migration successful - chunk counts match!")
    else:
        print(f"\n⚠️  Warning: Chunk count mismatch")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Migrate VectorDB data')
    parser.add_argument('--from', dest='source', required=True,
                       choices=['chromadb', 'faiss', 'redis'],
                       help='Source VectorDB')
    parser.add_argument('--to', dest='target', required=True,
                       choices=['chromadb', 'faiss', 'redis'],
                       help='Target VectorDB')
    
    # Source config
    parser.add_argument('--source-dir', default='./vectordb/chroma',
                       help='Source directory')
    parser.add_argument('--source-host', default='localhost',
                       help='Source Redis host')
    parser.add_argument('--source-port', type=int, default=6379,
                       help='Source Redis port')
    
    # Target config
    parser.add_argument('--target-dir', default='./vectordb/faiss',
                       help='Target directory')
    parser.add_argument('--target-host', default='localhost',
                       help='Target Redis host')
    parser.add_argument('--target-port', type=int, default=6379,
                       help='Target Redis port')
    
    args = parser.parse_args()
    
    # Build configs
    source_config = {}
    target_config = {}
    
    if args.source == 'chromadb':
        source_config = {'persist_directory': args.source_dir}
    elif args.source == 'faiss':
        source_config = {'persist_directory': args.source_dir}
    elif args.source == 'redis':
        source_config = {'host': args.source_host, 'port': args.source_port}
    
    if args.target == 'chromadb':
        target_config = {'persist_directory': args.target_dir}
    elif args.target == 'faiss':
        target_config = {'persist_directory': args.target_dir}
    elif args.target == 'redis':
        target_config = {'host': args.target_host, 'port': args.target_port}
    
    # Run migration
    migrate_vectordb(
        source_provider=args.source,
        target_provider=args.target,
        source_config=source_config,
        target_config=target_config
    )


if __name__ == '__main__':
    main()
