"""
Production PDF processing pipeline with Docling extraction and vector DB storage.
Implements dynamic table extraction without hardcoding.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from typing import List, Dict, Any
import json
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from datetime import datetime

from scrapers.docling_scraper import DoclingPDFScraper
from embeddings.multi_level_embeddings import MultiLevelEmbeddingGenerator
from embeddings.vector_store import VectorStore
from embeddings.embedding_manager import EmbeddingManager
from cache.redis_cache import RedisCache

console = Console()


class ProductionPDFProcessor:
    """Production-ready PDF processor with vector DB storage."""
    
    def __init__(
        self,
        vector_store: VectorStore = None,
        embedding_manager: EmbeddingManager = None,
        cache: RedisCache = None,
        embedding_levels: List[str] = ["table", "row"]
    ):
        """
        Initialize processor.
        
        Args:
            vector_store: Vector database for storage
            embedding_manager: Embedding generation
            cache: Redis cache for avoiding re-processing
            embedding_levels: Which levels to generate ("table", "row", "cell")
        """
        self.vector_store = vector_store or VectorStore()
        self.embedding_manager = embedding_manager or EmbeddingManager()
        self.cache = cache
        self.embedding_levels = embedding_levels
        
        # Initialize multi-level embedding generator
        self.embedding_generator = MultiLevelEmbeddingGenerator(
            embedding_model=self.embedding_manager.model
        )
    
    def process_pdf(
        self,
        pdf_path: str,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Process a single PDF: extract tables, generate embeddings, store in vector DB.
        
        Args:
            pdf_path: Path to PDF file
            force_reprocess: If True, reprocess even if cached
        
        Returns:
            Processing result with stats
        """
        filename = Path(pdf_path).name
        console.print(f"\n[bold cyan]Processing {filename}...[/bold cyan]")
        
        # Check cache
        if self.cache and not force_reprocess:
            cached = self.cache.get_pdf_parse(pdf_path)
            if cached:
                console.print(f"  [yellow]Using cached extraction[/yellow]")
                document = cached
            else:
                document = self._extract_with_docling(pdf_path)
                if document:
                    self.cache.set_pdf_parse(pdf_path, document)
        else:
            document = self._extract_with_docling(pdf_path)
        
        if not document:
            return {"success": False, "error": "Extraction failed"}
        
        # Generate embeddings at multiple levels
        console.print(f"  [cyan]Generating embeddings ({', '.join(self.embedding_levels)} levels)...[/cyan]")
        embeddings = self.embedding_generator.generate_document_embeddings(
            document,
            levels=self.embedding_levels
        )
        
        console.print(f"  [green]✓ Generated {len(embeddings)} embeddings[/green]")
        
        # Store in vector database
        console.print(f"  [cyan]Storing in vector database...[/cyan]")
        self._store_embeddings(embeddings)
        
        # Build result
        result = {
            "success": True,
            "filename": filename,
            "tables_extracted": len(document.tables),
            "embeddings_generated": len(embeddings),
            "embedding_breakdown": {
                level: len([e for e in embeddings if e["metadata"]["embedding_level"] == level])
                for level in self.embedding_levels
            },
            "document_metadata": {
                "company": document.metadata.company_name,
                "document_type": document.metadata.document_type,
                "total_pages": document.metadata.total_pages
            }
        }
        
        console.print(f"  [bold green]✓ Complete: {result['tables_extracted']} tables, {result['embeddings_generated']} embeddings[/bold green]")
        
        return result
    
    def process_directory(
        self,
        directory_path: str,
        pattern: str = "*.pdf",
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Process all PDFs in a directory.
        
        Args:
            directory_path: Directory containing PDFs
            pattern: File pattern to match
            force_reprocess: If True, reprocess all files
        
        Returns:
            Summary of processing results
        """
        pdf_dir = Path(directory_path)
        pdf_files = sorted(pdf_dir.glob(pattern))
        
        if not pdf_files:
            console.print(f"[red]No PDFs found in {directory_path}[/red]")
            return {"success": False, "error": "No PDFs found"}
        
        console.print(f"\n[bold]Found {len(pdf_files)} PDF(s) to process[/bold]\n")
        
        results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            
            task = progress.add_task("[cyan]Processing PDFs...", total=len(pdf_files))
            
            for pdf_path in pdf_files:
                result = self.process_pdf(str(pdf_path), force_reprocess)
                results.append(result)
                progress.update(task, advance=1)
        
        # Summary
        successful = [r for r in results if r.get("success")]
        total_tables = sum(r.get("tables_extracted", 0) for r in successful)
        total_embeddings = sum(r.get("embeddings_generated", 0) for r in successful)
        
        summary = {
            "success": True,
            "total_pdfs": len(pdf_files),
            "successful": len(successful),
            "failed": len(pdf_files) - len(successful),
            "total_tables": total_tables,
            "total_embeddings": total_embeddings,
            "embedding_levels": self.embedding_levels,
            "results": results
        }
        
        return summary
    
    def _extract_with_docling(self, pdf_path: str):
        """Extract document using Docling."""
        try:
            scraper = DoclingPDFScraper(pdf_path)
            document = scraper.extract_document()
            return document
        except Exception as e:
            console.print(f"  [red]✗ Extraction error: {e}[/red]")
            return None
    
    def _store_embeddings(self, embeddings: List[Dict[str, Any]]):
        """Store embeddings in vector database."""
        if not embeddings:
            return
        
        # Prepare for vector store
        ids = [e["id"] for e in embeddings]
        vectors = [e["vector"] for e in embeddings]
        metadatas = [e["metadata"] for e in embeddings]
        documents = [e["text"] for e in embeddings]
        
        # Add to vector store
        self.vector_store.add_chunks(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents
        )


def main():
    """Main entry point for production processing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Production PDF Processing Pipeline")
    parser.add_argument("--source", required=True, help="PDF file or directory")
    parser.add_argument("--levels", nargs="+", default=["table", "row"], 
                       choices=["table", "row", "cell"],
                       help="Embedding levels to generate")
    parser.add_argument("--force", action="store_true", help="Force reprocessing")
    parser.add_argument("--output", help="Output JSON file for results")
    
    args = parser.parse_args()
    
    console.print("\n[bold cyan]{'='*70}[/bold cyan]")
    console.print("[bold cyan]Production PDF Processing Pipeline[/bold cyan]")
    console.print(f"[bold cyan]Embedding Levels: {', '.join(args.levels)}[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]")
    
    # Initialize processor
    processor = ProductionPDFProcessor(
        embedding_levels=args.levels
    )
    
    # Process
    source_path = Path(args.source)
    
    if source_path.is_file():
        result = processor.process_pdf(str(source_path), args.force)
        summary = {"results": [result]}
    else:
        summary = processor.process_directory(str(source_path), force_reprocess=args.force)
    
    # Display summary
    console.print(f"\n[bold green]{'='*70}[/bold green]")
    console.print(f"[bold green]Processing Complete![/bold green]")
    console.print(f"[bold green]{'='*70}[/bold green]\n")
    
    if summary.get("success"):
        console.print(f"  PDFs Processed: {summary.get('successful', 1)}/{summary.get('total_pdfs', 1)}")
        console.print(f"  Tables Extracted: {summary.get('total_tables', 0)}")
        console.print(f"  Embeddings Generated: {summary.get('total_embeddings', 0)}")
        console.print(f"  Embedding Levels: {', '.join(args.levels)}")
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        console.print(f"\n[green]✓ Results saved to {args.output}[/green]")


if __name__ == "__main__":
    main()
