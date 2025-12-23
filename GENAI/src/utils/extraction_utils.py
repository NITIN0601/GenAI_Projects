"""
Common utilities for PDF extraction and processing.

Consolidates duplicate code from multiple extraction modules.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import re

import os

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from src.domain.tables import TableMetadata


# =============================================================================
# MODULE-LEVEL COMPILED REGEX PATTERNS (Optimization)
# =============================================================================
# These patterns are compiled once at module import time instead of being
# compiled repeatedly inside functions for better performance.

# TOC extraction patterns
_TOC_ENTRY_PATTERN = re.compile(r'^(\d+\.\s+)?(.+?)\s+(\d{1,3})\s*$')
_NUMBERED_SECTION_PATTERN = re.compile(r'^(\d{1,2})\.\s+([A-Z][A-Za-z\s,\-]+)$')
_NUMBERED_PREFIX_PATTERN = re.compile(r'^\d+\.\s+')

# Title cleaning patterns
_SECTION_NUMBER_PREFIX = re.compile(r'^\d+[\.\:\s]+\s*')
_NOTE_PREFIX_PATTERN = re.compile(r'^Note\s+\d+\.?\s*[-–:]?\s*', re.IGNORECASE)
_TABLE_PREFIX_PATTERN = re.compile(r'^Table\s+\d+\.?\s*[-–:]?\s*', re.IGNORECASE)
_ROW_RANGE_PATTERN = re.compile(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', re.IGNORECASE)

# Footnote patterns
_TRAILING_NUMBER_PATTERN = re.compile(r'\s+\d+\s*$')
_PAREN_NUMBER_PATTERN = re.compile(r'\s*\(\d+\)\s*$')
_SUPERSCRIPT_PATTERN = re.compile(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+')

# Note header pattern for section detection
_NOTE_HEADER_PATTERN = re.compile(r'^Note\s+\d+', re.IGNORECASE)
_NUMBERED_HEADER_PATTERN = re.compile(r'^\d+\.\s+[A-Z]')


class DoclingHelper:
    """Helper class for common Docling operations."""
    
    # Default local model directory names relative to src/model/
    LOCAL_MODEL_DIRS = [
        'doclingPackages',  # Layout model (docling-layout-heron)
        'docling-models',   # Tableformer models
    ]
    
    @staticmethod
    def _find_local_models() -> tuple:
        """
        Find local docling model directories.
        
        Searches for model directories in:
        1. Environment variable DOCLING_ARTIFACTS_PATH
        2. src/model/doclingPackages/ (layout model)
        3. src/model/docling-models/ (tableformer models)
        
        Returns:
            Tuple of (artifacts_path, tableformer_path) or (None, None) if not found
        """
        # First check environment variable
        env_artifacts_path = os.environ.get('DOCLING_ARTIFACTS_PATH')
        if env_artifacts_path and Path(env_artifacts_path).exists():
            return env_artifacts_path, None
        
        # Try to find src/model directory relative to this file or project root
        current_file = Path(__file__).resolve()
        
        # Try multiple possible locations
        possible_roots = [
            current_file.parent.parent,  # src/utils -> src
            current_file.parent.parent.parent,  # src/utils -> project root
            Path.cwd(),  # Current working directory
        ]
        
        artifacts_path = None
        tableformer_path = None
        
        for root in possible_roots:
            # Check for src/model/doclingPackages (layout models)
            docling_packages = root / 'model' / 'doclingPackages'
            if docling_packages.exists() and (docling_packages / 'model.safetensors').exists():
                artifacts_path = str(docling_packages)
            
            # Also check root/src/model/doclingPackages
            docling_packages_alt = root / 'src' / 'model' / 'doclingPackages'
            if docling_packages_alt.exists() and (docling_packages_alt / 'model.safetensors').exists():
                artifacts_path = str(docling_packages_alt)
            
            # Check for src/model/docling-models (tableformer models)
            docling_models = root / 'model' / 'docling-models'
            if docling_models.exists() and (docling_models / 'model_artifacts').exists():
                tableformer_path = str(docling_models)
            
            # Also check root/src/model/docling-models
            docling_models_alt = root / 'src' / 'model' / 'docling-models'
            if docling_models_alt.exists() and (docling_models_alt / 'model_artifacts').exists():
                tableformer_path = str(docling_models_alt)
            
            if artifacts_path or tableformer_path:
                break
        
        return artifacts_path, tableformer_path
    
    @staticmethod
    def convert_pdf(pdf_path: str) -> Any:
        """
        Convert PDF using Docling.
        
        NOTE: The docling pip packages are installed normally via pip.
        This configuration controls the MODEL WEIGHTS that docling downloads
        at runtime from HuggingFace Hub (layout models, tableformer models, etc.)
        
        DEFAULT: Uses LOCAL model weights only (no runtime downloads from HuggingFace).
        
        Platform-specific OCR:
        - macOS: Uses OcrMac (Apple Vision framework, fast GPU-accelerated)
        - Windows/Linux: Uses RapidOCR with local ONNX models from src/model/
        
        Model weight loading priority:
        1. Environment variable DOCLING_ARTIFACTS_PATH (if set)
        2. Auto-detect local model weights in:
           - src/model/doclingPackages/ (layout model weights - docling-layout-heron)  
           - src/model/docling-models/ (tableformer model weights)
        3. Download from HuggingFace Hub ONLY if DOCLING_ALLOW_DOWNLOAD=1
        
        Environment variables:
        - DOCLING_ARTIFACTS_PATH: Path to local model weights directory
        - DOCLING_ALLOW_DOWNLOAD: Set to "1" or "true" to allow downloading
                                  model weights from internet (default: False)
        - DOCLING_OCR_ENGINE: Override OCR engine ("ocrmac", "rapidocr", "auto")
        - DOCLING_TABLE_MODE: TableFormer mode ("accurate", "fast") default: accurate
        - DOCLING_IMAGE_SCALE: Image resolution scale (1.0-4.0) default: 1.0
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Docling conversion result
            
        Raises:
            RuntimeError: If no local model weights found and downloads not allowed
        """
        import logging
        import platform
        logger = logging.getLogger(__name__)
        
        # Check if downloading model weights from internet is allowed (default: NO - local only)
        allow_download = os.environ.get('DOCLING_ALLOW_DOWNLOAD', '').lower() in ('1', 'true', 'yes')
        
        # Find local model weights (checks env var first, then auto-detects)
        artifacts_path, tableformer_path = DoclingHelper._find_local_models()
        
        # Log model weight source
        if artifacts_path:
            logger.info(f"Using local docling layout model weights from: {artifacts_path}")
        if tableformer_path:
            logger.info(f"Using local tableformer model weights from: {tableformer_path}")
        
        # If we have local model weights, use them (set offline mode to prevent any downloads)
        if artifacts_path:
            # Prevent any accidental model weight downloads when using local files
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import PdfFormatOption
            
            # Determine OCR engine based on platform
            ocr_override = os.environ.get('DOCLING_OCR_ENGINE', '').lower()
            system = platform.system()
            
            if ocr_override == 'rapidocr':
                use_rapidocr = True
            elif ocr_override == 'ocrmac':
                use_rapidocr = False
            else:
                # Auto-detect: macOS uses OcrMac, Windows/Linux use RapidOCR
                use_rapidocr = (system != 'Darwin')
            
            # Configure OCR options
            ocr_options = None
            if use_rapidocr:
                from docling.datamodel.pipeline_options import RapidOcrOptions
                
                # Build paths to local RapidOCR models
                rapidocr_base = Path(artifacts_path) / 'RapidOcr' / 'onnx' / 'PP-OCRv4'
                det_model = rapidocr_base / 'det' / 'ch_PP-OCRv4_det_infer.onnx'
                rec_model = rapidocr_base / 'rec' / 'ch_PP-OCRv4_rec_infer.onnx'
                cls_model = rapidocr_base / 'cls' / 'ch_ppocr_mobile_v2.0_cls_infer.onnx'
                
                # Check if models exist, fall back to package defaults if not
                if det_model.exists() and rec_model.exists():
                    ocr_options = RapidOcrOptions(
                        det_model_path=str(det_model),
                        rec_model_path=str(rec_model),
                        cls_model_path=str(cls_model) if cls_model.exists() else None,
                    )
                    logger.info(f"Using RapidOCR with local models from: {rapidocr_base}")
                else:
                    # Use default RapidOCR (models from pip package)
                    ocr_options = RapidOcrOptions()
                    logger.info("Using RapidOCR with default bundled models")
            else:
                from docling.datamodel.pipeline_options import OcrMacOptions
                ocr_options = OcrMacOptions()
                logger.info("Using OcrMac (macOS native OCR)")
            
            # Configure tableformer mode (accurate vs fast)
            table_mode = os.environ.get('DOCLING_TABLE_MODE', 'accurate').lower()
            
            # Configure image scale for better quality (higher = better but slower)
            try:
                image_scale = float(os.environ.get('DOCLING_IMAGE_SCALE', '1.0'))
                image_scale = max(1.0, min(4.0, image_scale))  # Clamp between 1.0 and 4.0
            except ValueError:
                image_scale = 1.0
            
            # Import TableFormerMode for table structure detection
            try:
                from docling.datamodel.pipeline_options import TableFormerMode, TableStructureOptions
                
                if table_mode == 'fast':
                    table_structure_options = TableStructureOptions(
                        mode=TableFormerMode.FAST,
                        do_cell_matching=True
                    )
                    logger.info("Using TableFormer FAST mode")
                else:
                    table_structure_options = TableStructureOptions(
                        mode=TableFormerMode.ACCURATE,
                        do_cell_matching=True
                    )
                    logger.info("Using TableFormer ACCURATE mode (higher quality)")
                
                pipeline_options = PdfPipelineOptions(
                    artifacts_path=artifacts_path,
                    ocr_options=ocr_options,
                    do_table_structure=True,
                    table_structure_options=table_structure_options,
                    images_scale=image_scale,
                )
            except ImportError:
                # Fallback for older docling versions without TableFormerMode
                logger.warning("TableFormerMode not available, using default table detection")
                pipeline_options = PdfPipelineOptions(
                    artifacts_path=artifacts_path,
                    ocr_options=ocr_options,
                )
            
            if image_scale > 1.0:
                logger.info(f"Using image scale: {image_scale}x")
            
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            return converter.convert(pdf_path)
        
        # No local model weights found - check if downloads are allowed
        if allow_download:
            logger.warning("No local model weights found, downloading from HuggingFace Hub (DOCLING_ALLOW_DOWNLOAD=1)")
            converter = DocumentConverter()
            return converter.convert(pdf_path)
        
        # Default: local only, no model weight downloads allowed
        error_msg = (
            "No local docling model weights found and internet downloads are disabled.\n"
            "Note: pip packages (docling, docling-core) are installed normally.\n"
            "This error is about the MODEL WEIGHTS that docling needs at runtime.\n"
            "Please either:\n"
            "  1. Add model weights to src/model/doclingPackages/ and src/model/docling-models/\n"
            "  2. Set DOCLING_ARTIFACTS_PATH environment variable to your model weights directory\n"
            "  3. Set DOCLING_ALLOW_DOWNLOAD=1 to enable downloading model weights from HuggingFace"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    @staticmethod
    def extract_toc_sections(doc) -> dict:
        """
        Extract Table of Contents (TOC) and build page-to-section mapping.
        
        Parses the TOC from the PDF document to create a reliable mapping of
        page numbers to section names (e.g., page 51 -> "5. Fair Value Option").
        
        Handles hierarchical TOC structure:
        - Level 0: Major sections (e.g., "Notes to Consolidated Financial Statements")
        - Level 1: Subsections (e.g., "5. Fair Value Option")
        
        Args:
            doc: Docling document
            
        Returns:
            Dict mapping page numbers to section names, e.g.:
            {44: "Notes to Consolidated Financial Statements",
             51: "5. Fair Value Option",
             52: "6. Derivative Instruments and Hedging Activities"}
        """
        toc_sections = {}
        
        # Known section title patterns (to distinguish from footnotes)
        VALID_SECTION_STARTERS = [
            'introduction', 'executive', 'business', 'institutional', 'wealth',
            'investment', 'supplemental', 'accounting', 'critical', 'liquidity',
            'balance', 'regulatory', 'quantitative', 'qualitative', 'market',
            'credit', 'country', 'report', 'consolidated', 'notes', 'financial',
            'controls', 'legal', 'risk', 'other', 'exhibits', 'signatures',
            'cash', 'fair', 'derivative', 'securities', 'collateral', 'loans',
            'deposits', 'borrowings', 'commitments', 'variable', 'total', 'equity',
            'interest', 'income', 'taxes', 'segment', 'geographic', 'revenue',
            'basis', 'presentation', 'policies', 'assets', 'liabilities',
        ]
        
        # Words that indicate a footnote (NOT a section)
        FOOTNOTE_INDICATORS = [
            'amounts', 'includes', 'based on', 'represents', 'related to',
            'percent', 'excludes', 'primarily', 'net of', 'see note',
            'does not', 'prior to', 'inclusive of', 'applicable',
        ]
        
        try:
            items_list = list(doc.iterate_items())
            in_toc = False
            toc_end_page = 5  # TOC usually on first few pages
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                text_lower = text.lower()
                
                # Get page of this item
                item_page = DoclingHelper.get_item_page(item)
                
                # Detect start of TOC
                if 'table of contents' in text_lower or 'contents' == text_lower:
                    in_toc = True
                    continue
                
                # Skip very short or very long text
                if len(text) < 5 or len(text) > 100:
                    continue
                
                # Pattern: "Section Name PageNumber" at end
                # Examples: "5. Fair Value Option 51", "Executive Summary 5", "Notes to Consolidated Financial Statements 44"
                toc_match = re.match(r'^(\d+\.\s+)?(.+?)\s+(\d{1,3})\s*$', text)
                
                if toc_match:
                    prefix = toc_match.group(1) or ''
                    section_name = (prefix + toc_match.group(2)).strip()
                    
                    try:
                        page_num = int(toc_match.group(3))
                    except ValueError:
                        continue
                    
                    # Validate: page number should be reasonable
                    if not (1 <= page_num <= 500):
                        continue
                    
                    # Check if this looks like a footnote (should be filtered out)
                    is_footnote = False
                    section_lower = section_name.lower()
                    
                    # Footnote check: starts with number + "." but followed by footnote indicator
                    if re.match(r'^\d+\.\s+', section_name):
                        after_number = re.sub(r'^\d+\.\s+', '', section_lower)
                        for indicator in FOOTNOTE_INDICATORS:
                            if after_number.startswith(indicator):
                                is_footnote = True
                                break
                    
                    # Also check if the section text itself starts with footnote indicator
                    for indicator in FOOTNOTE_INDICATORS:
                        if section_lower.startswith(indicator):
                            is_footnote = True
                            break
                    
                    if is_footnote:
                        continue
                    
                    # Validate: section should start with known section word OR be numbered
                    is_valid = False
                    
                    # Numbered sections like "5. Fair Value Option" are valid
                    if re.match(r'^\d+\.\s+', section_name):
                        is_valid = True
                    else:
                        # Check if first word is a known section starter
                        first_word = section_lower.split()[0] if section_lower.split() else ''
                        if any(first_word.startswith(starter) for starter in VALID_SECTION_STARTERS):
                            is_valid = True
                    
                    if is_valid and len(section_name) > 3:
                        toc_sections[page_num] = section_name
            
            # Also look for numbered section headers in the document body
            # (these appear as standalone headers like "5. Fair Value Option" on the page)
            numbered_section_pattern = re.compile(r'^(\d{1,2})\.\s+([A-Z][A-Za-z\s,\-]+)$')
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                
                # Only consider short titles (section headers are usually brief)
                if len(text) < 5 or len(text) > 60:
                    continue
                
                num_match = numbered_section_pattern.match(text)
                if num_match:
                    section_num = num_match.group(1)
                    section_title = num_match.group(2).strip()
                    full_section = f"{section_num}. {section_title}"
                    
                    # Get page number of this item
                    page = DoclingHelper.get_item_page(item)
                    
                    # Only add if not already in toc_sections AND not a footnote
                    section_lower = section_title.lower()
                    is_footnote = any(section_lower.startswith(ind) for ind in FOOTNOTE_INDICATORS)
                    
                    if page and not is_footnote and page not in toc_sections:
                        toc_sections[page] = full_section
            
            # Third pass: Look for SECTION_HEADER labeled items to capture business segments
            # like "Institutional Securities", "Wealth Management", etc.
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                # Check for SECTION_HEADER or TITLE label
                if not hasattr(item, 'label') or not item.label:
                    continue
                
                label_str = str(item.label).upper()
                if 'SECTION' not in label_str and 'TITLE' not in label_str:
                    continue
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                text_lower = text.lower()
                
                # Skip short or long text
                if len(text) < 5 or len(text) > 80:
                    continue
                
                # Skip table-like content
                if any(skip in text_lower for skip in ['$', '|', '---', 'total:', 'net ']):
                    continue
                
                # Skip footnote-like content
                is_footnote = any(text_lower.startswith(ind) for ind in FOOTNOTE_INDICATORS)
                if is_footnote:
                    continue
                
                # Must start with a valid section word OR be a known business segment
                first_word = text_lower.split()[0] if text_lower.split() else ''
                is_valid_section = any(first_word.startswith(starter) for starter in VALID_SECTION_STARTERS)
                
                # Known business segment names
                is_business_segment = any(seg in text_lower for seg in [
                    'institutional securities', 'wealth management', 'investment management',
                    'corporate', 'intersegment', 'business segments'
                ])
                
                if is_valid_section or is_business_segment:
                    page = DoclingHelper.get_item_page(item)
                    if page and page not in toc_sections:
                        # Clean up the section name
                        section_name = text
                        if section_name.isupper():
                            section_name = section_name.title()
                        toc_sections[page] = section_name
            
        except Exception:
            pass
        
        return toc_sections
    
    @staticmethod
    def get_section_for_page(toc_sections: dict, page_no: int) -> str:
        """
        Get section name for a given page number using TOC mapping.
        
        Finds the most specific section that contains the given page.
        
        Args:
            toc_sections: Dict from extract_toc_sections()
            page_no: Page number to look up
            
        Returns:
            Section name or empty string if not found
        """
        if not toc_sections:
            return ""
        
        # Find the section with the highest page number <= page_no
        # This gives us the section that starts at or before the table's page
        best_section = ""
        best_page = 0
        
        for sec_page, sec_name in toc_sections.items():
            if sec_page <= page_no and sec_page > best_page:
                best_page = sec_page
                best_section = sec_name
        
        return best_section
    
    @staticmethod
    def get_item_page(item) -> int:
        """
        Get page number for a Docling item.
        
        Args:
            item: Docling document item
            
        Returns:
            Page number (1-indexed)
        """
        if hasattr(item, 'prov') and item.prov:
            for p in item.prov:
                if hasattr(p, 'page_no'):
                    return p.page_no
        return 1
    
    @staticmethod
    def extract_tables(doc) -> list:
        """
        Extract all tables from Docling document.
        
        Args:
            doc: Docling document
            
        Returns:
            List of table items
        """
        tables = []
        for item_data in doc.iterate_items():
            # Handle both tuple and direct item formats
            if isinstance(item_data, tuple):
                item = item_data[0]
            else:
                item = item_data
            
            if hasattr(item, 'label') and item.label == DocItemLabel.TABLE:
                tables.append(item)
        
        return tables
    
    @staticmethod
    def find_preceding_spanning_header(doc, table_item, page_no: int) -> str:
        """
        Find preceding TEXT items that could be a missing spanning header for this table.
        
        This handles cases where Docling extracts the spanning header (e.g., "Three Months 
        Ended March 31, 2024") as a separate TEXT item instead of including it in the table.
        
        Dynamic detection using universal date/period patterns (no hardcoding):
        - Month names (January, February, etc.)
        - Year patterns (2020-2030)
        - Period indicators (ended, ending, as of, at)
        
        Args:
            doc: Docling document
            table_item: The table item to find header for
            page_no: Page number of the table
            
        Returns:
            Spanning header text if found, empty string otherwise
        """
        import re
        
        # Universal date/period patterns (not domain-specific)
        MONTH_NAMES = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        ]
        PERIOD_INDICATORS = ['ended', 'ending', 'as of', 'at ', 'for the', 'period']
        YEAR_PATTERN = re.compile(r'\b20[0-3]\d\b')  # Years 2000-2039
        
        def is_date_period_header(text: str) -> bool:
            """Check if text looks like a date/period header dynamically."""
            text_lower = text.lower().strip()
            
            # Too short or too long for a header
            if len(text_lower) < 10 or len(text_lower) > 100:
                return False
            
            # Must contain a year
            if not YEAR_PATTERN.search(text):
                return False
            
            # Must contain a month name OR period indicator
            has_month = any(month in text_lower for month in MONTH_NAMES)
            has_period = any(ind in text_lower for ind in PERIOD_INDICATORS)
            
            return has_month or has_period
        
        try:
            items_list = list(doc.iterate_items())
            preceding_headers = []
            found_table = False
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                # Stop when we reach the target table
                if item is table_item:
                    found_table = True
                    break
                
                # Get item's page
                item_page = DoclingHelper.get_item_page(item)
                
                # Only consider items on the same page or immediately before
                if item_page < page_no - 1 or item_page > page_no:
                    continue
                
                # Check for TEXT label
                if not hasattr(item, 'label'):
                    continue
                
                label_name = item.label.name if hasattr(item.label, 'name') else str(item.label)
                if label_name not in ['TEXT', 'CAPTION', 'TITLE']:
                    continue
                
                # Get text content
                text = getattr(item, 'text', '')
                if not text:
                    continue
                
                text = str(text).strip()
                
                # Check if this looks like a date/period header
                if is_date_period_header(text):
                    preceding_headers.append((item_page, text))
            
            # Return the closest matching header on the same page (or just before)
            if preceding_headers:
                # Prefer headers on the same page
                same_page = [h for h in preceding_headers if h[0] == page_no]
                if same_page:
                    return same_page[-1][1]  # Last one before the table
                # Fall back to previous page
                return preceding_headers[-1][1]
                
        except Exception:
            pass
        
        return ""
    
    @staticmethod
    def prepend_spanning_header(table_markdown: str, spanning_header: str, num_columns: int) -> str:
        """
        Prepend a spanning header row to table markdown.
        
        Args:
            table_markdown: Original table markdown
            spanning_header: The header text to prepend
            num_columns: Number of columns in the table
            
        Returns:
            Modified markdown with spanning header prepended
        """
        if not spanning_header or not table_markdown or num_columns < 1:
            return table_markdown
        
        # Create a header row where the spanning header repeats across all data columns
        # Column 0 is typically empty (row labels column)
        header_cells = [''] + [spanning_header] * (num_columns - 1)
        header_row = '| ' + ' | '.join(header_cells) + ' |'
        
        # Prepend to existing markdown
        return header_row + '\n' + table_markdown
    
    # Class-level cache for TOC sections (to avoid re-parsing for every table)
    _toc_cache = {}
    
    @staticmethod
    def extract_section_name(doc, table_item, page_no: int, toc_sections: dict = None) -> str:
        """
        Extract the section name (e.g., '5. Fair Value Option', 'Wealth Management')
        that contains this table.
        
        Uses multiple strategies in priority order:
        1. TOC-based lookup (most reliable) - uses page-to-section mapping from Table of Contents
        2. Pattern matching for SECTION_HEADER/TITLE labels matching business segments
        3. Numbered section pattern matching (e.g., "5. Fair Value Option")
        4. General section header matching
        
        Args:
            doc: Docling document
            table_item: The table item
            page_no: Page number
            toc_sections: Optional pre-parsed TOC dict (from extract_toc_sections)
            
        Returns:
            Section name or empty string if not found
        """
        # Strategy 1: TOC-based lookup (most reliable)
        if toc_sections is None:
            # Try to use cached TOC or parse it
            doc_id = id(doc)
            if doc_id not in DoclingHelper._toc_cache:
                DoclingHelper._toc_cache[doc_id] = DoclingHelper.extract_toc_sections(doc)
            toc_sections = DoclingHelper._toc_cache[doc_id]
        
        if toc_sections:
            section = DoclingHelper.get_section_for_page(toc_sections, page_no)
            if section:
                return section
        
        # Strategy 2+: Fall back to pattern matching
        # IMPORTANT: Only use actual BUSINESS SEGMENT names - NOT table titles!
        # These are the top-level sections that group tables in Morgan Stanley reports
        BUSINESS_SEGMENTS = [
            'institutional securities',
            'wealth management', 
            'investment management',
            'corporate',
            'intersegment eliminations',
            'inter-segment eliminations',
        ]
        
        # Additional section headers that are valid (but less specific)
        GENERAL_SECTION_HEADERS = [
            'management\'s discussion and analysis',
            'consolidated financial statements',
            'notes to consolidated financial statements',
            'risk disclosures',
            'financial data supplement',
        ]
        
        try:
            items_list = list(doc.iterate_items())
            section_candidates = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                # Check if this is our table - stop looking
                if item is table_item:
                    break
                
                # Get item's page number
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                # Only consider items on same or recent pages
                if item_page >= page_no - 2:
                    # Get text first
                    if not hasattr(item, 'text') or not item.text:
                        continue
                    
                    text = str(item.text).strip()
                    
                    # Skip if too short or too long
                    if not (3 < len(text) < 80):
                        continue
                    
                    text_lower = text.lower()
                    
                    # Skip table-like content
                    if any(skip in text_lower for skip in ['$', '|', '---', 'row', 'total:', 'net ']):
                        continue
                    
                    # Strategy 1: Check label using both enum comparison and string fallback
                    is_section_or_title = False
                    
                    if hasattr(item, 'label') and item.label:
                        # Direct enum comparison (preferred)
                        if item.label == DocItemLabel.SECTION_HEADER:
                            is_section_or_title = True
                        elif hasattr(DocItemLabel, 'TITLE') and item.label == DocItemLabel.TITLE:
                            is_section_or_title = True
                        else:
                            # Fallback: string comparison for edge cases
                            label_str = str(item.label).upper()
                            if 'SECTION' in label_str or 'TITLE' in label_str:
                                is_section_or_title = True
                    
                    # Strategy 2: Check if it matches known BUSINESS SEGMENTS (high priority)
                    # This is the most reliable way to detect sections
                    matches_business_segment = any(seg in text_lower for seg in BUSINESS_SEGMENTS)
                    
                    # Strategy 3: Check if it matches general section headers (lower priority)
                    matches_general_header = any(hdr in text_lower for hdr in GENERAL_SECTION_HEADERS)
                    
                    # Strategy 4: Check for "Note X" pattern which often precedes sections
                    is_note_header = bool(re.match(r'^Note\s+\d+', text, re.IGNORECASE))

                    # Strategy 5: Check for Numbered Section pattern (e.g., "5. Fair Value Option")
                    # Must start with digit + dot + space + generic text
                    is_numbered_header = bool(re.match(r'^\d+\.\s+[A-Z]', text))
                    
                    # Only accept if it matches a BUSINESS SEGMENT or is a known general header
                    # Do NOT accept random section_or_title labels - they often pick up table titles
                    if matches_business_segment:
                        # Business segment - save with high priority
                        section_candidates.append(('business', text))
                    elif is_numbered_header and len(text) < 60:
                        # Numbered section (likely what we want, e.g. "5. Fair Value Option")
                        section_candidates.append(('numbered', text))
                    elif is_note_header:
                        # Note header - save with medium priority  
                        section_candidates.append(('note', text))
                    elif matches_general_header and is_section_or_title:
                        # General header with section label - save with low priority
                        section_candidates.append(('general', text))
            
            # Return the best section header (prioritize business segments)
            if section_candidates:
                # Sort by priority: business > numbered > note > general
                priority_order = {'business': 0, 'numbered': 0, 'note': 1, 'general': 2}
                section_candidates.sort(key=lambda x: priority_order.get(x[0], 99))
                
                # Get the highest priority match that's closest to the table
                # Among same priority, prefer the last one (closest to table)
                best_priority = section_candidates[0][0]
                same_priority = [c for c in section_candidates if c[0] == best_priority]
                result = same_priority[-1][1]  # Last match of best priority
                
                # Clean up the section name
                # Remove "Note X" prefix ONLY if the result is NOT just "Note X" (keep "Note 5" if that's all there is)
                # But keep "5. Fair Value Option" intact (it doesn't start with Note)
                # If it starts with "Note 5. Title", user might want "5. Title" or "Note 5. Title".
                # Given user feedback "The actual section is '5. Fair Value Option'", we should try to preserve the number.
                
                # If it matches "Note X. Title", strip "Note " but keep "X. Title" ?
                # Or just strip "Note \d+." completely?
                # The user request suggests they want "5. Fair Value Option".
                # If the text was "Note 5. Fair Value Option", stripping "Note " leaves "5. Fair Value Option".
                
                # Improved regex: Replace "Note " at start if followed by digit
                result = re.sub(r'^Note\s+(?=\d)', '', result, flags=re.IGNORECASE).strip()
                
                # Validation: If result became empty or just a number, revert or handle
                if not result or result.isdigit() or re.match(r'^\d+\.?$', result):
                    # Fallback or keep original?
                    if len(same_priority[-1][1]) > len(result): 
                         result = same_priority[-1][1] # unexpected over-cleaning
                
                # Normalize capitalization if all caps
                if result.isupper():
                    result = result.title()
                return result
                
        except Exception:
            pass
        
        return ""
    
    @staticmethod
    def extract_table_title(doc, table_item, table_index: int, page_no: int) -> str:
        """
        Extract meaningful table title from surrounding context.
        
        Priority:
        1. Table caption if available
        2. Preceding text item (section header) on same page (filtering out dates/units)
        3. Fallback to page-based name
        
        Args:
            doc: Docling document
            table_item: The table item
            table_index: Index of table in document
            page_no: Page number
            
        Returns:
            Extracted table title
        """
        def clean_title(text: str) -> str:
            """Clean footnotes, row ranges, section numbers, and extra whitespace from title."""
            if not text:
                return ""
            
            # Remove leading section numbers like "17." or "17 " or "17:"
            text = re.sub(r'^\d+[\.\:\s]+\s*', '', text)
            
            # Remove "Note X" or "Note X." prefix 
            text = re.sub(r'^Note\s+\d+\.?\s*[-–:]?\s*', '', text, flags=re.IGNORECASE)
            
            # Remove "Table X" prefix
            text = re.sub(r'^Table\s+\d+\.?\s*[-–:]?\s*', '', text, flags=re.IGNORECASE)
            
            # Remove row ranges like "(Rows 1-10)" or "(Rows 8-17)"
            text = re.sub(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', '', text, flags=re.IGNORECASE)
            
            # Clean footnotes
            # Trailing number: "Text 2"
            text = re.sub(r'\s+\d+\s*$', '', text)
            # Parenthesized: "Text (1)"
            text = re.sub(r'\s*\(\d+\)\s*$', '', text)
            
            # Remove superscript characters
            text = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', text)
            
            return text.strip()[:100]

        def is_valid_title(text: str) -> bool:
            """Check if text is a valid title and not a date/period header or boilerplate."""
            text_lower = text.lower().strip()
            
            # Too short or too long
            if len(text) < 5 or len(text) > 120:
                return False
            
            # Starts with parenthesis (likely not a title)
            if text.startswith('('):
                return False
            
            # Starts with lowercase (likely continuation text)
            if text[0].islower():
                return False
            
            invalid_patterns = [
                # Date/period patterns
                'three months ended', 'six months ended', 'nine months ended', 'twelve months ended',
                'year ended', 'quarter ended', 'at march', 'at december', 'at june', 'at september',
                'as of december', 'as of march', 'as of june', 'as of september',
                # Unit patterns
                '$ in millions', '$ in billions', 'in millions', 'in billions',
                'unaudited', '(unaudited)',
                # Row patterns
                'rows 1-', 'rows 10-', 'rows 8-',
                # Boilerplate/address patterns
                'address of principal', 'executive offices', 'zip code',
                'included within', 'in the balance sheet', 'in the following table',
                'see note', 'see also', 'refer to',
                # Fragment patterns
                'the following', 'as follows', 'shown below', 'presented below',
                # SEC form boilerplate
                'indicate by check mark', 'issuer pursuant', 'registrant',
            ]
            
            for pattern in invalid_patterns:
                if pattern in text_lower:
                    return False
            
            # Must contain at least one letter
            if not any(c.isalpha() for c in text):
                return False
            
            return True

        # Try to get caption first
        if hasattr(table_item, 'caption') and table_item.caption:
            caption = str(table_item.caption).strip()
            if caption and len(caption) > 3 and is_valid_title(caption):
                return clean_title(caption)
        
        # Look for preceding text item that could be the table title
        try:
            items_list = list(doc.iterate_items())
            preceding_texts = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                # Check if this is our table
                if item is table_item:
                    break
                
                # Get page number
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                # Only consider items on same page or preceding page
                if item_page >= page_no - 1:
                    label = str(item.label) if hasattr(item, 'label') else ''
                    
                    # Look for section headers, titles, or text items
                    if 'SECTION' in label.upper() or 'TITLE' in label.upper() or 'TEXT' in label.upper():
                        if hasattr(item, 'text') and item.text:
                            text = str(item.text).strip()
                            # Filter out long paragraphs, keep short titles
                            if 5 < len(text) < 150 and not text.startswith('|'):
                                preceding_texts.append(text)
            
            # Iterate backwards to find first valid title
            if preceding_texts:
                for text in reversed(preceding_texts):
                    if is_valid_title(text):
                        title = text
                        # Clean up common prefixes
                        for prefix in ['Note ', 'NOTE ', 'Table ']:
                            if title.startswith(prefix):
                                title = title[len(prefix):].strip()
                                if title and title[0].isdigit():
                                    # Skip the number
                                    parts = title.split(' ', 1)
                                    if len(parts) > 1:
                                        title = parts[1].strip()
                        
                        if title and len(title) > 3:
                            return clean_title(title)
        except Exception:
            pass
        
        # Fallback: Table with page reference
        return f"Table {table_index + 1} (Page {page_no})"


class FootnoteExtractor:
    """
    Extract and clean footnote references from table content.
    
    Handles patterns like:
    - "Loans and other receivables 2" -> ("Loans and other receivables", ["2"])
    - "Total assets (1)(2)" -> ("Total assets", ["1", "2"])
    - "Net income¹²" -> ("Net income", ["1", "2"])
    """
    
    # Patterns for footnote references
    FOOTNOTE_PATTERNS = [
        r'\s+(\d+)\s*$',           # Trailing number: "Text 2"
        r'\s*\((\d+)\)\s*$',       # Parenthesized: "Text (1)"
        r'\s*\[(\d+)\]\s*$',       # Bracketed: "Text [1]"
        r'(\s+\d+)+\s*$',          # Multiple trailing numbers: "Text 1 2 3"
        r'\s*(\(\d+\))+\s*$',      # Multiple parenthesized: "Text (1)(2)"
    ]
    
    # Superscript digits
    SUPERSCRIPT_MAP = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    @classmethod
    def extract_footnotes(cls, text: str) -> tuple:
        """
        Extract footnote references from text.
        
        Args:
            text: Original text with potential footnote refs
            
        Returns:
            Tuple of (cleaned_text, list_of_footnote_refs)
        """
        if not text or not isinstance(text, str):
            return text, []
        
        footnotes = []
        cleaned = text.strip()
        
        # Handle superscript characters first
        for sup, digit in cls.SUPERSCRIPT_MAP.items():
            if sup in cleaned:
                footnotes.append(digit)
                cleaned = cleaned.replace(sup, '')
        
        # Handle attached comma-separated footnotes like "ROTCE2,3" or "ROTCE2, 3"
        # Pattern: letter followed by digit(s) with optional commas, at end of string
        attached_comma_match = re.search(r'([a-zA-Z])(\d+(?:,\s*\d+)*),?\s*$', cleaned)
        if attached_comma_match:
            # Get the footnote numbers
            fn_part = attached_comma_match.group(2)
            fn_nums = re.findall(r'\d+', fn_part)
            if fn_nums:
                footnotes.extend(fn_nums)
                # Remove the footnotes but keep the last letter
                cleaned = cleaned[:attached_comma_match.start()] + attached_comma_match.group(1)
        
        # Handle trailing comma-separated footnotes with space: "Text 2,3" or "Text 2, 3"
        trailing_comma_match = re.search(r'\s+(\d+(?:,\s*\d+)+),?\s*$', cleaned)
        if trailing_comma_match:
            fn_part = trailing_comma_match.group(1)
            fn_nums = re.findall(r'\d+', fn_part)
            if fn_nums:
                footnotes.extend(fn_nums)
                cleaned = cleaned[:trailing_comma_match.start()].strip()
        
        # Extract trailing single/multiple numbers like "Text 2" or "Text 2 3"
        trailing_match = re.search(r'\s+(\d(?:\s+\d)*)\s*$', cleaned)
        if trailing_match:
            nums = trailing_match.group(1).split()
            footnotes.extend(nums)
            cleaned = cleaned[:trailing_match.start()].strip()
        
        # Extract parenthesized numbers like "(1)" or "(1)(2)"
        paren_matches = re.findall(r'\((\d+)\)', cleaned)
        if paren_matches:
            footnotes.extend(paren_matches)
            cleaned = re.sub(r'\s*\(\d+\)', '', cleaned).strip()
        
        # Deduplicate while preserving order
        seen = set()
        unique_footnotes = []
        for fn in footnotes:
            if fn not in seen:
                seen.add(fn)
                unique_footnotes.append(fn)
        
        return cleaned, unique_footnotes
    
    @classmethod
    def clean_table_content(cls, table_text: str) -> tuple:
        """
        Clean entire table content, extracting footnotes from row labels.
        
        Args:
            table_text: Full table text in markdown format
            
        Returns:
            Tuple of (cleaned_table_text, dict of {row_label: footnotes})
        """
        if not table_text:
            return table_text, {}
        
        lines = table_text.split('\n')
        cleaned_lines = []
        all_footnotes = {}
        
        for line in lines:
            if '|' not in line or '---' in line:
                # Keep header separators and non-table lines as-is
                cleaned_lines.append(line)
                continue
            
            # Split into cells
            cells = line.split('|')
            cleaned_cells = []
            
            for i, cell in enumerate(cells):
                if i == 1:  # First data column (row label)
                    cleaned_cell, footnotes = cls.extract_footnotes(cell)
                    if footnotes:
                        all_footnotes[cleaned_cell.strip()] = footnotes
                    cleaned_cells.append(cleaned_cell)
                else:
                    cleaned_cells.append(cell)
            
            cleaned_lines.append('|'.join(cleaned_cells))
        
        return '\n'.join(cleaned_lines), all_footnotes


class CurrencyValueCleaner:
    """
    Clean and merge currency values that are incorrectly split across columns.
    
    Problem Pattern:
        PDF extraction often splits financial values across columns:
        - "$10,207 $" + ",762" (split mid-value)
        - "$ 10" + ",207 $" (leading $ in wrong column)
        
    Solution:
        Detect $ symbols and merge values appropriately:
        - "$10,207 $ 2,762" -> ["$10,207", "$2,762"]
        - "$ 10,207" -> ["$10,207"]
    """
    
    # Pattern to detect currency values
    CURRENCY_PATTERN = re.compile(
        r'^\s*\$?\s*[\d,]+(?:\.\d+)?\s*$'  # Matches: $10,207 or 10,207 or $10.5
    )
    
    # Pattern to detect cell containing only partial currency (ends with $ or starts with comma)
    PARTIAL_CURRENCY_END = re.compile(r'.*\$\s*$')  # Ends with "$" 
    PARTIAL_CURRENCY_START = re.compile(r'^\s*,?\d+')  # Starts with comma/digit (continuation)
    
    @classmethod
    def clean_currency_cells(cls, cells: list) -> list:
        """
        Clean a row of cells, merging incorrectly split currency values.
        
        The key insight: If a cell ends with '$' and the next cell starts with digits,
        they should be merged OR interpreted as separate column values.
        
        Pattern: "$10,207 $ 2,762" in a single cell means:
                 Value1: $10,207 (2024)
                 Value2: $2,762 (2023)
        
        Args:
            cells: List of cell values from a table row
            
        Returns:
            List of cleaned cell values with proper column separation
        """
        if not cells:
            return cells
        
        cleaned = []
        
        for cell in cells:
            if not isinstance(cell, str):
                cleaned.append(cell)
                continue
            
            cell = cell.strip()
            
            # Check if this cell contains multiple currency values
            # Pattern: "$10,207 $ 2,762" or "10,207 2,762" or "$X $Y"
            split_values = cls._split_multi_value_cell(cell)
            
            if len(split_values) > 1:
                # This cell contains multiple values - expand to multiple columns
                cleaned.extend(split_values)
            else:
                # Single value - clean it
                cleaned.append(cls._clean_single_value(cell))
        
        return cleaned
    
    @classmethod
    def _split_multi_value_cell(cls, cell: str) -> list:
        """
        Split a cell containing multiple currency values.
        
        Examples:
            "$10,207 $ 2,762" -> ["$10,207", "$2,762"]
            "10,207 2,762" -> ["10,207", "2,762"]
            "$647 $" -> ["$647"]  (trailing $ is noise)
            "$ 10,207 $ 2,762" -> ["$10,207", "$2,762"]
            "$ in millions" -> ["$ in millions"]  (preserve descriptive text)
            "Financing $2,022 $136 $ (891)" -> ["Financing", "$2,022", "$136", "$(891)"]
            "At March 31, 2025" -> ["At March 31, 2025"]  (preserve date headers)
        """
        if not cell:
            return [cell]
        
        # IMPORTANT: Preserve date headers - don't split them
        # Pattern: text containing month name + day + year
        cell_lower = cell.lower()
        date_months = ['january', 'february', 'march', 'april', 'may', 'june', 
                       'july', 'august', 'september', 'october', 'november', 'december']
        is_date_header = (
            any(month in cell_lower for month in date_months) and
            re.search(r'\b20[0-3]\d\b', cell)  # Contains year like 2024, 2025
        )
        if is_date_header:
            return [cell]
        
        # Also preserve "At" or "As of" date prefixes even without full date
        if cell_lower.startswith('at ') or cell_lower.startswith('as of '):
            return [cell]
        
        # Check for pattern: text label followed by multiple currency values
        # e.g., "Financing $2,022 $136 $ (891)" or "Total Equity $3,736 $954"
        # Pattern: word(s) followed by $ and numbers
        label_then_values = re.match(
            r'^([A-Za-z][A-Za-z\s]*?)\s+(\$?\s*[\d,\(\)\-]+(?:\s+\$?\s*[\d,\(\)\-]+)+)\s*$',
            cell
        )
        
        if label_then_values:
            label = label_then_values.group(1).strip()
            values_part = label_then_values.group(2)
            
            # Split the values part by $ or whitespace
            # Handle values like "$2,022", "$136", "$(891)", "(98)"
            values = re.findall(
                r'\$?\s*[\d,]+(?:\.\d+)?|\$?\s*\([\d,]+(?:\.\d+)?\)',
                values_part
            )
            
            if len(values) >= 2:
                # Clean up each value
                cleaned_values = []
                for val in values:
                    val = val.strip()
                    if val:
                        # Normalize spacing
                        val = re.sub(r'\$\s+', '$', val)
                        val = re.sub(r'\s+', ' ', val)
                        if val and val not in ['$', '']:
                            cleaned_values.append(val)
                
                if cleaned_values:
                    return [label] + cleaned_values
        
        # IMPORTANT: If cell contains letters (a-zA-Z) and no obvious split pattern,
        # it's likely descriptive text, preserve it as-is
        if re.search(r'[a-zA-Z]', cell):
            return [cell]
        
        # Pattern: Look for $ followed by number, potentially with another $ and number
        # This handles: "$10,207 $ 2,762" or "$10,207 $2,762"
        multi_currency = re.findall(
            r'\$?\s*([\d,]+(?:\.\d+)?)',  # Capture number groups
            cell
        )
        
        if len(multi_currency) >= 2:
            # Check if there are multiple $ symbols indicating separate values
            dollar_count = cell.count('$')
            
            if dollar_count >= 2 or (dollar_count == 1 and len(multi_currency) >= 2):
                # Multiple values - format each with $ if original had $
                values = []
                for num in multi_currency:
                    num = num.strip()
                    if num and re.match(r'[\d,]+', num):
                        # Only add $ prefix if the original cell had $ symbols
                        if '$' in cell and not num.startswith('$'):
                            values.append(f"${num}")
                        else:
                            values.append(num)
                
                # Filter out empty values
                values = [v for v in values if v and v not in ['$', '']]
                if values:
                    return values
        
        return [cell]
    
    @classmethod
    def _clean_single_value(cls, cell: str) -> str:
        """
        Clean a single cell value.
        
        - Remove trailing $ with no number
        - Normalize spacing around $
        - Remove leading/trailing whitespace
        """
        if not cell:
            return cell
        
        # Remove trailing $ with no numbers after
        cell = re.sub(r'\$\s*$', '', cell)
        
        # Normalize "$ 123" to "$123"
        cell = re.sub(r'\$\s+(\d)', r'$\1', cell)
        
        # Clean multiple spaces
        cell = re.sub(r'\s+', ' ', cell)
        
        return cell.strip()
    
    @classmethod
    def clean_table_rows(cls, table_text: str) -> str:
        """
        Clean all rows in a markdown table, properly splitting multi-value cells.
        
        Args:
            table_text: Markdown table text
            
        Returns:
            Cleaned table text with proper column separation
        """
        if not table_text:
            return table_text
        
        lines = table_text.split('\n')
        cleaned_lines = []
        expected_cols = None
        
        for line in lines:
            if '|' not in line:
                cleaned_lines.append(line)
                continue
            
            if '---' in line or '===' in line:
                # Separator line - track expected columns
                sep_cols = line.count('|') - 1
                if expected_cols is None:
                    expected_cols = sep_cols
                cleaned_lines.append(line)
                continue
            
            # Parse cells
            parts = line.split('|')
            
            # Remove leading/trailing empty parts from |...|
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            # Clean each cell, potentially expanding multi-value cells
            cleaned_cells = []
            for cell in parts:
                split_values = cls._split_multi_value_cell(cell.strip())
                for val in split_values:
                    cleaned_val = cls._clean_single_value(val)
                    
                    # Filter out standalone footnote cells
                    # Pattern: "2," or "3," or "1, 2," (digits/commas/spaces, ending in comma)
                    if re.match(r'^[\d\s,]+,$', cleaned_val):
                        continue
                    
                    cleaned_cells.append(cleaned_val)
            
            # Rebuild row
            cleaned_line = '| ' + ' | '.join(cleaned_cells) + ' |'
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)


class PDFMetadataExtractor:
    """Extract metadata from PDF filenames and content."""
    
    @staticmethod
    def compute_file_hash(pdf_path: str) -> str:
        """
        Compute MD5 hash of PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            MD5 hash string
        """
        with open(pdf_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    @staticmethod
    def extract_year(filename: str) -> Optional[int]:
        """
        Extract year from filename.
        
        Examples:
            10q0925.pdf -> 2025
            10k1222.pdf -> 2022
            
        Args:
            filename: PDF filename
            
        Returns:
            Year or None
        """
        # Pattern: 10q0925 -> month=09, year=25
        match = re.search(r'10[qk](\d{2})(\d{2})', filename.lower())
        if match:
            month, year_suffix = match.groups()
            year = 2000 + int(year_suffix)
            return year
        return None
    
    @staticmethod
    def extract_quarter(filename: str) -> Optional[str]:
        """
        Extract quarter from filename.
        
        Examples:
            10q0925.pdf -> Q3 (September)
            10q0320.pdf -> Q1 (March)
            
        Args:
            filename: PDF filename
            
        Returns:
            Quarter (Q1-Q4) or None
        """
        match = re.search(r'10q(\d{2})\d{2}', filename.lower())
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
    
    @staticmethod
    def extract_report_type(filename: str) -> str:
        """
        Extract report type from filename.
        
        Args:
            filename: PDF filename
            
        Returns:
            Report type (10-Q or 10-K)
        """
        if '10q' in filename.lower():
            return "10-Q"
        elif '10k' in filename.lower():
            return "10-K"
        return "Unknown"
    
    @staticmethod
    def create_metadata(
        pdf_path: str,
        page_no: int,
        table_title: str,
        table_index: int = 0,
        **kwargs
    ) -> TableMetadata:
        """
        Create TableMetadata from PDF file and table info.
        
        Args:
            pdf_path: Path to PDF file
            page_no: Page number
            table_title: Table title/caption
            table_index: Index of table in document (0-based)
            **kwargs: Additional metadata fields
            
        Returns:
            TableMetadata object
        """
        filename = Path(pdf_path).name
        
        # Build table-level metadata
        table_meta = {
            'page_no': page_no,
            'table_title': table_title,
            'table_id': kwargs.pop('table_id', None),
            **kwargs
        }
        
        # Build document-level metadata
        doc_metadata = {
            'year': kwargs.get('year') or PDFMetadataExtractor.extract_year(filename),
            'quarter': kwargs.get('quarter') or PDFMetadataExtractor.extract_quarter(filename),
            'report_type': kwargs.get('report_type') or PDFMetadataExtractor.extract_report_type(filename),
        }
        
        # Use the factory method (single source of truth)
        return TableMetadata.from_extraction(
            table_meta=table_meta,
            doc_metadata=doc_metadata,
            filename=filename,
            table_index=table_index,
        )


class TableClassifier:
    """Classify financial tables by type."""
    
    TABLE_TYPES = {
        'balance_sheet': [
            'balance sheet', 'statement of financial position',
            'assets', 'liabilities', 'equity'
        ],
        'income_statement': [
            'income statement', 'statement of operations',
            'statement of earnings', 'revenues', 'expenses'
        ],
        'cash_flow': [
            'cash flow', 'statement of cash flows',
            'operating activities', 'investing activities', 'financing activities'
        ],
        'equity': [
            'stockholders equity', 'shareholders equity',
            'statement of equity', 'changes in equity'
        ],
        'notes': [
            'note', 'footnote', 'disclosure'
        ]
    }
    
    @staticmethod
    def classify(title: str) -> str:
        """
        Classify table type from title.
        
        Args:
            title: Table title
            
        Returns:
            Table type category
        """
        title_lower = title.lower()
        
        for table_type, keywords in TableClassifier.TABLE_TYPES.items():
            if any(keyword in title_lower for keyword in keywords):
                return table_type
        
        return 'other'
    
    @staticmethod
    def extract_fiscal_period(table_text: str) -> Optional[str]:
        """
        Extract fiscal period from table headers.
        
        Args:
            table_text: Table text content
            
        Returns:
            Fiscal period string or None
        """
        # Look for patterns like "Three Months Ended March 31, 2025"
        patterns = [
            r'(Three|Six|Nine|Twelve) Months Ended (\w+ \d{1,2}, \d{4})',
            r'Year Ended (\w+ \d{1,2}, \d{4})',
            r'Quarter Ended (\w+ \d{1,2}, \d{4})',
            r'At (\w+ \d{1,2}, \d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, table_text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None


class TableDataFrameConverter:
    """
    Convert HTML tables to pandas DataFrames for programmatic access.
    
    Provides easy access to table data by column name, with automatic
    handling of currency values and column name normalization.
    
    Usage:
        df = TableDataFrameConverter.html_to_dataframe(html_content)
        print(df['December 31, 2024'])  # Access by column
        print(df.loc['Loans and other receivables'])  # Access by row
    """
    
    @classmethod
    def html_to_dataframe(cls, html_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """
        Convert HTML table to pandas DataFrame.
        
        Args:
            html_content: HTML string containing table(s)
            index_col: Column to use as row index (default: first column)
            
        Returns:
            pandas DataFrame with normalized columns
        """
        try:
            import pandas as pd
            from io import StringIO
        except ImportError:
            raise ImportError("pandas is required for DataFrame conversion: pip install pandas")
        
        # Parse HTML tables
        tables = pd.read_html(StringIO(html_content))
        
        if not tables:
            return pd.DataFrame()
        
        # Use first table
        df = tables[0]
        
        # Clean column names
        df.columns = [cls._normalize_column_name(str(col)) for col in df.columns]
        
        # Set index if valid
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
            df.index = [cls._normalize_row_label(str(idx)) for idx in df.index]
        
        # Clean currency values in all cells
        for col in df.columns:
            df[col] = df[col].apply(cls._clean_currency_value)
        
        return df
    
    @classmethod
    def markdown_to_dataframe(cls, markdown_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """
        Convert markdown table to pandas DataFrame.
        
        Args:
            markdown_content: Markdown table string
            index_col: Column to use as row index
            
        Returns:
            pandas DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for DataFrame conversion: pip install pandas")
        
        lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
        
        # Find header and data
        header_line = None
        data_lines = []
        
        for i, line in enumerate(lines):
            if '|' not in line:
                continue
            if '---' in line or '===' in line:
                continue  # Skip separator
            
            if header_line is None:
                header_line = line
            else:
                data_lines.append(line)
        
        if not header_line:
            return pd.DataFrame()
        
        # Parse header
        header_parts = [p.strip() for p in header_line.split('|') if p.strip()]
        
        # Parse data rows
        rows = []
        for line in data_lines:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            # Pad or truncate to match header length
            while len(parts) < len(header_parts):
                parts.append('')
            parts = parts[:len(header_parts)]
            rows.append(parts)
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=header_parts)
        
        # Set index
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
        
        return df
    
    @classmethod
    def extract_column_values(cls, df: 'pd.DataFrame', column_pattern: str) -> dict:
        """
        Extract values from columns matching a pattern.
        
        Args:
            df: pandas DataFrame
            column_pattern: Regex pattern to match column names (e.g., "2024|2023")
            
        Returns:
            Dict of {column_name: {row_label: value}}
        """
        import re
        
        result = {}
        for col in df.columns:
            if re.search(column_pattern, str(col), re.IGNORECASE):
                result[col] = df[col].to_dict()
        
        return result
    
    @classmethod
    def compare_periods(cls, df: 'pd.DataFrame', period1: str, period2: str) -> 'pd.DataFrame':
        """
        Create comparison DataFrame between two periods.
        
        Args:
            df: Source DataFrame with period columns
            period1: Column name/pattern for first period (e.g., "2024")
            period2: Column name/pattern for second period (e.g., "2023")
            
        Returns:
            DataFrame with columns: [Row Label, Period1, Period2, Change, Change %]
        """
        import pandas as pd
        
        # Find matching columns
        col1 = cls._find_column(df, period1)
        col2 = cls._find_column(df, period2)
        
        if col1 is None or col2 is None:
            raise ValueError(f"Could not find columns for periods: {period1}, {period2}")
        
        # Build comparison
        comparison = pd.DataFrame({
            'Category': df.index,
            period1: df[col1].values,
            period2: df[col2].values,
        })
        
        # Calculate change (handle non-numeric)
        def calc_change(row):
            try:
                v1 = cls._parse_currency(row[period1])
                v2 = cls._parse_currency(row[period2])
                return v1 - v2
            except (ValueError, TypeError):
                return None
        
        def calc_pct(row):
            try:
                v1 = cls._parse_currency(row[period1])
                v2 = cls._parse_currency(row[period2])
                if v2 != 0:
                    return ((v1 - v2) / abs(v2)) * 100
                return None
            except (ValueError, TypeError, ZeroDivisionError):
                return None
        
        comparison['Change'] = comparison.apply(calc_change, axis=1)
        comparison['Change %'] = comparison.apply(calc_pct, axis=1)
        
        return comparison.set_index('Category')
    
    @staticmethod
    def _find_column(df: 'pd.DataFrame', pattern: str) -> str:
        """Find column matching pattern."""
        import re
        for col in df.columns:
            if re.search(pattern, str(col), re.IGNORECASE):
                return col
        return None
    
    @staticmethod
    def _normalize_column_name(name: str) -> str:
        """Normalize column name."""
        # Remove excessive whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    @staticmethod
    def _normalize_row_label(label: str) -> str:
        """Normalize row label."""
        # Remove footnote numbers
        label = re.sub(r'\s+\d+$', '', label)
        label = re.sub(r'\(\d+\)$', '', label)
        return label.strip()
    
    @staticmethod
    def _clean_currency_value(value) -> str:
        """Clean currency value for display."""
        if pd.isna(value):
            return ''
        value = str(value).strip()
        # Normalize spacing around $
        value = re.sub(r'\$\s+', '$', value)
        # Remove extra whitespace
        value = re.sub(r'\s+', ' ', value)
        return value
    
    @staticmethod
    def _parse_currency(value) -> float:
        """Parse currency string to float."""
        if not value or pd.isna(value):
            return 0.0
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,\s]', '', str(value))
        # Handle parentheses for negative
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        return float(cleaned)


# Need pd in scope for type hints  
try:
    import pandas as pd
except ImportError:
    pd = None

