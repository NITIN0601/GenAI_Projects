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


# =============================================================================
# SECTION HIERARCHY TRACKER
# =============================================================================

class SectionHierarchyTracker:
    """
    Dynamic section hierarchy tracker for financial documents.
    
    Uses pattern matching + frequency analysis + position-based fallback
    to classify section headers into hierarchy levels:
    - toc: Table of Contents entry (e.g., "Management's Discussion and Analysis of Financial Condition...")
    - main: Main section (repeating on multiple pages)
    - section1: Primary subsection (e.g., "Executive Summary", "Business Segments")
    - section2: Secondary subsection (e.g., "Institutional Securities", "Wealth Management")
    - section3: Topic (e.g., "Investment Banking", "Net New Assets")
    - section4: Detail (e.g., "Advisor-led Channel", "Rollforward")
    """
    
    def __init__(self, config_path: str = None):
        """Initialize with optional config file path."""
        self.patterns = self._load_patterns(config_path)
        self.current = {
            'toc': '',
            'main': '',
            'section1': '',
            'section2': '',
            'section3': '',
            'section4': ''
        }
        self.repeating_headers = set()  # Headers that appear 3+ times (MAIN sections)
        self.header_counts = {}  # Track frequency of each header
        
    def _load_patterns(self, config_path: str = None) -> dict:
        """Load section patterns from config file."""
        import json
        
        if config_path is None:
            # Default path
            config_path = Path(__file__).parent.parent.parent.parent.parent / 'config' / 'section_patterns.json'
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load section patterns config: {e}")
            return self._default_patterns()
    
    def _default_patterns(self) -> dict:
        """Default patterns if config file not found."""
        return {
            'toc_patterns': ["Management's Discussion and Analysis of Financial Condition"],
            'main_section_patterns': ["Management's Discussion and Analysis"],
            'section1_patterns': ["Executive Summary", "Business Segments"],
            'section2_patterns': {'patterns': ["Institutional Securities", "Wealth Management", "Investment Management"]},
            'section3_patterns': {'patterns': ["Investment Banking", "Income Statement", "Net New Assets"]},
            'section4_patterns': {'patterns': ["Rollforward", "Average", "Channel"]}
        }
    
    def pre_scan_headers(self, headers: list) -> None:
        """
        Pre-scan all section headers to identify repeating headers (MAIN sections).
        
        Args:
            headers: List of (page, text) tuples
        """
        from collections import Counter
        
        # Count each header
        texts = [h[1] for h in headers]
        counts = Counter(texts)
        
        # Headers appearing 3+ times are MAIN sections
        self.repeating_headers = {text for text, count in counts.items() if count >= 3}
        self.header_counts = dict(counts)
        
        logger.debug(f"Found {len(self.repeating_headers)} repeating headers (MAIN sections)")
    
    def classify_header(self, text: str) -> str:
        """
        Classify a section header into hierarchy level.
        
        Returns: 'toc', 'main', 'section1', 'section2', 'section3', 'section4', 'table_title', or 'unknown'
        """
        # Step 1: Normalize text - fix OCR broken words
        text_normalized = self._normalize_ocr_text(text)
        text_lower = text_normalized.lower().strip()
        
        # Step 2: Check for table title patterns FIRST - these should NOT update section hierarchy
        table_title_data = self.patterns.get('table_title_patterns', {})
        table_title_patterns = table_title_data.get('patterns', []) if isinstance(table_title_data, dict) else table_title_data
        for pattern in table_title_patterns:
            if pattern.lower() in text_lower:
                return 'table_title'
        
        # Rule 1: Check for TOC-level patterns
        for pattern in self.patterns.get('toc_patterns', []):
            if pattern.lower() in text_lower:
                return 'toc'
        
        # Rule 2: Check for MAIN section patterns (before repeating headers check)
        for pattern in self.patterns.get('main_section_patterns', []):
            if pattern.lower() in text_lower:
                return 'main'
        
        # Rule 3: Check if this is a repeating header (MAIN section)
        # But only if it's not already classified as something more specific
        if text in self.repeating_headers:
            # Check if it matches section patterns first
            if not self._matches_section_pattern(text_lower):
                return 'main'
        
        # Rule 4: Check for Section1 patterns
        for pattern in self.patterns.get('section1_patterns', []):
            if pattern.lower() in text_lower:
                return 'section1'
        
        # Rule 5: Check for Section2 patterns (business segments)
        section2_data = self.patterns.get('section2_patterns', {})
        section2_patterns = section2_data.get('patterns', []) if isinstance(section2_data, dict) else section2_data
        for pattern in section2_patterns:
            if pattern.lower() in text_lower:
                return 'section2'
        
        # Rule 6: Check for Section3 patterns (topics)
        section3_data = self.patterns.get('section3_patterns', {})
        section3_patterns = section3_data.get('patterns', []) if isinstance(section3_data, dict) else section3_data
        for pattern in section3_patterns:
            if pattern.lower() in text_lower:
                return 'section3'
        
        # Rule 7: Check for Section4 patterns (details)
        section4_data = self.patterns.get('section4_patterns', {})
        section4_patterns = section4_data.get('patterns', []) if isinstance(section4_data, dict) else section4_data
        for pattern in section4_patterns:
            if pattern.lower() in text_lower:
                return 'section4'
        
        # Fallback: unknown (will use position-based logic)
        return 'unknown'
    
    def _normalize_ocr_text(self, text: str) -> str:
        """
        Normalize OCR text to fix common issues like broken words.
        
        Args:
            text: Raw OCR text
            
        Returns:
            Normalized text with OCR issues fixed
        """
        import re
        
        # Fix common OCR broken words
        ocr_fixes = {
            r'Wealth\s+Manageme\s*nt': 'Wealth Management',
            r'Institutional\s+Securitie\s*s': 'Institutional Securities',
            r'Investment\s+Manageme\s*nt': 'Investment Management',
            r'Manageme\s*nt\'?s?\s+Discussion': "Management's Discussion",
        }
        
        result = text
        for pattern, replacement in ocr_fixes.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Collapse multiple spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def _matches_section_pattern(self, text_lower: str) -> bool:
        """Check if text matches any section 1-4 pattern."""
        for level in ['section1_patterns', 'section2_patterns', 'section3_patterns', 'section4_patterns']:
            data = self.patterns.get(level, {})
            patterns = data.get('patterns', []) if isinstance(data, dict) else data
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return True
        return False
    
    def process_header(self, text: str, page: int) -> dict:
        """
        Process a section header and update current hierarchy state.
        
        Args:
            text: Section header text
            page: Page number
            
        Returns:
            Current hierarchy state after processing
        """
        level = self.classify_header(text)
        
        # Table titles should NOT update section hierarchy
        if level == 'table_title':
            return self.get_current_hierarchy()
        
        if level == 'toc':
            self.current['toc'] = self._normalize_ocr_text(text)
            # TOC clears everything below
            self.current['main'] = ''
            self.current['section1'] = ''
            self.current['section2'] = ''
            self.current['section3'] = ''
            self.current['section4'] = ''
        elif level == 'main':
            self.current['main'] = self._normalize_ocr_text(text)
            # Main doesn't clear section1+ (they persist across pages)
        elif level == 'section1':
            self.current['section1'] = self._normalize_ocr_text(text)
            self.current['section2'] = ''
            self.current['section3'] = ''
            self.current['section4'] = ''
        elif level == 'section2':
            self.current['section2'] = self._normalize_ocr_text(text)
            self.current['section3'] = ''
            self.current['section4'] = ''
        elif level == 'section3':
            self.current['section3'] = self._normalize_ocr_text(text)
            self.current['section4'] = ''
        elif level == 'section4':
            self.current['section4'] = self._normalize_ocr_text(text)
        elif level == 'unknown':
            # Position-based fallback: if we're within a section2, this is likely section3
            if self.current['section2'] and not self.current['section3']:
                self.current['section3'] = self._normalize_ocr_text(text)
            elif self.current['section3'] and not self.current['section4']:
                self.current['section4'] = self._normalize_ocr_text(text)
            elif self.current['section1'] and not self.current['section2']:
                self.current['section2'] = self._normalize_ocr_text(text)
            else:
                # Default: treat as section3
                self.current['section3'] = self._normalize_ocr_text(text)
        
        return self.get_current_hierarchy()
    
    def get_current_hierarchy(self) -> dict:
        """Get copy of current hierarchy state."""
        return self.current.copy()


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
    def extract_toc_hierarchy(doc) -> dict:
        """
        Extract Table of Contents with hierarchical section levels.
        
        Parses the TOC and PDF body to build a mapping of page numbers to
        hierarchical section paths (level1 → level2 → level3).
        
        Args:
            doc: Docling document
            
        Returns:
            Dict mapping page numbers to section hierarchy:
            {page: {'level1': 'Main Section', 'level2': 'Subsection', 'level3': 'Detail'}}
        """
        hierarchy = {}
        
        # Pattern to detect section numbering levels
        # "1." = level 1, "1.1" = level 2, "1.1.1" = level 3
        level1_pattern = re.compile(r'^(\d+)\.\s+(.+)$')  # "1. Section Name"
        level2_pattern = re.compile(r'^(\d+)\.(\d+)\s+(.+)$')  # "1.1 Subsection"
        level3_pattern = re.compile(r'^(\d+)\.(\d+)\.(\d+)\s+(.+)$')  # "1.1.1 Detail"
        
        # Track current hierarchy state
        current_level1 = ""
        current_level2 = ""
        current_level3 = ""
        
        # Storage for all section headers found
        section_entries = []  # [(page, level, name)]
        
        try:
            items_list = list(doc.iterate_items())
            
            # First pass: Extract from TOC entries (pattern: "Name ...page")
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if not hasattr(item, 'text') or not item.text:
                    continue
                
                text = str(item.text).strip()
                
                # Skip very short or very long text
                if len(text) < 5 or len(text) > 100:
                    continue
                
                # Pattern: "Section Name PageNumber" at end
                toc_match = re.match(r'^(.+?)\s+(\d{1,3})\s*$', text)
                if toc_match:
                    section_text = toc_match.group(1).strip()
                    try:
                        page_num = int(toc_match.group(2))
                    except ValueError:
                        continue
                    
                    if not (1 <= page_num <= 500):
                        continue
                    
                    # Determine level from numbering pattern
                    level = 1  # Default
                    name = section_text
                    
                    l3_match = level3_pattern.match(section_text)
                    l2_match = level2_pattern.match(section_text)
                    l1_match = level1_pattern.match(section_text)
                    
                    if l3_match:
                        level = 3
                        name = section_text
                    elif l2_match:
                        level = 2
                        name = section_text
                    elif l1_match:
                        level = 1
                        name = section_text
                    
                    section_entries.append((page_num, level, name))
            
            # Second pass: Look for SECTION_HEADER labeled items in PDF body
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
                if len(text) < 5 or len(text) > 80:
                    continue
                
                page = DoclingHelper.get_item_page(item)
                if not page:
                    continue
                
                # Check if this is a numbered subsection
                l3_match = level3_pattern.match(text)
                l2_match = level2_pattern.match(text)
                l1_match = level1_pattern.match(text)
                
                if l3_match:
                    section_entries.append((page, 3, text))
                elif l2_match:
                    section_entries.append((page, 2, text))
                elif l1_match:
                    section_entries.append((page, 1, text))
                elif text[0].isupper() and len(text) > 10:
                    # Non-numbered section header - treat as subsection
                    section_entries.append((page, 2, text))
            
            # Sort by page number
            section_entries.sort(key=lambda x: x[0])
            
            # Build hierarchy mapping
            for page, level, name in section_entries:
                if level == 1:
                    current_level1 = name
                    current_level2 = ""
                    current_level3 = ""
                elif level == 2:
                    current_level2 = name
                    current_level3 = ""
                elif level == 3:
                    current_level3 = name
                
                hierarchy[page] = {
                    'level1': current_level1,
                    'level2': current_level2,
                    'level3': current_level3
                }
            
            # Fill gaps - propagate hierarchy to all pages
            if hierarchy:
                max_page = max(hierarchy.keys())
                current = {'level1': '', 'level2': '', 'level3': ''}
                
                for pg in range(1, max_page + 1):
                    if pg in hierarchy:
                        current = hierarchy[pg].copy()
                    else:
                        hierarchy[pg] = current.copy()
                        
        except Exception as e:
            logger.debug(f"Error extracting TOC hierarchy: {e}")
        
        return hierarchy
    
    @staticmethod
    def get_hierarchy_for_page(hierarchy: dict, page_no: int) -> dict:
        """
        Get section hierarchy for a given page number.
        
        Args:
            hierarchy: Dict from extract_toc_hierarchy()
            page_no: Page number to look up
            
        Returns:
            Dict with level1, level2, level3 or empty dict if not found
        """
        if not hierarchy:
            return {'level1': '', 'level2': '', 'level3': ''}
        
        if page_no in hierarchy:
            return hierarchy[page_no]
        
        # Find closest lower page
        best_page = 0
        for pg in hierarchy.keys():
            if pg <= page_no and pg > best_page:
                best_page = pg
        
        if best_page:
            return hierarchy[best_page]
        
        return {'level1': '', 'level2': '', 'level3': ''}
    
    @staticmethod
    def extract_full_section_hierarchy(doc) -> dict:
        """
        Extract full section hierarchy using SectionHierarchyTracker.
        
        This method provides deeper hierarchy detection than extract_toc_hierarchy,
        using pattern matching, frequency analysis, and position-based fallback.
        
        Args:
            doc: Docling document
            
        Returns:
            Dict mapping page numbers to full section hierarchy:
            {page: {'toc': ..., 'main': ..., 'section1': ..., 'section2': ..., 'section3': ..., 'section4': ...}}
        """
        hierarchy = {}
        tracker = SectionHierarchyTracker()
        
        try:
            items_list = list(doc.iterate_items())
            
            # Step 1: Collect all section headers for pre-scan
            all_headers = []
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
                if len(text) < 5 or len(text) > 100:
                    continue
                
                page = DoclingHelper.get_item_page(item)
                all_headers.append((page, text))
            
            # Step 2: Pre-scan to identify repeating headers (MAIN sections)
            tracker.pre_scan_headers(all_headers)
            
            # Step 3: Process headers in page order
            all_headers.sort(key=lambda x: x[0])
            
            for page, text in all_headers:
                current = tracker.process_header(text, page)
                hierarchy[page] = current.copy()
            
            # Step 4: Fill gaps - propagate hierarchy to pages without headers
            if hierarchy:
                max_page = max(hierarchy.keys())
                current_state = {'toc': '', 'main': '', 'section1': '', 'section2': '', 'section3': '', 'section4': ''}
                
                for pg in range(1, max_page + 1):
                    if pg in hierarchy:
                        current_state = hierarchy[pg].copy()
                    else:
                        hierarchy[pg] = current_state.copy()
            
            logger.debug(f"Built full section hierarchy for {len(hierarchy)} pages")
            
        except Exception as e:
            logger.debug(f"Error extracting full section hierarchy: {e}")
        
        return hierarchy
    
    @staticmethod
    def get_full_hierarchy_for_page(hierarchy: dict, page_no: int) -> dict:
        """
        Get full section hierarchy for a given page number.
        
        Args:
            hierarchy: Dict from extract_full_section_hierarchy()
            page_no: Page number to look up
            
        Returns:
            Dict with toc, main, section1, section2, section3, section4
        """
        empty = {'toc': '', 'main': '', 'section1': '', 'section2': '', 'section3': '', 'section4': ''}
        
        if not hierarchy:
            return empty
        
        if page_no in hierarchy:
            return hierarchy[page_no]
        
        # Find closest lower page
        best_page = 0
        for pg in hierarchy.keys():
            if pg <= page_no and pg > best_page:
                best_page = pg
        
        if best_page:
            return hierarchy[best_page]
        
        return empty
    
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
        1. Backwards search for numbered SECTION_HEADER (most precise)
        2. TOC-based lookup (fallback)
        3. Pattern matching for other headers
        
        Args:
            doc: Docling document
            table_item: The table item
            page_no: Page number
            toc_sections: Optional pre-parsed TOC dict
            
        Returns:
            Section name or empty string if not found
        """
        # Strategy 1: Backwards search for numbered SECTION_HEADER (most precise)
        # This correctly handles multiple sections on same page
        try:
            items_list = list(doc.iterate_items())
            table_found = False
            distance = 0
            
            for item_data in reversed(items_list):
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if item is table_item:
                    table_found = True
                    distance = 0
                    continue
                
                if not table_found:
                    continue
                
                distance += 1
                if distance > 100:  # Search up to 100 items back for section
                    break
                
                # Look for SECTION_HEADER with numbered section pattern (e.g., "19. Segment...")
                if hasattr(item, 'label'):
                    label = str(item.label.value) if hasattr(item.label, 'value') else str(item.label)
                    if 'SECTION' in label.upper() and hasattr(item, 'text') and item.text:
                        text = item.text.strip()
                        # Check if it's a numbered section (e.g., "19. Segment, Geographic...")
                        if re.match(r'^\d+\.\s+[A-Z]', text):
                            return text
        except Exception:
            pass
        
        # Strategy 2: TOC-based lookup (fallback)
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
    def extract_table_title_hybrid(doc, table_item, table_index: int, page_no: int) -> str:
        """
        HYBRID table title extraction - combines multiple approaches for best accuracy.
        
        Strategy:
        1. Get IMMEDIATE preceding text on same page (most accurate for same-page tables)
        2. Validate if it looks like a table title (not a section header or footnote)
        3. Fallback to pattern-based approach if immediate text is invalid
        
        Args:
            doc: Docling document
            table_item: The table item
            table_index: Index of table in document
            page_no: Page number
            
        Returns:
            Extracted table title
        """
        import json
        
        # Load config for table title patterns
        try:
            config_path = Path(__file__).parent.parent.parent.parent.parent / 'config' / 'section_patterns.json'
            with open(config_path, 'r') as f:
                config = json.load(f)
            table_title_patterns = config.get('table_title_patterns', {}).get('patterns', [])
            section_patterns = (
                config.get('main_section_patterns', []) +
                config.get('section1_patterns', []) +
                config.get('section2_patterns', {}).get('patterns', []) +
                config.get('section3_patterns', {}).get('patterns', [])
            )
        except Exception:
            table_title_patterns = []
            section_patterns = []
        
        # =====================================================================
        # DYNAMIC TITLE DETECTION PATTERNS
        # Based on analysis of 972 tables across 4 PDFs
        # =====================================================================
        
        # Short headers (< 30 chars) that are SUB-HEADERS needing parent context
        # These appear frequently near tables but aren't the main title
        # NOTE: Valid table titles like 'Deposits', 'Dividends' should NOT be here
        #       Instead, add them to table_title_patterns in section_patterns.json
        SUB_HEADER_PATTERNS = [
            # Generic sub-table markers
            r'^by\s+(region|property\s*type|product|asset\s*class|industry|type)$',
            r'^(americas|emea|asia|total)$',
            # Common short headers that repeat frequently
            r'^risk disclosures$',
            r'^table of contents$',
        ]
        
        # Headers that START with these are valid MAIN titles
        VALID_TITLE_STARTERS = [
            'institutional securities',
            'wealth management',
            'investment management', 
            'assets under management',
            'net income applicable',
            'consolidated results',
            'allowance for credit losses',
            'fair value',
            'regulatory capital',
            'liquidity resources',
            'credit spread',
            'selected financial',
            'reconciliation',
            'reconciliations',
            'advisor-led',
            'self-directed',
            'workplace',
            'deposits',
            'dividends',
            'borrowings',
            'commitments',
            'guarantees',
            'forecasted',
        ]
        
        # Minimum length for a standalone title (shorter needs parent)
        MIN_STANDALONE_TITLE_LENGTH = 30
        
        def is_sub_header(text: str) -> bool:
            """Check if text is a short sub-header that needs parent context."""
            text_lower = text.lower().strip()
            
            # FIRST: Check if text matches a known table title pattern from config
            # If it matches, it's a VALID title, not a sub-header
            for pattern in table_title_patterns:
                if pattern.lower() in text_lower or text_lower in pattern.lower():
                    return False  # It's a known table title - NOT a sub-header
            
            # Check against known sub-header patterns
            for pattern in SUB_HEADER_PATTERNS:
                if re.match(pattern, text_lower, re.IGNORECASE):
                    return True
            
            # Short headers (< 25 chars) that don't start with valid starters
            if len(text) < 25:
                for starter in VALID_TITLE_STARTERS:
                    if text_lower.startswith(starter):
                        return False  # It's a valid title, not sub-header
                return True  # Short and not a valid starter = sub-header
            
            return False

        
        def is_valid_main_title(text: str) -> bool:
            """Check if text is a valid main table title."""
            text_lower = text.lower().strip()
            
            # Must be reasonably long
            if len(text) < 15:
                return False
            
            # Must start with capital letter
            if not text[0].isupper():
                return False
            
            # Check for valid title starters
            for starter in VALID_TITLE_STARTERS:
                if text_lower.startswith(starter):
                    return True
            
            # Or be long and descriptive (> 30 chars)
            if len(text) >= MIN_STANDALONE_TITLE_LENGTH:
                # But not if it's a known invalid pattern
                invalid_patterns = [
                    'notes to consolidated financial',
                    'management\'s discussion and analysis',
                    'securities registered pursuant',
                ]
                for inv in invalid_patterns:
                    if inv in text_lower:
                        return False
                return True
            
            return False
        
        def is_sub_table_title(text: str) -> bool:
            """Wrapper for backward compatibility."""
            return is_sub_header(text)
        
        def is_table_title_candidate(text: str) -> bool:
            """Check if text is a good table title candidate."""
            if not text or len(text) < 5 or len(text) > 120:
                return False
            
            text_lower = text.lower().strip()
            
            # Reject table data patterns (numbers, currency, dates)
            table_data_patterns = [
                r'^\s*\$',  # Starts with $
                r'^\s*\(\d+\)',  # Starts with (N)
                r'^\s*[\d,]+$',  # Pure numbers
                r'^\s*[\d,]+\s*%?$',  # Numbers with optional %
                r'^(sept|oct|nov|dec|jan|feb|mar|apr|may|jun|jul|aug)\s+\d',  # Date abbrev
                r'^\d{4}$',  # Just a year
            ]
            for pattern in table_data_patterns:
                if re.match(pattern, text_lower):
                    return False
            
            # Reject clear non-titles
            invalid_starters = [
                'the ', 'our ', 'this ', 'these ', 'such ', 'certain ',
                'see ', 'refer ', 'note:', 'notes:', 'source:',
                '(', '*', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
            ]
            for starter in invalid_starters:
                if text_lower.startswith(starter):
                    return False
            
            # Reject if contains sentence indicators
            if text.count('.') >= 2 or (text.endswith('.') and len(text) > 60):
                return False
            
            # Reject standalone date/period headers (not table titles)
            date_period_patterns = [
                r'^at\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
                r'^(three|six|nine)\s+months?\s+ended',
                r'^year\s+ended',
            ]
            for pattern in date_period_patterns:
                if re.match(pattern, text_lower):
                    return False
            
            return True
        
        def is_known_table_title(text: str) -> bool:
            """Check if text matches a known table title pattern.
            
            Handles OCR spacing issues by normalizing whitespace before matching.
            """
            # Normalize: collapse multiple spaces, lowercase, strip
            text_normalized = re.sub(r'\s+', ' ', text.lower().strip())
            
            for pattern in table_title_patterns:
                pattern_normalized = re.sub(r'\s+', ' ', pattern.lower().strip())
                if pattern_normalized in text_normalized:
                    return True
            return False
        
        def clean_title(text: str) -> str:
            """Clean up the title text, including OCR artifacts."""
            text = re.sub(r'^\d+[\.\:\s]+\s*', '', text)  # Remove leading numbers
            text = re.sub(r'\s+\d+\s*$', '', text)  # Remove trailing numbers
            text = re.sub(r'\s*\(\d+\)\s*$', '', text)  # Remove (N) at end
            # Normalize OCR spacing: collapse multiple spaces to single
            text = re.sub(r'\s+', ' ', text)
            # Normalize dashes: replace em-dash, en-dash with regular dash
            text = text.replace('—', '-').replace('–', '-')
            return text.strip()[:100]
        
        # === APPROACH 1: Get immediate preceding text (most accurate) ===
        # Extended to 30 items and 3 pages back for multi-page tables
        items_list = list(doc.iterate_items())
        immediate_candidates = []  # (text, distance_from_table, label)
        
        # Page headers that should NEVER be used as table titles
        PAGE_HEADER_PATTERNS = [
            'notes to consolidated financial statements',
            'management\'s discussion and analysis',
            'quarterly report on form 10',
            'table of contents',
            'annual report on form 10',
        ]
        
        # === APPROACH -1: Find IMMEDIATE preceding text (actual table title) ===
        # The table title is literally the text directly above the table
        # This takes highest priority - check first 5 items before the table
        items_list = list(doc.iterate_items())
        immediate_title = None
        table_found = False
        
        items_checked = 0
        for item_data in reversed(items_list):
            item = item_data[0] if isinstance(item_data, tuple) else item_data
            
            if item is table_item:
                table_found = True
                items_checked = 0
                continue
            
            if not table_found:
                continue
            
            items_checked += 1
            
            # For multi-page tables, check up to 15 items before
            if items_checked > 15:
                break
            
            item_page = DoclingHelper.get_item_page(item)
            # For multi-page tables (spanning 2-3 pages), look back up to 3 pages
            if item_page < page_no - 3:
                continue  # Too far back
            
            if not hasattr(item, 'text') or not item.text:
                continue
            
            text = str(item.text).strip()
            
            # Skip very short or very long text
            if len(text) < 5 or len(text) > 120:
                continue
            
            # Skip if it looks like table data (numbers, currency)
            if re.match(r'^[\$\(\d\,\.\%\)\s\-]+$', text):
                continue
            
            # Skip page headers
            text_lower = text.lower()
            if any(ph in text_lower for ph in PAGE_HEADER_PATTERNS):
                continue
            
            # Skip footnotes and references
            if text_lower.startswith(('(', 'note:', 'see ', '1 ', '2 ', '* ')):
                continue
                
            # This looks like a valid title - use it!
            if is_table_title_candidate(text):
                immediate_title = text
                break
        
        # If we found immediate title, use it
        if immediate_title:
            return clean_title(immediate_title)
        
        # === APPROACH 0: Find CLOSEST SECTION_HEADER (highest priority) ===
        # This is the most reliable method - section headers are explicitly labeled
        closest_section_header = None
        table_found = False
        distance = 0
        
        for item_data in reversed(items_list):
            item = item_data[0] if isinstance(item_data, tuple) else item_data
            
            if item is table_item:
                table_found = True
                distance = 0
                continue
            
            if not table_found:
                continue
            
            distance += 1
            if distance > 15:  # Only check closest 15 items for section headers
                break
            
            item_page = DoclingHelper.get_item_page(item)
            if item_page < page_no - 1:  # Section header should be on same or previous page
                continue
            
            if not hasattr(item, 'text') or not item.text:
                continue
            
            text = str(item.text).strip()
            label = str(item.label) if hasattr(item, 'label') else 'UNKNOWN'
            
            # Check if this is a SECTION_HEADER
            if 'SECTION' in label.upper() or 'TITLE' in label.upper():
                text_lower = text.lower()
                # Skip page headers
                if any(ph in text_lower for ph in PAGE_HEADER_PATTERNS):
                    continue
                # This is the closest section header - use it!
                closest_section_header = text
                break
        
        # If we found a close section header, use it directly
        if closest_section_header and len(closest_section_header) > 10:
            return clean_title(closest_section_header)
        
        # === APPROACH 1 (continued): Collect all candidates for scoring ===
        table_found = False
        distance = 0
        
        for item_data in reversed(items_list):
            item = item_data[0] if isinstance(item_data, tuple) else item_data
            
            if item is table_item:
                table_found = True
                distance = 0
                continue
            
            if not table_found:
                continue
            
            distance += 1
            if distance > 30:  # Extended: look at up to 30 items before (for multi-page tables)
                break
            
            item_page = DoclingHelper.get_item_page(item)
            if item_page < page_no - 3:  # Extended: allow up to 3 pages back for long tables
                continue
            
            if not hasattr(item, 'text') or not item.text:
                continue
            
            text = str(item.text).strip()
            label = str(item.label) if hasattr(item, 'label') else 'UNKNOWN'
            
            # Only add if it passes basic title validation (rejects table data like numbers, "(7) $")
            if 5 < len(text) < 120 and is_table_title_candidate(text):
                immediate_candidates.append((text, distance, label, item_page))
        
        
        # Note: PAGE_HEADER_PATTERNS is defined above in APPROACH 0
        
        # Date/time fragments from multi-page tables (NOT table titles)
        DATE_FRAGMENT_PATTERNS = [
            r'^at\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'^(three|six|nine)\s+months?\s+(ended|ending)',
            r'^year\s+ended',
            r'^(sept|oct|nov|dec|jan|feb|mar|apr|may|jun|jul|aug)\s+\d',
            r'^\d{4}$',  # Just a year like "2025"
        ]
        
        # Sentences/explanatory text that are NOT table titles
        SENTENCE_PATTERNS = [
            r'^we\s+and\s+our',  # "We and our U.S. Bank Subsidiaries..."
            r'^for\s+a\s+further',  # "For a further description..."
            r'^see\s+note\s+\d',  # "See Note 16..."
            r'^commitments\s+and\s+contingent',  # "Commitments and contingent liabilities (see Note..."
            r'^the\s+firm\s+has',  # "The Firm has additional..."
            r'^amounts\s+include',  # "Amounts include..."
            r'^includes?\s+derivative',  # "Includes derivative..."
        ]
        
        # === APPROACH 2: Evaluate candidates and pick the best ===
        best_title = None
        best_score = 0
        
        for text, distance, label, item_page in immediate_candidates:
            score = 0
            text_lower = text.lower()
            
            # FIRST: Check if this is a known table title pattern
            # Known patterns should OVERRIDE other penalties
            is_known_title = is_known_table_title(text)
            
            # PENALTY: Page headers that appear on every page
            # BUT SKIP if this is a known table title pattern
            is_page_header = any(ph in text_lower for ph in PAGE_HEADER_PATTERNS)
            if is_page_header and not is_known_title:
                score -= 200  # Strong penalty - should never be picked as title
            
            # PENALTY: Date fragments from multi-page tables
            is_date_fragment = any(re.match(p, text_lower) for p in DATE_FRAGMENT_PATTERNS)
            if is_date_fragment:
                score -= 150  # Strong penalty - not a title
            
            # PENALTY: Explanatory sentences (not table titles)
            is_sentence = any(re.match(p, text_lower) for p in SENTENCE_PATTERNS)
            if is_sentence:
                score -= 150  # Strong penalty - explanatory text, not title
            
            # Known table title pattern = HIGHEST priority (increased from +100)
            if is_known_title:
                score += 150
            
            # Same page = better than previous page
            if item_page == page_no:
                score += 50
            
            # Closer to table = MUCH better (increased weight from *5 to *15)
            # At distance 1: +135 points, at distance 12: -30 points
            score += (10 - distance) * 15
            
            # SECTION_HEADER or TITLE label = likely title
            if 'SECTION' in label.upper() or 'TITLE' in label.upper():
                score += 30
            
            # Good candidate = bonus
            if is_table_title_candidate(text):
                score += 20
            
            # Short and capitalized = likely title
            if text[0].isupper() and len(text) < 60:
                score += 10
            
            if score > best_score:
                best_score = score
                best_title = text
        
        # === Return the best title found ===
        # Only accept if score is positive (not penalized)
        if best_title and best_score >= 0:
            cleaned = clean_title(best_title)
            
            # If best title is a sub-header (short/generic), try to find a better main title
            if is_sub_header(cleaned):
                # Look for a valid MAIN title instead
                for text, distance, label, item_page in immediate_candidates:
                    if text == best_title:
                        continue
                    # Check if it's a valid main title
                    if is_valid_main_title(text):
                        # Use the main title instead (don't combine with -)
                        return clean_title(text)
                
                # If no main title found, still return sub-header 
                # (better than "Table N (Page X)")
            
            return cleaned
        
        # === FALLBACK 1: Look for nearby SECTION_HEADER items ===
        # ONLY use section headers that match known table title patterns
        # Generic section headers like "Management's Discussion and Analysis" should be skipped
        items_list = list(doc.iterate_items())
        table_found = False
        distance = 0
        
        for item_data in reversed(items_list):
            item = item_data[0] if isinstance(item_data, tuple) else item_data
            
            if item is table_item:
                table_found = True
                distance = 0
                continue
            
            if not table_found:
                continue
            
            distance += 1
            if distance > 50:  # Search up to 50 items back
                break
            
            # Check for SECTION_HEADER label
            if hasattr(item, 'label'):
                label = str(item.label.value) if hasattr(item.label, 'value') else str(item.label)
                if 'SECTION' in label.upper() and hasattr(item, 'text') and item.text:
                    text = item.text.strip()
                    # Skip page headers (generic repeated headers)
                    if any(ph in text.lower() for ph in PAGE_HEADER_PATTERNS):
                        continue
                    # ONLY accept as title if it matches a KNOWN table title pattern
                    # This prevents generic section headers from becoming table titles
                    if is_known_table_title(text) and is_table_title_candidate(text):
                        return clean_title(text)
        
        # === FALLBACK 2: Use section name from TOC hierarchy ===
        section_name = DoclingHelper.extract_section_name(doc, table_item, page_no)
        if section_name and len(section_name) > 10:
            return section_name
        
        # === Final FALLBACK: Use the original method ===
        return DoclingHelper.extract_table_title(doc, table_item, table_index, page_no)
    
    @staticmethod
    def extract_table_metadata(doc, table_item, table_index: int, page_no: int) -> dict:
        """
        Extract structured table metadata with section, title, and optional subtitle.
        
        Returns:
            Dict with:
            - table_section: The section/chapter from TOC hierarchy
            - table_title: The main table title
            - table_subtitle: Optional short qualifier (e.g., "By Region", "At September 30")
        """
        # Get section from TOC hierarchy
        table_section = DoclingHelper.extract_section_name(doc, table_item, page_no)
        
        # Get main title using hybrid extraction
        table_title = DoclingHelper.extract_table_title_hybrid(doc, table_item, table_index, page_no)
        
        # Check if the title is actually a subtitle pattern (short qualifier)
        # These are ONLY short qualifiers that modify a parent title, NOT main titles
        SUBTITLE_PATTERNS = [
            r'^by\s+(region|property|type|industry|product|segment)',  # "By Region", "By Type"
            r'^(americas|emea|asia)$',  # Geographic qualifiers (not "Total")
            r'^time deposit maturities$',  # Specific sub-table
            r'^(non-consolidated|consolidated)\s+vies?$',
        ]
        
        table_subtitle = None
        title_lower = table_title.lower().strip() if table_title else ''
        
        # Check if the "title" is actually a subtitle pattern
        is_subtitle = len(title_lower) < 30 and any(
            re.match(p, title_lower) for p in SUBTITLE_PATTERNS
        )
        
        if is_subtitle:
            # The current "title" is actually a subtitle
            table_subtitle = table_title
            # Try to get the real title from section or look further back
            # For now, use section as the title if available, otherwise use a generic name
            if table_section and len(table_section) > 15:
                table_title = table_section
                table_section = ''  # Don't duplicate
            else:
                # Keep the subtitle as title if we can't find better
                table_subtitle = None
        
        return {
            'table_section': table_section or '',
            'table_title': table_title or f'Table {table_index + 1} (Page {page_no})',
            'table_subtitle': table_subtitle,  # None if not applicable
        }
    
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

        def is_footnote(text: str) -> bool:
            """Check if text looks like a footnote or explanatory text."""
            text_lower = text.lower().strip()
            
            # Footnote patterns to filter out
            footnote_patterns = [
                'see note', 'refer to note', 'as described in note',
                'see page', 'refer to page', 'continued on',
                'continued from', 'see accompanying', 'refer to accompanying',
                'see the accompanying', 'as discussed', 'as described',
                '(1)', '(2)', '(3)', '(a)', '(b)', '(c)',  # Numbered refs
                'note:', 'notes:', 'source:', 'sources:',
                'are held', 'is held', 'are primarily', 'is primarily',
                'includes', 'excludes', 'represents', 'consists of',
                'based on', 'pursuant to', 'subject to', 'related to',
                'effective', 'applicable', 'accordance with',
                'can be set', 'is currently set', 'has been set',
                'is currently', 'has been', 'was set', 'were set',
                'is set by', 'are set by', 'determined by',
            ]
            
            for pattern in footnote_patterns:
                if pattern in text_lower:
                    return True
            
            # Check if starts with superscript-like patterns (1, 2, *, etc.)
            if text and text[0] in '0123456789*†‡§#':
                return True
            
            # Very short text starting with parens is likely footnote
            if len(text) < 30 and text.startswith('('):
                return True
            
            # Text starting with "Our", "The", "This", "These" followed by descriptive text is usually footnote
            sentence_starters = ['our ', 'the ', 'this ', 'these ', 'such ', 'certain ']
            for starter in sentence_starters:
                if text_lower.startswith(starter) and len(text) > 40:
                    return True
            
            # Text with multiple periods (sentences) is likely explanatory text, not a title
            if text.count('.') >= 2:
                return True
            
            # Text ending with period is often explanatory, unless it's short
            if text.endswith('.') and len(text) > 50:
                return True
            
            return False

        def is_section_header(text: str) -> bool:
            """Check if text looks like a section header (not a table title)."""
            text_lower = text.lower().strip()
            
            # Section header patterns (broad categories, not specific table titles)
            section_patterns = [
                'institutional securities', 'wealth management', 
                'investment management', 'corporate', 'other',
                'risk management', 'credit risk', 'market risk',
                'liquidity', 'capital', 'regulatory', 'supervision',
                'part i', 'part ii', 'part iii', 'item 1', 'item 2',
            ]
            
            for pattern in section_patterns:
                if text_lower == pattern or text_lower.startswith(f"{pattern} "):
                    return True
            
            # Single word all caps is likely section header
            if text.isupper() and len(text.split()) <= 2 and len(text) < 30:
                return True
            
            return False

        def is_valid_title(text: str) -> bool:
            text_lower = text.lower().strip()
            
            if len(text) < 5 or len(text) > 120:
                return False
            
            if text.startswith('('):
                return False
            
            if text[0].islower():
                return False
            
            # Filter out footnotes
            if is_footnote(text):
                return False
            
            # Check if this matches a known table title pattern from config
            # If so, it's a valid title even if it matches invalid_patterns
            try:
                import json
                config_path = Path(__file__).parent.parent.parent.parent.parent / 'config' / 'section_patterns.json'
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                table_title_data = config.get('table_title_patterns', {})
                table_title_patterns = table_title_data.get('patterns', []) if isinstance(table_title_data, dict) else table_title_data
                
                for pattern in table_title_patterns:
                    if pattern.lower() in text_lower:
                        return True  # Known table title - accept it
            except Exception:
                pass  # Continue with other checks
            
            invalid_patterns = [
                'three months ended', 'six months ended', 'nine months ended',
                'year ended', 'quarter ended', 'at march', 'at december',
                'at september', 'at june', 'at january', 'at february',
                '$ in millions', '$ in billions', 'in millions', 'in billions',
                'unaudited', 'address of principal', 'the following', 'as follows',
                'morgan stanley', 'consolidated statements', 'condensed consolidated',
                "management's discussion and analysis",
                'notes to consolidated financial statements',
                'risk disclosures', 'trading risks',
                'securities registered pursuant', '(registrant)',
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
            section_headers = []  # Track section headers separately
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                if item is table_item:
                    break
                
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                # Look at current page and previous page (for continued tables)
                if item_page >= page_no - 1:
                    label = str(item.label) if hasattr(item, 'label') else ''
                    
                    if 'SECTION' in label.upper() or 'TITLE' in label.upper() or 'TEXT' in label.upper():
                        if hasattr(item, 'text') and item.text:
                            text = str(item.text).strip()
                            if 5 < len(text) < 150 and not text.startswith('|'):
                                # Categorize as section header or potential title
                                if is_section_header(text):
                                    section_headers.append((text, item_page))
                                else:
                                    preceding_texts.append((text, item_page))
            
            # First, try to find valid title from preceding texts (prefer same page)
            if preceding_texts:
                # Sort by page (current page first), then by position (last first)
                same_page = [(t, p) for t, p in preceding_texts if p == page_no]
                prev_page = [(t, p) for t, p in preceding_texts if p == page_no - 1]
                
                # Try same page first
                for text, _ in reversed(same_page):
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
                
                # Try previous page (for continued tables)
                for text, _ in reversed(prev_page):
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
                            # Mark as continued if from previous page
                            return clean_title(title)
            
            # Fallback: use section header only if no better title found
            # (This handles the case where section header is the best we have)
            if section_headers:
                # Prefer current page section header
                for text, p in reversed(section_headers):
                    if p == page_no and is_valid_title(text):
                        return clean_title(text)
                        
        except Exception as e:
            logger.debug(f"Error extracting table title: {e}")
        
        return f"Table {table_index + 1} (Page {page_no})"
