"""
Unified Metadata Extractor - Enhanced metadata extraction (21+ fields).

Extracts comprehensive metadata from table content:
- Company information (ticker, name)
- Financial context (statement type, filing type, fiscal period)
- Table-specific (units, currency, consolidation status)
- Hierarchical info (sections, footnotes, related tables)
- Data quality markers
- Chunk management
"""

from typing import Dict, Any, Optional, List
import re
from datetime import datetime
from pathlib import Path

# Circular import fix: These are imported locally where needed
# from extraction.table_formatter import TableStructureFormatter
# from extraction.enhanced_formatter import EnhancedTableFormatter


def _get_table_formatter():
    """Lazy import to avoid circular dependency."""
    from extraction.table_formatter import TableStructureFormatter
    return TableStructureFormatter


def _get_enhanced_formatter():
    """Lazy import to avoid circular dependency."""
    from extraction.enhanced_formatter import EnhancedTableFormatter
    return EnhancedTableFormatter


class UnifiedMetadataExtractor:
    """
    Unified metadata extractor for all backends.
    
    Extracts 21+ enhanced metadata fields from tables.
    """
    
    @staticmethod
    def extract_complete_metadata(
        table_dict: Dict[str, Any],
        pdf_metadata: Optional[Dict[str, Any]] = None,
        extraction_backend: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Extract ALL enhanced metadata fields.
        
        Args:
            table_dict: Table dictionary from extraction
            pdf_metadata: PDF-level metadata (filename, year, etc.)
            extraction_backend: Backend used (docling, pymupdf, etc.)
            
        Returns:
            Complete enhanced metadata dictionary
        """
        content = table_dict.get('content', '')
        base_metadata = table_dict.get('metadata', {})
        pdf_metadata = pdf_metadata or {}
        
        # Parse table structure
        TableStructureFormatter = _get_table_formatter()
        parsed = TableStructureFormatter.parse_markdown_table(content)
        
        # Extract all metadata categories
        company_info = UnifiedMetadataExtractor._extract_company_info(pdf_metadata)
        statement_context = UnifiedMetadataExtractor._extract_statement_context(
            table_dict, pdf_metadata
        )
        table_specific = UnifiedMetadataExtractor._extract_table_specific(
            content, base_metadata
        )
        hierarchical = UnifiedMetadataExtractor._extract_hierarchical_info(
            content, parsed
        )
        structure_info = UnifiedMetadataExtractor._extract_structure_info(
            content, parsed
        )
        quality_markers = UnifiedMetadataExtractor._extract_quality_markers(
            content, parsed
        )
        chunk_management = UnifiedMetadataExtractor._extract_chunk_management(
            table_dict, parsed
        )
        
        # Combine all metadata
        complete_metadata = {
            # Document Information
            'source_doc': pdf_metadata.get('filename', base_metadata.get('source_doc', '')),
            'page_no': base_metadata.get('page_no', 0),
            
            # Company Information
            **company_info,
            
            # Financial Statement Context
            **statement_context,
            
            # Table Identification
            'table_title': base_metadata.get('table_title', ''),
            'table_index': base_metadata.get('table_index'),
            
            # Temporal Information
            'year': pdf_metadata.get('year', base_metadata.get('year', 0)),
            'quarter': pdf_metadata.get('quarter', base_metadata.get('quarter')),
            'fiscal_period': base_metadata.get('fiscal_period'),
            
            # Table-Specific Metadata
            **table_specific,
            
            # Table Structure
            **structure_info,
            
            # Hierarchical Information
            **hierarchical,
            
            # Data Quality Markers
            **quality_markers,
            
            # Extraction Metadata
            'extraction_date': datetime.utcnow().isoformat(),
            'extraction_backend': extraction_backend,
            'quality_score': base_metadata.get('quality_score'),
            
            # Chunk Management
            **chunk_management
        }
        
        # Remove None values
        complete_metadata = {
            k: v for k, v in complete_metadata.items()
            if v is not None
        }
        
        return complete_metadata
    
    @staticmethod
    def _extract_company_info(pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract company ticker and name from PDF metadata or filename."""
        company_info = {}
        
        # Try to extract from metadata
        if 'company_ticker' in pdf_metadata:
            company_info['company_ticker'] = pdf_metadata['company_ticker']
        
        if 'company_name' in pdf_metadata:
            company_info['company_name'] = pdf_metadata['company_name']
        
        # Try to extract from filename
        filename = pdf_metadata.get('filename', '')
        
        # Common ticker patterns in filenames
        ticker_patterns = [
            r'([A-Z]{2,5})[-_]',  # AAPL-10Q
            r'[-_]([A-Z]{2,5})[-_]',  # report-AAPL-2024
        ]
        
        for pattern in ticker_patterns:
            match = re.search(pattern, filename)
            if match and 'company_ticker' not in company_info:
                company_info['company_ticker'] = match.group(1)
                break
        
        return company_info
    
    @staticmethod
    def _extract_statement_context(
        table_dict: Dict[str, Any],
        pdf_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract financial statement context."""
        context = {}
        
        table_title = table_dict.get('metadata', {}).get('table_title', '').lower()
        
        # Classify statement type
        if 'balance sheet' in table_title or 'balance' in table_title:
            context['statement_type'] = 'balance_sheet'
        elif 'income' in table_title or 'earnings' in table_title or 'operations' in table_title:
            context['statement_type'] = 'income_statement'
        elif 'cash flow' in table_title:
            context['statement_type'] = 'cash_flow'
        elif 'note' in table_title or 'footnote' in table_title:
            context['statement_type'] = 'footnotes'
        
        # Filing type from filename or metadata
        filename = pdf_metadata.get('filename', '').lower()
        if '10-q' in filename or '10q' in filename:
            context['filing_type'] = '10-Q'
        elif '10-k' in filename or '10k' in filename:
            context['filing_type'] = '10-K'
        elif '8-k' in filename or '8k' in filename:
            context['filing_type'] = '8-K'
        else:
            context['filing_type'] = pdf_metadata.get('filing_type', '')
        
        # Fiscal period end (try to extract from headers or metadata)
        fiscal_period_end = UnifiedMetadataExtractor._extract_fiscal_period_end(
            table_dict, pdf_metadata
        )
        if fiscal_period_end:
            context['fiscal_period_end'] = fiscal_period_end
        
        # Restatement flag (check title for keywords)
        if 'restat' in table_title or 'revised' in table_title:
            context['restatement'] = True
        else:
            context['restatement'] = False
        
        return context
    
    @staticmethod
    def _extract_fiscal_period_end(
        table_dict: Dict[str, Any],
        pdf_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """Extract fiscal period end date in ISO format."""
        # Try from metadata
        if 'fiscal_period_end' in pdf_metadata:
            return pdf_metadata['fiscal_period_end']
        
        # Try to construct from year and quarter
        year = pdf_metadata.get('year')
        quarter = pdf_metadata.get('quarter', '').upper()
        
        if year and quarter:
            quarter_end_dates = {
                'Q1': f"{year}-03-31",
                'Q2': f"{year}-06-30",
                'Q3': f"{year}-09-30",
                'Q4': f"{year}-12-31"
            }
            return quarter_end_dates.get(quarter)
        
        # Try to parse from table headers
        content = table_dict.get('content', '')
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',  # 2025-06-30
            r'(\w+)\s+(\d{1,2}),\s+(\d{4})',  # June 30, 2025
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, content)
            if match:
                # Return first match (could be improved)
                if '-' in match.group(0):
                    return match.group(0)
        
        return None
    
    @staticmethod
    def _extract_table_specific(
        content: str,
        base_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract table-specific metadata."""
        specific = {}
        
        # Table type
        title = base_metadata.get('table_title', '').lower()
        if 'summary' in title:
            specific['table_type'] = 'summary'
        elif 'detail' in title or 'detailed' in title:
            specific['table_type'] = 'detail'
        elif 'reconciliation' in title:
            specific['table_type'] = 'reconciliation'
        elif 'segment' in title:
            specific['table_type'] = 'segment'
        
        # Units (critical for financial data!)
        units_patterns = [
            (r'in\s+thousands', 'thousands'),
            (r'in\s+millions', 'millions'),
            (r'in\s+billions', 'billions'),
            (r'\(in\s+thousands\)', 'thousands'),
            (r'\(in\s+millions\)', 'millions'),
            (r'\(in\s+billions\)', 'billions'),
        ]
        
        content_lower = content.lower()
        for pattern, unit in units_patterns:
            if re.search(pattern, content_lower):
                specific['units'] = unit
                break
        
        # Currency
        if '$' in content:
            specific['currency'] = 'USD'
        elif '€' in content or 'EUR' in content:
            specific['currency'] = 'EUR'
        elif '£' in content or 'GBP' in content:
            specific['currency'] = 'GBP'
        
        # Consolidated flag
        if 'consolidated' in title:
            specific['is_consolidated'] = True
        else:
            specific['is_consolidated'] = False
        
        # Comparative periods (extract from headers)
        comparative_periods = UnifiedMetadataExtractor._extract_comparative_periods(content)
        if comparative_periods:
            specific['comparative_periods'] = comparative_periods
        
        return specific
    
    @staticmethod
    def _extract_comparative_periods(content: str) -> List[str]:
        """Extract comparative periods from table headers."""
        periods = []
        
        # Look for year patterns in first few lines
        lines = content.split('\n')[:5]
        
        for line in lines:
            # Find years (4 digits)
            years = re.findall(r'\b(20\d{2})\b', line)
            for year in years:
                # Try to find quarter
                quarter_match = re.search(rf'Q([1-4]).*{year}', line, re.IGNORECASE)
                if quarter_match:
                    periods.append(f"{year}-Q{quarter_match.group(1)}")
                else:
                    # Assume year-end if no quarter
                    periods.append(f"{year}-Q4")
        
        return list(set(periods))  # Remove duplicates
    
    @staticmethod
    def _extract_hierarchical_info(
        content: str,
        parsed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract hierarchical information."""
        hierarchical = {}
        
        # Parent section (from title)
        title = parsed.get('title', '').lower()
        
        section_keywords = {
            'assets': 'Assets',
            'liabilities': 'Liabilities',
            'equity': 'Shareholders\' Equity',
            'revenue': 'Revenue',
            'expenses': 'Expenses',
            'income': 'Income',
            'cash': 'Cash Flows'
        }
        
        for keyword, section in section_keywords.items():
            if keyword in title:
                hierarchical['parent_section'] = section
                break
        
        # Subsection
        if 'current' in title:
            hierarchical['subsection'] = 'Current'
        elif 'non-current' in title or 'noncurrent' in title:
            hierarchical['subsection'] = 'Non-Current'
        elif 'long-term' in title:
            hierarchical['subsection'] = 'Long-Term'
        
        # Footnote references
        footnote_refs = re.findall(r'\((\d+)\)', content)
        if footnote_refs:
            hierarchical['footnote_references'] = list(set(footnote_refs))[:10]  # First 10 unique
        
        # Related tables (placeholder - would need document-level context)
        hierarchical['related_tables'] = []
        
        return hierarchical
    
    @staticmethod
    def _extract_structure_info(
        content: str,
        parsed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract table structure information."""
        lines = content.split('\n')
        
        # Multi-level headers
        EnhancedTableFormatter = _get_enhanced_formatter()
        header_info = EnhancedTableFormatter.detect_multi_level_headers(lines)
        
        # Subsections
        subsections = EnhancedTableFormatter.detect_subsections(lines)
        
        # Row hierarchy
        TableStructureFormatter = _get_table_formatter()
        hierarchical_rows = TableStructureFormatter.detect_row_hierarchy(parsed['rows'])
        
        # Row headers (first column)
        row_headers = [row[0] if row else '' for row in parsed['rows']]
        row_headers = [h for h in row_headers if h]
        
        structure = {
            'column_headers': parsed['columns'],
            'row_headers': row_headers[:50],  # First 50
            'column_count': parsed['column_count'],
            'row_count': parsed['row_count'],
            
            # Multi-level headers
            'has_multi_level_headers': header_info['has_multi_level'],
            'main_header': header_info['main_header'],
            'sub_headers': header_info['sub_headers'],
            
            # Hierarchical structure
            'has_hierarchy': any(row['level'] > 0 for row in hierarchical_rows),
            'subsections': [s['text'] for s in subsections],
            
            # Table structure complexity
            'table_structure': UnifiedMetadataExtractor._classify_table_structure(
                header_info, hierarchical_rows
            )
        }
        
        return structure
    
    @staticmethod
    def _classify_table_structure(
        header_info: Dict[str, Any],
        hierarchical_rows: List[Dict[str, Any]]
    ) -> str:
        """Classify table structure complexity."""
        if header_info['has_multi_level']:
            return 'multi_header'
        elif any(row['level'] > 0 for row in hierarchical_rows):
            return 'nested'
        else:
            return 'simple'
    
    @staticmethod
    def _extract_quality_markers(
        content: str,
        parsed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract data quality markers."""
        quality = {}
        
        # Currency analysis
        quality['has_currency'] = '$' in content or '€' in content or '£' in content
        quality['currency_count'] = content.count('$') + content.count('€') + content.count('£')
        
        # Subtotals detection
        subtotal_keywords = ['subtotal', 'sub-total', 'total', 'sum']
        has_subtotals = any(
            any(keyword in str(cell).lower() for keyword in subtotal_keywords)
            for row in parsed['rows']
            for cell in row
        )
        quality['has_subtotals'] = has_subtotals
        
        # Calculations detection (look for formulas or computed values)
        calculation_indicators = ['calculated', 'computed', 'derived', '=']
        has_calculations = any(indicator in content.lower() for indicator in calculation_indicators)
        quality['has_calculations'] = has_calculations
        
        # Extraction confidence (placeholder - would come from backend)
        quality['extraction_confidence'] = 0.95  # Default high confidence
        
        return quality
    
    @staticmethod
    def _extract_chunk_management(
        table_dict: Dict[str, Any],
        parsed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract chunk management information."""
        chunk_mgmt = {}
        
        # Determine chunk type
        row_count = parsed['row_count']
        if row_count <= 10:
            chunk_mgmt['chunk_type'] = 'complete'
        else:
            chunk_mgmt['chunk_type'] = 'data'  # Would be split into chunks
        
        # Overlapping context (placeholder)
        chunk_mgmt['overlapping_context'] = None
        
        # Multi-page tables
        page_no = table_dict.get('metadata', {}).get('page_no')
        if page_no:
            chunk_mgmt['table_start_page'] = page_no
            chunk_mgmt['table_end_page'] = page_no  # Same page unless split
        
        return chunk_mgmt


def extract_enhanced_metadata_unified(
    extraction_result,
    pdf_metadata: Optional[Dict[str, Any]] = None,
    extraction_backend: str = "unknown"
) -> List[Dict[str, Any]]:
    """
    Extract enhanced metadata for all tables (unified across backends).
    
    Args:
        extraction_result: ExtractionResult from any backend
        pdf_metadata: PDF-level metadata
        extraction_backend: Backend name
        
    Returns:
        List of tables with complete enhanced metadata
    """
    enhanced_tables = []
    
    for table in extraction_result.tables:
        # Extract complete metadata
        complete_metadata = UnifiedMetadataExtractor.extract_complete_metadata(
            table_dict=table,
            pdf_metadata=pdf_metadata,
            extraction_backend=extraction_backend
        )
        
        enhanced_tables.append({
            'content': table['content'],
            'metadata': complete_metadata,
            'embedding_text': UnifiedMetadataExtractor._create_embedding_text(
                table, complete_metadata
            )
        })
    
    return enhanced_tables


def _create_embedding_text(
    table_dict: Dict[str, Any],
    metadata: Dict[str, Any]
) -> str:
    """Create optimized text for embedding."""
    text_parts = []
    
    # Title and context
    text_parts.append(f"Table: {metadata.get('table_title', 'Unknown')}")
    
    if metadata.get('company_name'):
        text_parts.append(f"Company: {metadata['company_name']}")
    
    text_parts.append(f"Source: {metadata.get('source_doc', 'Unknown')}, Page {metadata.get('page_no', 'N/A')}")
    text_parts.append(f"Period: {metadata.get('fiscal_period_end', metadata.get('year', 'N/A'))}")
    
    if metadata.get('units'):
        text_parts.append(f"Units: {metadata['units']}")
    
    # Headers
    if metadata.get('has_multi_level_headers'):
        text_parts.append(f"Main Header: {metadata.get('main_header')}")
    
    column_headers = metadata.get('column_headers', [])
    if column_headers:
        text_parts.append(f"Columns: {', '.join(column_headers[:5])}")
    
    # Sample data
    content = table_dict.get('content', '')
    lines = content.split('\n')
    data_lines = [l for l in lines if '|' in l and not l.strip().startswith('|---')]
    
    if data_lines:
        text_parts.append("\nData:")
        for line in data_lines[:5]:
            text_parts.append(line)
    
    return '\n'.join(text_parts)
