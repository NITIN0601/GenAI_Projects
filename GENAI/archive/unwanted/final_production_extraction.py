#!/usr/bin/env python3
"""
Production Docling extraction that extracts ALL tables from PDFs.
Stores results in vector DB with multi-level embeddings.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from typing import List, Dict, Any
import json
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from datetime import datetime

from scrapers.docling_scraper import DoclingPDFScraper
from embeddings.multi_level_embeddings import MultiLevelEmbeddingGenerator
from embeddings.embedding_manager import get_embedding_manager
from embeddings.vector_store import VectorStore

console = Console()


def extract_all_tables_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extract ALL tables from a PDF using Docling.
    No filtering - get everything.
    """
    filename = Path(pdf_path).name
    console.print(f"\n[bold cyan]Processing {filename} with Docling...[/bold cyan]")
    
    try:
        scraper = DoclingPDFScraper(pdf_path)
        document = scraper.extract_document()
        
        console.print(f"  [green]✓ Extracted {len(document.tables)} tables[/green]")
        console.print(f"  [green]✓ Total pages: {document.metadata.total_pages}[/green]")
        
        return {
            "success": True,
            "filename": filename,
            "document": document,
            "tables_count": len(document.tables),
            "metadata": {
                "company": document.metadata.company_name,
                "document_type": document.metadata.document_type,
                "total_pages": document.metadata.total_pages
            }
        }
        
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "filename": filename,
            "error": str(e)
        }


def generate_and_store_embeddings(
    document,
    filename: str,
    vector_store: VectorStore,
    embedding_levels: List[str] = ["table", "row"]
):
    """Generate multi-level embeddings and store in vector DB."""
    console.print(f"\n[cyan]Generating embeddings for {filename}...[/cyan]")
    
    # Get embedding manager
    embedding_manager = get_embedding_manager()
    
    # Create multi-level embedding generator
    generator = MultiLevelEmbeddingGenerator(embedding_model=embedding_manager.model)
    
    # Generate embeddings
    embeddings = generator.generate_document_embeddings(
        document,
        levels=embedding_levels
    )
    
    console.print(f"  [green]✓ Generated {len(embeddings)} embeddings[/green]")
    
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
        
        console.print(f"  [green]✓ Stored in vector database[/green]")
    
    return embeddings


def find_specific_table(document, search_terms: List[str]) -> List[Any]:
    """Find tables matching specific search terms."""
    matching_tables = []
    
    for table in document.tables:
        title_lower = table.original_title.lower()
        
        # Check if all search terms are in title
        if all(term.lower() in title_lower for term in search_terms):
            matching_tables.append(table)
            continue
        
        # Check row headers
        row_texts = " ".join([rh.text.lower() for rh in table.row_headers])
        if all(term.lower() in row_texts for term in search_terms):
            matching_tables.append(table)
    
    return matching_tables


def extract_contractual_principal_table(document) -> Dict[str, Any]:
    """Extract the specific 'Difference Between Contractual Principal and Fair Value' table."""
    # Search for the table
    search_terms = ["difference", "contractual", "principal", "fair value"]
    matching_tables = find_specific_table(document, search_terms)
    
    if not matching_tables:
        # Try alternative search
        search_terms = ["loans", "nonaccrual", "borrowings"]
        matching_tables = find_specific_table(document, search_terms)
    
    if not matching_tables:
        return None
    
    table = matching_tables[0]
    
    # Extract data
    result = {
        "title": table.original_title,
        "page": table.metadata.get("page_no"),
        "periods": [],
        "data": {}
    }
    
    # Extract periods from column headers
    for col_header in table.column_headers:
        if col_header.period:
            result["periods"].append(col_header.period.display_label)
    
    # Extract the three key rows
    for row_header in table.row_headers:
        text_lower = row_header.text.lower()
        canonical = (row_header.canonical_label or "").lower()
        
        # Find matching data cells
        row_cells = [cell for cell in table.data_cells if cell.row_header == row_header.text]
        values = [cell.parsed_value for cell in row_cells if cell.parsed_value is not None]
        
        # Categorize
        if ("loans" in text_lower and "debt" in text_lower) or ("loans" in text_lower and "receivable" in text_lower):
            result["data"]["loans_and_other_debt"] = {
                "label": row_header.text,
                "values": values
            }
        elif "nonaccrual" in text_lower and "loan" in text_lower:
            result["data"]["nonaccrual_loans"] = {
                "label": row_header.text,
                "values": values
            }
        elif "borrowing" in text_lower:
            result["data"]["borrowings"] = {
                "label": row_header.text,
                "values": values
            }
    
    return result if result["data"] else None


def process_all_pdfs(
    pdf_dir: str,
    extract_specific_table: bool = True,
    store_in_vector_db: bool = True
):
    """Process all PDFs in directory."""
    pdf_path = Path(pdf_dir)
    pdf_files = sorted(pdf_path.glob("*.pdf"))
    
    console.print(f"\n[bold]Found {len(pdf_files)} PDF(s)[/bold]\n")
    
    # Initialize vector store if needed
    vector_store = VectorStore() if store_in_vector_db else None
    
    all_results = []
    specific_tables = []
    
    for pdf_file in pdf_files:
        # Extract all tables
        result = extract_all_tables_from_pdf(str(pdf_file))
        all_results.append(result)
        
        if not result["success"]:
            continue
        
        document = result["document"]
        
        # Generate and store embeddings
        if store_in_vector_db and vector_store:
            embeddings = generate_and_store_embeddings(
                document,
                result["filename"],
                vector_store,
                embedding_levels=["table", "row"]
            )
            result["embeddings_count"] = len(embeddings)
        
        # Extract specific table if requested
        if extract_specific_table:
            specific = extract_contractual_principal_table(document)
            if specific:
                specific["source"] = result["filename"]
                specific_tables.append(specific)
                console.print(f"  [green]✓ Found contractual principal table[/green]")
    
    return all_results, specific_tables


def create_consolidated_table(specific_tables: List[Dict]) -> RichTable:
    """Create consolidated table from all extracted tables."""
    if not specific_tables:
        return None
    
    # Collect all periods
    all_periods = []
    period_data = {}
    
    for table_data in specific_tables:
        periods = table_data.get("periods", [])
        data = table_data.get("data", {})
        
        for i, period in enumerate(periods):
            if period not in all_periods:
                all_periods.append(period)
                period_data[period] = {}
            
            # Map data to period
            for category, cat_data in data.items():
                values = cat_data.get("values", [])
                if i < len(values):
                    period_data[period][category] = values[i]
    
    # Sort periods chronologically
    from dateutil import parser
    def parse_period(p):
        try:
            return parser.parse(p)
        except:
            return p
    
    sorted_periods = sorted(all_periods, key=parse_period)
    
    # Create table
    table = RichTable(
        title="Difference Between Contractual Principal and Fair Value ($ millions)",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )
    
    table.add_column("Category", style="cyan", width=30)
    for period in sorted_periods:
        table.add_column(period, justify="right", style="green")
    
    # Add rows
    categories = {
        "loans_and_other_debt": "Loans and other debt",
        "nonaccrual_loans": "Nonaccrual loans",
        "borrowings": "Borrowings"
    }
    
    for cat_key, cat_label in categories.items():
        row_data = [cat_label]
        for period in sorted_periods:
            value = period_data.get(period, {}).get(cat_key)
            if value is not None:
                if value < 0:
                    row_data.append(f"$({abs(value):,})")
                else:
                    row_data.append(f"${value:,}")
            else:
                row_data.append("—")
        
        table.add_row(*row_data)
    
    return table


if __name__ == "__main__":
    console.print("\n[bold cyan]{'='*70}[/bold cyan]")
    console.print("[bold cyan]Production Docling Extraction with Vector DB Storage[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]")
    
    # Process all PDFs
    all_results, specific_tables = process_all_pdfs(
        "../raw_data",
        extract_specific_table=True,
        store_in_vector_db=True
    )
    
    # Summary
    console.print(f"\n[bold green]{'='*70}[/bold green]")
    console.print(f"[bold green]Extraction Complete![/bold green]")
    console.print(f"[bold green]{'='*70}[/bold green]\n")
    
    successful = [r for r in all_results if r.get("success")]
    total_tables = sum(r.get("tables_count", 0) for r in successful)
    total_embeddings = sum(r.get("embeddings_count", 0) for r in successful)
    
    console.print(f"  PDFs Processed: {len(successful)}/{len(all_results)}")
    console.print(f"  Total Tables: {total_tables}")
    console.print(f"  Total Embeddings: {total_embeddings}")
    console.print(f"  Contractual Principal Tables Found: {len(specific_tables)}")
    
    # Show consolidated table
    if specific_tables:
        console.print("\n")
        consolidated = create_consolidated_table(specific_tables)
        if consolidated:
            console.print(consolidated)
        
        # Save results
        output_file = "final_contractual_principal_consolidated.json"
        with open(output_file, 'w') as f:
            json.dump({
                "extraction_date": datetime.utcnow().isoformat(),
                "total_pdfs": len(all_results),
                "tables_found": len(specific_tables),
                "tables": specific_tables
            }, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ Results saved to {output_file}[/green]")
