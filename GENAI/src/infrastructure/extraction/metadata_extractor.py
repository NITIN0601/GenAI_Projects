"""
Utility to extract rich table structure metadata for VectorDB storage.

Extracts:
- Column headers
- Row headers  
- Table dimensions
- Multi-level headers
- Hierarchical structure
- Subsections
- Currency information
"""

from typing import Dict, List, Any
from src.infrastructure.extraction.formatters.table_formatter import TableStructureFormatter
from src.infrastructure.extraction.formatters.enhanced_formatter import EnhancedTableFormatter


class MetadataExtractor:
    """Extract rich metadata from table content."""
    
    @staticmethod
    def extract_table_metadata(table_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a table.
        
        Args:
            table_dict: Table dictionary from extraction result
            
        Returns:
            Dictionary with all metadata fields
        """
        content = table_dict.get('content', '')
        base_metadata = table_dict.get('metadata', {})
        
        # Parse table structure
        parsed = TableStructureFormatter.parse_markdown_table(content)
        
        # Detect multi-level headers
        lines = content.split('\n')
        header_info = EnhancedTableFormatter.detect_multi_level_headers(lines)
        
        # Detect subsections
        subsections = EnhancedTableFormatter.detect_subsections(lines)
        
        # Detect row hierarchy
        hierarchical_rows = TableStructureFormatter.detect_row_hierarchy(parsed['rows'])
        
        # Extract row headers (first column)
        row_headers = [row[0] if row else '' for row in parsed['rows']]
        row_headers = [h for h in row_headers if h]  # Remove empty
        
        # Currency analysis
        has_currency = '$' in content
        currency_count = content.count('$')
        
        # Build enhanced metadata
        enhanced_metadata = {
            # Base metadata
            **base_metadata,
            
            # Table Structure
            'column_headers': parsed['columns'],
            'row_headers': row_headers[:50],  # Limit to first 50
            'column_count': parsed['column_count'],
            'row_count': parsed['row_count'],
            
            # Multi-level Headers
            'has_multi_level_headers': header_info['has_multi_level'],
            'main_header': header_info['main_header'],
            'sub_headers': header_info['sub_headers'],
            
            # Hierarchical Structure
            'has_hierarchy': any(row['level'] > 0 for row in hierarchical_rows),
            'subsections': [s['text'] for s in subsections],
            
            # Content Analysis
            'has_currency': has_currency,
            'currency_count': currency_count,
            
            # Text for embedding
            'embedding_text': MetadataExtractor._create_embedding_text(
                table_dict, parsed, header_info
            )
        }
        
        return enhanced_metadata
    
    @staticmethod
    def _create_embedding_text(
        table_dict: Dict[str, Any],
        parsed: Dict[str, Any],
        header_info: Dict[str, Any]
    ) -> str:
        """
        Create optimized text for embedding generation.
        
        Includes:
        - Table title
        - Headers (multi-level if present)
        - First few rows of data
        - Metadata context
        """
        metadata = table_dict.get('metadata', {})
        content = table_dict.get('content', '')
        
        # Build embedding text
        text_parts = []
        
        # Title and context
        text_parts.append(f"Table: {metadata.get('table_title', 'Unknown')}")
        text_parts.append(f"Source: {metadata.get('source_doc', 'Unknown')}, Page {metadata.get('page_no', 'N/A')}")
        text_parts.append(f"Period: {metadata.get('year', 'N/A')} {metadata.get('quarter', '')}")
        
        # Headers
        if header_info['has_multi_level']:
            text_parts.append(f"Main Header: {header_info['main_header']}")
            text_parts.append(f"Columns: {', '.join(header_info['sub_headers'])}")
        else:
            text_parts.append(f"Columns: {', '.join(parsed['columns'])}")
        
        # Sample data (first 5 rows)
        text_parts.append("\nData:")
        lines = content.split('\n')
        data_lines = [l for l in lines if '|' in l and not l.strip().startswith('|---')]
        for line in data_lines[:5]:
            text_parts.append(line)
        
        return '\n'.join(text_parts)
    
    @staticmethod
    def create_vectordb_metadata(enhanced_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create metadata suitable for VectorDB storage.
        
        ChromaDB has limitations on metadata types, so we need to:
        - Convert lists to strings
        - Ensure all values are JSON-serializable
        - Keep only essential fields
        """
        vectordb_metadata = {
            # Document info
            'source_doc': enhanced_metadata.get('source_doc', ''),
            'page_no': enhanced_metadata.get('page_no', 0),
            'table_title': enhanced_metadata.get('table_title', ''),
            
            # Temporal
            'year': enhanced_metadata.get('year', 0),
            'quarter': enhanced_metadata.get('quarter', ''),
            'report_type': enhanced_metadata.get('report_type', ''),
            
            # Structure (as strings for ChromaDB)
            'column_headers': '|'.join(enhanced_metadata.get('column_headers', [])),
            'row_headers': '|'.join(enhanced_metadata.get('row_headers', [])[:10]),  # First 10
            'column_count': enhanced_metadata.get('column_count', 0),
            'row_count': enhanced_metadata.get('row_count', 0),
            
            # Flags (booleans work in ChromaDB)
            'has_multi_level_headers': enhanced_metadata.get('has_multi_level_headers', False),
            'has_hierarchy': enhanced_metadata.get('has_hierarchy', False),
            'has_currency': enhanced_metadata.get('has_currency', False),
            
            # Multi-level headers
            'main_header': enhanced_metadata.get('main_header', ''),
            'sub_headers': '|'.join(enhanced_metadata.get('sub_headers', [])),
            
            # Subsections
            'subsections': '|'.join(enhanced_metadata.get('subsections', [])),
            
            # Content analysis
            'currency_count': enhanced_metadata.get('currency_count', 0),
        }
        
        # Remove empty strings and None values
        vectordb_metadata = {
            k: v for k, v in vectordb_metadata.items()
            if v not in ['', None, []]
        }
        
        return vectordb_metadata


def extract_and_prepare_for_vectordb(extraction_result) -> List[Dict[str, Any]]:
    """
    Extract all tables with enhanced metadata ready for VectorDB.
    
    Args:
        extraction_result: ExtractionResult from unified extractor
        
    Returns:
        List of dictionaries with content and enhanced metadata
    """
    prepared_tables = []
    
    for table in extraction_result.tables:
        # Extract enhanced metadata
        enhanced_metadata = MetadataExtractor.extract_table_metadata(table)
        
        # Create VectorDB-compatible metadata
        vectordb_metadata = MetadataExtractor.create_vectordb_metadata(enhanced_metadata)
        
        prepared_tables.append({
            'content': table['content'],
            'embedding_text': enhanced_metadata['embedding_text'],
            'metadata': vectordb_metadata,
            'full_metadata': enhanced_metadata  # Keep full metadata for reference
        })
    
    return prepared_tables
