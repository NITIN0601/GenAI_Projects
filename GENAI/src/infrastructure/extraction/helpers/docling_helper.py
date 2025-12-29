"""
Docling Helper - Extraction Infrastructure.

Provides helper utilities for Docling PDF extraction including:
- PDF conversion with local model weights
- Table of Contents (TOC) extraction and caching
- Section name detection
- Table title extraction
- Spanning header detection

Moved from src/utils/extraction_utils.py for better separation of concerns.
This module is extraction-specific and belongs in infrastructure layer.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    
    # Class-level cache for TOC sections (to avoid re-parsing for every table)
    # Cache is cleared after each PDF extraction to prevent memory growth
    _toc_cache: Dict[int, dict] = {}
    
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
            current_file.parent.parent.parent.parent,  # infrastructure/extraction/helpers -> src
            current_file.parent.parent.parent.parent.parent,  # -> project root
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
            # Save original environment values to restore later (prevents global state pollution)
            original_hf_offline = os.environ.get('HF_HUB_OFFLINE')
            original_tf_offline = os.environ.get('TRANSFORMERS_OFFLINE')
            
            try:
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
                    
                    # Disable RapidOCR visualization font download
                    try:
                        from rapidocr.utils import vis_res as _rapid_vis
                        
                        def _get_font_path_no_download(self, font_path=None, lang_type='en'):
                            """Return empty path to skip font download."""
                            return ""
                        
                        _rapid_vis.VisRes.get_font_path = _get_font_path_no_download
                        logger.debug("RapidOCR visualization font download disabled")
                    except Exception as e:
                        logger.debug(f"Could not patch RapidOCR visualization: {e}")
                    
                    # Build paths to local RapidOCR models
                    rapidocr_base = Path(artifacts_path) / 'RapidOcr' / 'onnx' / 'PP-OCRv4'
                    det_model = rapidocr_base / 'det' / 'ch_PP-OCRv4_det_infer.onnx'
                    rec_model = rapidocr_base / 'rec' / 'ch_PP-OCRv4_rec_infer.onnx'
                    cls_model = rapidocr_base / 'cls' / 'ch_ppocr_mobile_v2.0_cls_infer.onnx'
                    
                    if det_model.exists() and rec_model.exists():
                        ocr_options = RapidOcrOptions(
                            det_model_path=str(det_model),
                            rec_model_path=str(rec_model),
                            cls_model_path=str(cls_model) if cls_model.exists() else None,
                        )
                        logger.info(f"Using RapidOCR with local ONNX models")
                    else:
                        ocr_options = RapidOcrOptions()
                        logger.info("Using RapidOCR with default bundled models")
                else:
                    from docling.datamodel.pipeline_options import OcrMacOptions
                    ocr_options = OcrMacOptions()
                    logger.info("Using OcrMac (macOS native OCR)")
                
                # Configure tableformer mode
                table_mode = os.environ.get('DOCLING_TABLE_MODE', 'accurate').lower()
                
                # Configure image scale
                try:
                    image_scale = float(os.environ.get('DOCLING_IMAGE_SCALE', '1.0'))
                    image_scale = max(1.0, min(4.0, image_scale))
                except ValueError:
                    image_scale = 1.0
                
                # Import TableFormerMode
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
                        logger.info("Using TableFormer ACCURATE mode")
                    
                    pipeline_options = PdfPipelineOptions(
                        artifacts_path=artifacts_path,
                        ocr_options=ocr_options,
                        do_table_structure=True,
                        table_structure_options=table_structure_options,
                        images_scale=image_scale,
                    )
                except ImportError:
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
            finally:
                # Restore original environment state
                if original_hf_offline is None:
                    os.environ.pop('HF_HUB_OFFLINE', None)
                else:
                    os.environ['HF_HUB_OFFLINE'] = original_hf_offline
                if original_tf_offline is None:
                    os.environ.pop('TRANSFORMERS_OFFLINE', None)
                else:
                    os.environ['TRANSFORMERS_OFFLINE'] = original_tf_offline
        
        # No local model weights found - check if downloads are allowed
        if allow_download:
            logger.warning("No local model weights found, downloading from HuggingFace Hub")
            converter = DocumentConverter()
            return converter.convert(pdf_path)
        
        # Default: local only, no downloads
        error_msg = (
            "No local docling model weights found and internet downloads are disabled.\n"
            "Please either:\n"
            "  1. Add model weights to src/model/doclingPackages/ and src/model/docling-models/\n"
            "  2. Set DOCLING_ARTIFACTS_PATH environment variable\n"
            "  3. Set DOCLING_ALLOW_DOWNLOAD=1 to enable downloading"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    @staticmethod
    def extract_toc_sections(doc) -> dict:
        """
        Extract Table of Contents (TOC) and build page-to-section mapping.
        
        Parses the TOC from the PDF document to create a reliable mapping of
        page numbers to section names (e.g., page 51 -> "5. Fair Value Option").
        
        Args:
            doc: Docling document
            
        Returns:
            Dict mapping page numbers to section names
        """
        toc_sections = {}
        
        def _normalize_section_name(name: str) -> str:
            """Clean section name: normalize whitespace."""
            return re.sub(r'\s+', ' ', name).strip()
        
        # Import domain patterns from centralized config
        from src.utils.financial_domain import (
            VALID_SECTION_STARTERS, FOOTNOTE_INDICATORS
        )
        
        try:
            items_list = list(doc.iterate_items())
            in_toc = False
            
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
                toc_match = re.match(r'^(\d+\.\s+)?(.+?)\s+(\d{1,3})\s*$', text)
                
                if toc_match:
                    prefix = toc_match.group(1) or ''
                    section_name = (prefix + toc_match.group(2)).strip()
                    
                    try:
                        page_num = int(toc_match.group(3))
                    except ValueError:
                        continue
                    
                    if not (1 <= page_num <= 500):
                        continue
                    
                    # Check if this looks like a footnote
                    is_footnote = False
                    section_lower = section_name.lower()
                    
                    if re.match(r'^\d+\.\s+', section_name):
                        after_number = re.sub(r'^\d+\.\s+', '', section_lower)
                        for indicator in FOOTNOTE_INDICATORS:
                            if after_number.startswith(indicator):
                                is_footnote = True
                                break
                    
                    for indicator in FOOTNOTE_INDICATORS:
                        if section_lower.startswith(indicator):
                            is_footnote = True
                            break
                    
                    if is_footnote:
                        continue
                    
                    # Validate section
                    is_valid = False
                    
                    if re.match(r'^\d+\.\s+', section_name):
                        is_valid = True
                    else:
                        first_word = section_lower.split()[0] if section_lower.split() else ''
                        if any(first_word.startswith(starter) for starter in VALID_SECTION_STARTERS):
                            is_valid = True
                    
                    if is_valid and len(section_name) > 3:
                        toc_sections[page_num] = _normalize_section_name(section_name)
            
            # Also look for numbered section headers in the document body
            numbered_section_pattern = re.compile(r'^(\d{1,2})\.\s+([A-Z][A-Za-z\s,\-]+)$')
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                
                if len(text) < 5 or len(text) > 60:
                    continue
                
                num_match = numbered_section_pattern.match(text)
                if num_match:
                    section_num = num_match.group(1)
                    section_title = num_match.group(2).strip()
                    full_section = f"{section_num}. {section_title}"
                    
                    page = DoclingHelper.get_item_page(item)
                    
                    section_lower = section_title.lower()
                    is_footnote = any(section_lower.startswith(ind) for ind in FOOTNOTE_INDICATORS)
                    
                    if page and not is_footnote and page not in toc_sections:
                        toc_sections[page] = _normalize_section_name(full_section)
            
            # Third pass: Look for SECTION_HEADER labeled items
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if not hasattr(item, 'label') or not item.label:
                    continue
                
                label_str = str(item.label).upper()
                if 'SECTION' not in label_str and 'TITLE' not in label_str:
                    continue
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                text_lower = text.lower()
                
                if len(text) < 5 or len(text) > 80:
                    continue
                
                if any(skip in text_lower for skip in ['$', '|', '---', 'total:', 'net ']):
                    continue
                
                is_footnote = any(text_lower.startswith(ind) for ind in FOOTNOTE_INDICATORS)
                if is_footnote:
                    continue
                
                first_word = text_lower.split()[0] if text_lower.split() else ''
                is_valid_section = any(first_word.startswith(starter) for starter in VALID_SECTION_STARTERS)
                
                is_business_segment = any(seg in text_lower for seg in [
                    'institutional securities', 'wealth management', 'investment management',
                    'corporate', 'intersegment', 'business segments'
                ])
                
                if is_valid_section or is_business_segment:
                    page = DoclingHelper.get_item_page(item)
                    if page and page not in toc_sections:
                        section_name = text
                        if section_name.isupper():
                            section_name = section_name.title()
                        toc_sections[page] = _normalize_section_name(section_name)
            
        except Exception as e:
            logger.debug(f"Error extracting TOC sections: {e}")
        
        return toc_sections
    
    @staticmethod
    def get_section_for_page(toc_sections: dict, page_no: int) -> str:
        """
        Get section name for a given page number using TOC mapping.
        
        Args:
            toc_sections: Dict from extract_toc_sections()
            page_no: Page number to look up
            
        Returns:
            Section name or empty string if not found
        """
        if not toc_sections:
            return ""
        
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
        Find preceding TEXT items that could be a missing spanning header.
        
        Args:
            doc: Docling document
            table_item: The table item to find header for
            page_no: Page number of the table
            
        Returns:
            Spanning header text if found, empty string otherwise
        """
        MONTH_NAMES = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        ]
        PERIOD_INDICATORS = ['ended', 'ending', 'as of', 'at ', 'for the', 'period']
        YEAR_PATTERN = re.compile(r'\b20[0-3]\d\b')
        
        def is_date_period_header(text: str) -> bool:
            text_lower = text.lower().strip()
            
            if len(text_lower) < 10 or len(text_lower) > 100:
                return False
            
            if not YEAR_PATTERN.search(text):
                return False
            
            has_month = any(month in text_lower for month in MONTH_NAMES)
            has_period = any(ind in text_lower for ind in PERIOD_INDICATORS)
            
            return has_month or has_period
        
        try:
            items_list = list(doc.iterate_items())
            preceding_headers = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if item is table_item:
                    break
                
                item_page = DoclingHelper.get_item_page(item)
                
                if item_page < page_no - 1 or item_page > page_no:
                    continue
                
                if not hasattr(item, 'label'):
                    continue
                
                label_name = item.label.name if hasattr(item.label, 'name') else str(item.label)
                if label_name not in ['TEXT', 'CAPTION', 'TITLE']:
                    continue
                
                text = getattr(item, 'text', '')
                if not text:
                    continue
                
                text = str(text).strip()
                
                if is_date_period_header(text):
                    preceding_headers.append((item_page, text))
            
            if preceding_headers:
                same_page = [h for h in preceding_headers if h[0] == page_no]
                if same_page:
                    return same_page[-1][1]
                return preceding_headers[-1][1]
                
        except Exception as e:
            logger.debug(f"Error finding preceding spanning header: {e}")
        
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
        
        header_cells = [''] + [spanning_header] * (num_columns - 1)
        header_row = '| ' + ' | '.join(header_cells) + ' |'
        
        return header_row + '\n' + table_markdown
    
    @staticmethod
    def clear_toc_cache(doc_id: int = None) -> None:
        """
        Clear TOC cache to free memory after PDF extraction completes.
        
        Args:
            doc_id: Specific doc ID to clear, or None to clear all
        """
        if doc_id is not None:
            DoclingHelper._toc_cache.pop(doc_id, None)
        else:
            DoclingHelper._toc_cache.clear()
    
    @staticmethod
    def extract_section_name(doc, table_item, page_no: int, toc_sections: dict = None) -> str:
        """
        Extract the section name that contains this table.
        
        Uses multiple strategies in priority order:
        1. TOC-based lookup (most reliable)
        2. Pattern matching for SECTION_HEADER/TITLE labels
        3. Numbered section pattern matching
        
        Args:
            doc: Docling document
            table_item: The table item
            page_no: Page number
            toc_sections: Optional pre-parsed TOC dict
            
        Returns:
            Section name or empty string if not found
        """
        # Strategy 1: TOC-based lookup (most reliable)
        if toc_sections is None:
            doc_id = id(doc)
            if doc_id not in DoclingHelper._toc_cache:
                DoclingHelper._toc_cache[doc_id] = DoclingHelper.extract_toc_sections(doc)
            toc_sections = DoclingHelper._toc_cache[doc_id]
        
        if toc_sections:
            section = DoclingHelper.get_section_for_page(toc_sections, page_no)
            if section:
                return section
        
        # Import domain patterns
        from src.utils.financial_domain import (
            BUSINESS_SEGMENTS, GENERAL_SECTION_HEADERS
        )
        
        try:
            items_list = list(doc.iterate_items())
            section_candidates = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if item is table_item:
                    break
                
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                if item_page >= page_no - 2:
                    if not hasattr(item, 'text') or not item.text:
                        continue
                    
                    text = str(item.text).strip()
                    
                    if not (3 < len(text) < 80):
                        continue
                    
                    text_lower = text.lower()
                    
                    if any(skip in text_lower for skip in ['$', '|', '---', 'row', 'total:', 'net ']):
                        continue
                    
                    # Check label
                    is_section_or_title = False
                    
                    if hasattr(item, 'label') and item.label:
                        if item.label == DocItemLabel.SECTION_HEADER:
                            is_section_or_title = True
                        elif hasattr(DocItemLabel, 'TITLE') and item.label == DocItemLabel.TITLE:
                            is_section_or_title = True
                        else:
                            label_str = str(item.label).upper()
                            if 'SECTION' in label_str or 'TITLE' in label_str:
                                is_section_or_title = True
                    
                    matches_business_segment = any(seg in text_lower for seg in BUSINESS_SEGMENTS)
                    matches_general_header = any(hdr in text_lower for hdr in GENERAL_SECTION_HEADERS)
                    is_note_header = bool(re.match(r'^Note\s+\d+', text, re.IGNORECASE))
                    is_numbered_header = bool(re.match(r'^\d+\.\s+[A-Z]', text))
                    
                    if matches_business_segment:
                        section_candidates.append(('business', text))
                    elif is_numbered_header and len(text) < 60:
                        section_candidates.append(('numbered', text))
                    elif is_note_header:
                        section_candidates.append(('note', text))
                    elif matches_general_header and is_section_or_title:
                        section_candidates.append(('general', text))
            
            if section_candidates:
                priority_order = {'business': 0, 'numbered': 0, 'note': 1, 'general': 2}
                section_candidates.sort(key=lambda x: priority_order.get(x[0], 99))
                
                best_priority = section_candidates[0][0]
                same_priority = [c for c in section_candidates if c[0] == best_priority]
                result = same_priority[-1][1]
                
                result = re.sub(r'^Note\s+(?=\d)', '', result, flags=re.IGNORECASE).strip()
                
                if not result or result.isdigit() or re.match(r'^\d+\.?$', result):
                    if len(same_priority[-1][1]) > len(result):
                        result = same_priority[-1][1]
                
                if result.isupper():
                    result = result.title()
                return result
                
        except Exception as e:
            logger.debug(f"Error extracting section name: {e}")
        
        return ""
    
    @staticmethod
    def extract_table_title(doc, table_item, table_index: int, page_no: int) -> str:
        """
        Extract meaningful table title from surrounding context.
        
        Args:
            doc: Docling document
            table_item: The table item
            table_index: Index of table in document
            page_no: Page number
            
        Returns:
            Extracted table title
        """
        def clean_title(text: str) -> str:
            if not text:
                return ""
            
            text = _SECTION_NUMBER_PREFIX.sub('', text)
            text = _NOTE_PREFIX_PATTERN.sub('', text)
            text = _TABLE_PREFIX_PATTERN.sub('', text)
            text = _ROW_RANGE_PATTERN.sub('', text)
            text = _TRAILING_NUMBER_PATTERN.sub('', text)
            text = _PAREN_NUMBER_PATTERN.sub('', text)
            text = _SUPERSCRIPT_PATTERN.sub('', text)
            
            return text.strip()[:100]

        def is_valid_title(text: str) -> bool:
            text_lower = text.lower().strip()
            
            if len(text) < 5 or len(text) > 120:
                return False
            
            if text.startswith('('):
                return False
            
            if text[0].islower():
                return False
            
            invalid_patterns = [
                'three months ended', 'six months ended', 'nine months ended',
                'year ended', 'quarter ended', 'at march', 'at december',
                '$ in millions', '$ in billions', 'in millions', 'in billions',
                'unaudited', 'address of principal', 'the following', 'as follows',
            ]
            
            for pattern in invalid_patterns:
                if pattern in text_lower:
                    return False
            
            if not any(c.isalpha() for c in text):
                return False
            
            return True

        # Try caption first
        if hasattr(table_item, 'caption') and table_item.caption:
            caption = str(table_item.caption).strip()
            if caption and len(caption) > 3 and is_valid_title(caption):
                return clean_title(caption)
        
        try:
            items_list = list(doc.iterate_items())
            preceding_texts = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if item is table_item:
                    break
                
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                if item_page >= page_no - 1:
                    label = str(item.label) if hasattr(item, 'label') else ''
                    
                    if 'SECTION' in label.upper() or 'TITLE' in label.upper() or 'TEXT' in label.upper():
                        if hasattr(item, 'text') and item.text:
                            text = str(item.text).strip()
                            if 5 < len(text) < 150 and not text.startswith('|'):
                                preceding_texts.append(text)
            
            if preceding_texts:
                for text in reversed(preceding_texts):
                    if is_valid_title(text):
                        title = text
                        for prefix in ['Note ', 'NOTE ', 'Table ']:
                            if title.startswith(prefix):
                                title = title[len(prefix):].strip()
                                if title and title[0].isdigit():
                                    parts = title.split(' ', 1)
                                    if len(parts) > 1:
                                        title = parts[1].strip()
                        
                        if title and len(title) > 3:
                            return clean_title(title)
        except Exception as e:
            logger.debug(f"Error extracting table title: {e}")
        
        return f"Table {table_index + 1} (Page {page_no})"
