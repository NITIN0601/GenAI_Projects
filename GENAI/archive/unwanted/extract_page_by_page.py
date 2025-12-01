#!/usr/bin/env python3
"""
Optimized Page-by-Page PDF Extraction with Docling

⚠️ DEPRECATED: This module is deprecated in favor of the unified extraction system.
Please use extraction.UnifiedExtractor instead.

This file is kept for backward compatibility and will be removed in a future version.

Migration:
    OLD:
        from extract_page_by_page import PageByPageExtractor
        extractor = PageByPageExtractor(pdf_path)
        result = extractor.extract_document()
    
    NEW:
        from extraction import UnifiedExtractor
        extractor = UnifiedExtractor()
        result = extractor.extract(pdf_path)

Features:
- Process each page individually with document intelligence
- Detect 2-sided layouts and facing pages
- Extract tables with full hierarchical context
- Merge multi-page tables automatically
- Intelligent chunking with overlap
"""

import warnings
warnings.warn(
    "extract_page_by_page is deprecated. Use extraction.UnifiedExtractor instead.",
    DeprecationWarning,
    stacklevel=2
)

import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel, TableItem
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from models.schemas import TableMetadata, TableChunk
from embeddings.vector_store import get_vector_store

console = Console()


class PageByPageExtractor:
    """
    Optimized page-by-page PDF extractor with document intelligence.
    
    Key Features:
    - Page-level processing with context preservation
    - Two-sided page detection and intelligent merging
    - Section hierarchy tracking across pages
    - Metadata alignment with TableMetadata schema
    - Batch processing with progress tracking
    """
    
    def __init__(self, pdf_path: str, vector_store=None):
        """
        Initialize extractor.
        
        Args:
            pdf_path: Path to PDF file
            vector_store: Optional vector store instance
        """
        self.pdf_path = Path(pdf_path)
        self.filename = self.pdf_path.name
        self.vector_store = vector_store or get_vector_store()
        
        # Initialize Docling converter
        self.converter = DocumentConverter()
        
        # Document state
        self.file_hash = self._compute_file_hash()
        self.year = self._extract_year()
        self.quarter = self._extract_quarter()
        self.report_type = self._extract_report_type()
        
        # Section tracking across pages
        self.current_headings = {
            1: None,  # H1
            2: None,  # H2
            3: None,  # H3
            4: None,  # H4
        }
        
        console.print(f"\n[bold cyan]Initializing extractor for {self.filename}[/bold cyan]")
        console.print(f"  Report Type: {self.report_type}")
        console.print(f"  Year: {self.year}")
        console.print(f"  Quarter: {self.quarter or 'N/A (Annual)'}")
    
    def _compute_file_hash(self) -> str:
        """Compute MD5 hash of PDF file."""
        with open(self.pdf_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _extract_year(self) -> int:
        """Extract year from filename (e.g., 10q0925.pdf -> 2025)."""
        match = re.search(r'10[qk]\d{2}(\d{2})', self.filename.lower())
        if match:
            year_suffix = int(match.group(1))
            return 2000 + year_suffix
        return datetime.now().year
    
    def _extract_quarter(self) -> Optional[str]:
        """Extract quarter from filename (e.g., 10q0925.pdf -> Q3)."""
        match = re.search(r'10q(\d{2})\d{2}', self.filename.lower())
        if match:
            month = int(match.group(1))
            if month in [1, 2, 3]:
                return "Q1"
            elif month in [4, 5, 6]:
                return "Q2"
            elif month in [7, 8, 9]:
                return "Q3"
            elif month in [10, 11, 12]:
                return "Q4"
        return None
    
    def _extract_report_type(self) -> str:
        """Extract report type from filename."""
        if '10k' in self.filename.lower():
            return "10-K"
        elif '10q' in self.filename.lower():
            return "10-Q"
        return "Unknown"
    
    def extract_document(self) -> Dict[str, Any]:
        """
        Extract complete document page-by-page.
        
        Returns:
            Extraction results with statistics
        """
        console.print(f"\n[bold green]Starting extraction...[/bold green]")
        
        # Convert PDF with Docling
        result = self.converter.convert(str(self.pdf_path))
        doc = result.document
        
        total_pages = len(doc.pages) if hasattr(doc, 'pages') else 1
        console.print(f"  Total pages: {total_pages}")
        
        # Process all items (not page-by-page filtering, but track pages)
        all_chunks = []
        tables_by_page = defaultdict(int)
        
        console.print(f"\n[cyan]Extracting tables from document...[/cyan]")
        
        # Iterate through ALL document items
        for item in doc.iterate_items():
            # Update section context
            if item.label == DocItemLabel.SECTION_HEADER:
                self._update_section_context(item)
            
            # Extract tables
            elif item.label == DocItemLabel.TABLE:
                # Get page number from table
                page_no = self._get_item_page(item)
                
                # Extract table chunks
                table_chunks = self._extract_table_chunks(item, page_no)
                all_chunks.extend(table_chunks)
                tables_by_page[page_no] += 1
                
                console.print(f"  [green]✓[/green] Table on page {page_no}: {table_chunks[0].metadata.table_title[:60]}...")
        
        # Detect and merge multi-page tables
        merged_chunks = self._merge_multi_page_tables(all_chunks)
        
        # Summary
        total_tables = len(all_chunks)
        total_chunks = len(merged_chunks)
        
        console.print(f"\n[bold green]✓ Extraction complete![/bold green]")
        console.print(f"  Pages processed: {total_pages}")
        console.print(f"  Tables extracted: {total_tables}")
        console.print(f"  Chunks created: {total_chunks}")
        
        # Show tables per page
        if tables_by_page:
            console.print(f"\n[bold]Tables per page:[/bold]")
            for page in sorted(tables_by_page.keys())[:10]:  # Show first 10
                console.print(f"  Page {page}: {tables_by_page[page]} tables")
            if len(tables_by_page) > 10:
                console.print(f"  ... and {len(tables_by_page) - 10} more pages")
        
        return {
            'filename': self.filename,
            'total_pages': total_pages,
            'total_tables': total_tables,
            'total_chunks': total_chunks,
            'chunks': merged_chunks,
            'tables_by_page': dict(tables_by_page)
        }
    
    def _get_item_page(self, item) -> int:
        """Get page number for an item."""
        if hasattr(item, 'prov') and item.prov:
            # Get first page number from provenance
            for p in item.prov:
                if hasattr(p, 'page_no'):
                    return p.page_no
        return 1  # Default to page 1
    
    def _process_page(self, doc, page_no: int) -> Dict[str, Any]:
        """
        Process a single page with document intelligence.
        
        Args:
            doc: Docling document
            page_no: Page number (1-indexed)
        
        Returns:
            Page processing results
        """
        # Get all items on this page
        page_items = [
            item for item in doc.iterate_items()
            if hasattr(item, 'prov') and item.prov and 
            any(p.page_no == page_no for p in item.prov)
        ]
        
        if not page_items:
            return {
                'page_no': page_no,
                'chunks': [],
                'stats': {'tables': 0, 'headings': 0}
            }
        
        # Track section headings
        headings_found = 0
        
        # Process items
        chunks = []
        tables_found = 0
        
        for item in page_items:
            # Update section context
            if item.label == DocItemLabel.SECTION_HEADER:
                self._update_section_context(item)
                headings_found += 1
            
            # Extract tables
            elif item.label == DocItemLabel.TABLE:
                table_chunks = self._extract_table_chunks(item, page_no)
                chunks.extend(table_chunks)
                tables_found += len(table_chunks)
        
        return {
            'page_no': page_no,
            'chunks': chunks,
            'stats': {
                'tables': tables_found,
                'headings': headings_found
            }
        }
    
    def _update_section_context(self, heading_item):
        """Update current section heading hierarchy."""
        # Determine heading level from Docling reference
        level = heading_item.self_ref.split('.').count('.')
        if level == 0:
            level = 1
        
        heading_text = heading_item.text if hasattr(heading_item, 'text') else str(heading_item)
        
        # Update current headings
        self.current_headings[level] = heading_text
        
        # Clear lower levels
        for l in range(level + 1, 5):
            self.current_headings[l] = None
    
    def _extract_table_chunks(self, table_item: TableItem, page_no: int) -> List[TableChunk]:
        """
        Extract table and create chunks with metadata.
        
        NOW WITH CHUNKING + OVERLAP for better vector search!
        
        Args:
            table_item: Docling table item
            page_no: Page number
        
        Returns:
            List of TableChunk objects (may be multiple chunks per table)
        """
        # Get table caption/title
        table_title = table_item.caption if hasattr(table_item, 'caption') else f"Table on page {page_no}"
        if not table_title:
            table_title = f"Table on page {page_no}"
        
        # Get table content
        table_text = table_item.export_to_markdown() if hasattr(table_item, 'export_to_markdown') else str(table_item.text)
        
        # Detect table type
        table_type = self._classify_table_type(table_title)
        
        # Extract fiscal period from table
        fiscal_period = self._extract_fiscal_period(table_text)
        
        # Build heading path
        heading_path_parts = [h for h in [
            self.current_headings.get(1),
            self.current_headings.get(2),
            self.current_headings.get(3),
            self.current_headings.get(4)
        ] if h]
        heading_path = ' > '.join(heading_path_parts) if heading_path_parts else None
        
        # Create base metadata
        metadata = TableMetadata(
            source_doc=self.filename,
            page_no=page_no,
            table_title=table_title,
            year=self.year,
            quarter=self.quarter,
            report_type=self.report_type,
            table_type=table_type,
            fiscal_period=fiscal_period,
            extraction_date=datetime.now()
        )
        
        # CHUNKING STRATEGY: Decide based on table size
        table_lines = table_text.split('\n')
        num_rows = len([line for line in table_lines if line.strip() and '|' in line])
        
        if num_rows <= 15:
            # Small table: Single chunk
            chunks = [TableChunk(
                content=table_text,
                metadata=metadata,
                embedding=None
            )]
        else:
            # Large table: Create overlapping chunks
            from embeddings.table_chunker import create_chunked_embeddings
            
            # Use sliding window with overlap
            chunks = create_chunked_embeddings(
                table_text=table_text,
                metadata=metadata,
                chunking_strategy="sliding_window",
                chunk_size=10,   # 10 rows per chunk
                overlap=3        # 3 rows overlap
            )
        
        return chunks
    
    def _classify_table_type(self, title: str) -> Optional[str]:
        """Classify table type from title."""
        title_lower = title.lower()
        
        if 'balance sheet' in title_lower or 'financial condition' in title_lower:
            return "Balance Sheet"
        elif 'income statement' in title_lower or 'earnings' in title_lower or 'operations' in title_lower:
            return "Income Statement"
        elif 'cash flow' in title_lower:
            return "Cash Flow Statement"
        elif 'equity' in title_lower:
            return "Equity Statement"
        elif 'segment' in title_lower:
            return "Segment Information"
        elif 'fair value' in title_lower:
            return "Fair Value"
        elif 'derivative' in title_lower:
            return "Derivatives"
        elif 'contractual principal' in title_lower:
            return "Contractual Principal"
        else:
            return None
    
    def _extract_fiscal_period(self, table_text: str) -> Optional[str]:
        """Extract fiscal period from table headers."""
        # Look for date patterns in first few lines
        lines = table_text.split('\n')[:5]
        
        for line in lines:
            # Pattern: "March 31, 2025" or "Q1 2025"
            match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(\d{4})', line)
            if match:
                return match.group(0)
            
            match = re.search(r'Q[1-4]\s+(\d{4})', line)
            if match:
                return match.group(0)
        
        return None
    
    def _merge_multi_page_tables(self, chunks: List[TableChunk]) -> List[TableChunk]:
        """
        Detect and merge tables that span multiple pages.
        
        Heuristics:
        - Same or similar title on consecutive pages
        - Matching table type
        - "Continued" indicators
        
        Args:
            chunks: List of table chunks
        
        Returns:
            Merged chunks
        """
        if len(chunks) <= 1:
            return chunks
        
        merged = []
        skip_indices = set()
        
        for i, chunk in enumerate(chunks):
            if i in skip_indices:
                continue
            
            # Check if next chunk is continuation
            if i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                
                # Check for continuation
                if self._is_continuation(chunk, next_chunk):
                    # Merge chunks
                    merged_chunk = self._merge_chunks(chunk, next_chunk)
                    merged.append(merged_chunk)
                    skip_indices.add(i + 1)
                    continue
            
            merged.append(chunk)
        
        return merged
    
    def _is_continuation(self, chunk1: TableChunk, chunk2: TableChunk) -> bool:
        """Check if chunk2 is a continuation of chunk1."""
        # Same table type
        if chunk1.metadata.table_type != chunk2.metadata.table_type:
            return False
        
        # Consecutive pages
        if chunk2.metadata.page_no != chunk1.metadata.page_no + 1:
            return False
        
        # Similar titles or "continued" indicator
        title1 = chunk1.metadata.table_title.lower()
        title2 = chunk2.metadata.table_title.lower()
        
        if 'continued' in title2 or 'cont' in title2:
            return True
        
        # Very similar titles (edit distance)
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, title1, title2).ratio()
        
        return similarity > 0.8
    
    def _merge_chunks(self, chunk1: TableChunk, chunk2: TableChunk) -> TableChunk:
        """Merge two table chunks."""
        # Combine content
        merged_content = f"{chunk1.content}\n\n{chunk2.content}"
        
        # Update metadata
        merged_metadata = chunk1.metadata.copy()
        merged_metadata.table_title = f"{chunk1.metadata.table_title} (Pages {chunk1.metadata.page_no}-{chunk2.metadata.page_no})"
        
        return TableChunk(
            content=merged_content,
            metadata=merged_metadata,
            embedding=None
        )
    
    def store_to_vectordb(self, chunks: List[TableChunk]) -> int:
        """
        Store chunks to vector database.
        
        Args:
            chunks: List of table chunks
        
        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0
        
        console.print(f"\n[bold cyan]Storing {len(chunks)} chunks to vector DB...[/bold cyan]")
        
        self.vector_store.add_chunks(chunks, show_progress=True)
        
        console.print(f"[bold green]✓ Stored {len(chunks)} chunks[/bold green]")
        
        return len(chunks)


def extract_pdfs_batch(
    pdf_dir: str,
    vector_store=None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Extract multiple PDFs in batch.
    
    Args:
        pdf_dir: Directory containing PDFs
        vector_store: Optional vector store instance
        force: Force re-extraction even if already processed
    
    Returns:
        Batch processing results
    """
    pdf_path = Path(pdf_dir)
    pdf_files = list(pdf_path.glob("*.pdf"))
    
    if not pdf_files:
        console.print(f"[red]No PDF files found in {pdf_dir}[/red]")
        return {'processed': 0, 'failed': 0, 'results': []}
    
    console.print(f"\n[bold]Found {len(pdf_files)} PDF files to process[/bold]\n")
    
    results = []
    processed = 0
    failed = 0
    
    for pdf_file in pdf_files:
        try:
            console.print(f"\n{'='*70}")
            
            # Initialize extractor
            extractor = PageByPageExtractor(str(pdf_file), vector_store)
            
            # Extract document
            result = extractor.extract_document()
            
            # Store to vector DB
            stored = extractor.store_to_vectordb(result['chunks'])
            result['stored_chunks'] = stored
            
            results.append(result)
            processed += 1
            
        except Exception as e:
            console.print(f"[red]✗ Error processing {pdf_file.name}: {e}[/red]")
            failed += 1
    
    # Summary
    console.print(f"\n{'='*70}")
    console.print(f"[bold]Batch Processing Summary:[/bold]")
    console.print(f"  Processed: {processed}/{len(pdf_files)}")
    console.print(f"  Failed: {failed}/{len(pdf_files)}")
    
    total_chunks = sum(r['total_chunks'] for r in results)
    console.print(f"  Total chunks: {total_chunks}")
    console.print(f"{'='*70}\n")
    
    return {
        'processed': processed,
        'failed': failed,
        'total_chunks': total_chunks,
        'results': results
    }


if __name__ == "__main__":
    import sys
    
    # Example usage
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        extractor = PageByPageExtractor(pdf_path)
        result = extractor.extract_document()
        extractor.store_to_vectordb(result['chunks'])
    else:
        # Batch process all PDFs in raw_data
        extract_pdfs_batch("../raw_data")
