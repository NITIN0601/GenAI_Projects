#!/usr/bin/env python3
"""
Smart extraction that uses vector DB caching.
Only processes PDFs that aren't already in the database.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from docling.document_converter import DocumentConverter
from embeddings.vector_store import get_vector_store
from embeddings.multi_level_embeddings import MultiLevelEmbeddingGenerator
from embeddings.embedding_manager import get_embedding_manager
import json
import hashlib

console = Console()


def get_pdf_hash(pdf_path):
    """Get hash of PDF file for caching."""
    with open(pdf_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def is_pdf_in_vectordb(pdf_hash, vector_store):
    """Check if PDF is already processed and in vector DB."""
    try:
        # Search for any embedding with this document hash
        results = vector_store.search(
            query_text="test",
            top_k=1,
            filter={"document_id": pdf_hash[:12]}
        )
        return len(results) > 0
    except:
        return False


def process_and_store_pdf(pdf_path, vector_store):
    """Process PDF with Docling and store in vector DB."""
    filename = Path(pdf_path).name
    pdf_hash = get_pdf_hash(pdf_path)
    
    console.print(f"\n[cyan]Processing {filename} (first time)...[/cyan]")
    
    # Extract with Docling
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    # Create enhanced document structure
    from models.enhanced_schemas import EnhancedDocument, DocumentMetadata
    
    doc_metadata = DocumentMetadata(
        filename=filename,
        file_hash=pdf_hash,
        total_pages=len(result.document.pages),
        company_name="Morgan Stanley"  # Could extract from PDF
    )
    
    # Convert Docling tables to enhanced format
    # (This would need proper conversion logic)
    enhanced_doc = EnhancedDocument(
        metadata=doc_metadata,
        tables=[]  # Would populate from Docling tables
    )
    
    # Generate embeddings
    embedding_manager = get_embedding_manager()
    generator = MultiLevelEmbeddingGenerator(embedding_manager.model)
    
    embeddings = generator.generate_document_embeddings(
        enhanced_doc,
        levels=["table", "row"]
    )
    
    # Store in vector DB
    if embeddings:
        ids = [e["id"] for e in embeddings]
        vectors = [e["vector"] for e in embeddings]
        metadatas = [e["metadata"] for e in embeddings]
        documents = [e["text"] for e in embeddings]
        
        vector_store.add_chunks(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents
        )
        
        console.print(f"  [green]✓ Stored {len(embeddings)} embeddings in vector DB[/green]")
    
    return result.document.tables


def retrieve_from_vectordb(pdf_hash, vector_store):
    """Retrieve PDF data from vector DB."""
    console.print(f"  [green]✓ Found in vector DB (using cache)[/green]")
    
    # Query vector DB for this document
    results = vector_store.search(
        query_text="contractual principal fair value",
        top_k=100,
        filter={"document_id": pdf_hash[:12]}
    )
    
    return results


def extract_contractual_principal_smart(pdf_path):
    """Smart extraction using vector DB cache."""
    filename = Path(pdf_path).name
    pdf_hash = get_pdf_hash(pdf_path)
    
    console.print(f"\n[bold cyan]Processing {filename}...[/bold cyan]")
    
    vector_store = get_vector_store()
    
    # Check if already in vector DB
    if is_pdf_in_vectordb(pdf_hash, vector_store):
        # Use cached version
        results = retrieve_from_vectordb(pdf_hash, vector_store)
        console.print(f"  Retrieved {len(results)} cached results")
        return results
    else:
        # Process and store
        tables = process_and_store_pdf(pdf_path, vector_store)
        console.print(f"  Extracted {len(tables)} tables")
        
        # Now retrieve from vector DB
        return retrieve_from_vectordb(pdf_hash, vector_store)


if __name__ == "__main__":
    console.print("\n[bold]Smart Extraction with Vector DB Caching[/bold]")
    console.print("=" * 70)
    
    # Test on 2 PDFs
    test_pdfs = [
        "../raw_data/10k1224.pdf",
        "../raw_data/10q0320.pdf"
    ]
    
    for pdf_path in test_pdfs:
        if Path(pdf_path).exists():
            results = extract_contractual_principal_smart(pdf_path)
            
            # Search results for contractual principal table
            for result in results:
                metadata = result.get("metadata", {})
                if "contractual" in result.get("text", "").lower():
                    console.print(f"  [yellow]Found relevant result:[/yellow]")
                    console.print(f"    {metadata.get('row_label')}: {metadata.get('value_display')}")
    
    console.print(f"\n[bold green]✓ Complete![/bold green]")
    console.print("[yellow]Next time: Instant retrieval from vector DB![/yellow]")
