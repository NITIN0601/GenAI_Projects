"""
TOC Builder - Create Table of Contents and Index sheets for Excel exports.

Standalone module for building navigation sheets in Excel workbooks.
Used by: excel_exporter.py, consolidated_exporter.py
"""

import re
import pandas as pd
from typing import List, Dict, Any

from src.utils import get_logger
from src.utils.excel_utils import ExcelUtils
from src.infrastructure.extraction.helpers.docling_helper import SectionHierarchyTracker

logger = get_logger(__name__)


class TOCBuilder:
    """
    Build Table of Contents and Index sheets for Excel exports.
    
    Handles:
    - TOC with hierarchical section columns
    - Index with comprehensive table metadata
    - Column width auto-adjustment
    """
    
    @classmethod
    def create_toc_sheet(
        cls,
        writer: pd.ExcelWriter,
        tables: List[Dict[str, Any]],
        clean_title_func=None,
        normalize_title_func=None,
        get_column_letter_func=None
    ) -> None:
        """
        Create TOC sheet with hierarchical section columns.
        
        Columns: Table of Contents | Main Section | Section1 | Section2 | Section3 | Section4 | Table Title | Page | Sheet
        
        Uses SectionHierarchyTracker for pattern-based classification of sections.
        """
        # Initialize tracker with config-based patterns
        tracker = SectionHierarchyTracker()
        
        toc_data = []
        
        # Track tables per page to generate sheet names
        logical_table_ids = {}
        next_table_id = 1
        
        # First pass: collect all section names for pre-scan
        all_sections = []
        for table in tables:
            metadata = table.get('metadata', {})
            section_str = metadata.get('section_name', '')
            page_no = metadata.get('page_no', 1)
            if section_str:
                all_sections.append((page_no, section_str))
        
        # Pre-scan to identify repeating headers (MAIN sections)
        tracker.pre_scan_headers(all_sections)
        
        # Second pass: process each table
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            section_str = metadata.get('section_name', '')
            page_no = metadata.get('page_no', 'N/A')
            
            # Generate table_id for sheet link
            cleaned_title = clean_title_func(title) if clean_title_func else title
            normalized_title = normalize_title_func(cleaned_title) if normalize_title_func else cleaned_title.lower()
            
            section_fixed = ExcelUtils.fix_ocr_broken_words(section_str) if section_str else ''
            section_normalized = re.sub(r'\s+', ' ', section_fixed).strip().lower() if section_fixed else ''
            if section_normalized:
                grouping_key = f"{section_normalized}::{normalized_title}"
            else:
                grouping_key = f"default::{normalized_title}"
            
            if grouping_key not in logical_table_ids:
                logical_table_ids[grouping_key] = str(next_table_id)
                next_table_id += 1
            
            table_id = logical_table_ids[grouping_key]
            
            # Use tracker to process section and get hierarchy
            if section_str:
                hierarchy = tracker.process_header(section_str.strip(), page_no if isinstance(page_no, int) else 1)
            else:
                hierarchy = tracker.get_current_hierarchy()
            
            # Clean title
            title_clean = ExcelUtils.fix_ocr_broken_words(str(title)) if title else ''
            title_clean = re.sub(r'\s+', ' ', title_clean).strip()
            
            # Clean section directly from metadata (not re-classified)
            section_clean = ExcelUtils.fix_ocr_broken_words(section_str) if section_str else ''
            section_clean = re.sub(r'\s+', ' ', section_clean).strip() if section_clean else '-'
            
            toc_data.append({
                'Page': page_no,
                'Section': section_clean,  # ACTUAL section from metadata
                'Table Title': title_clean,
                'Table of Contents': hierarchy.get('toc', '') or '-',
                'Main Section': hierarchy.get('main', '') or '-',
                'Section1': hierarchy.get('section1', '') or '-',
                'Section2': hierarchy.get('section2', '') or '-',
                'Section3': hierarchy.get('section3', '') or '-',
                'Section4': hierarchy.get('section4', '') or '-',
                'Sheet': table_id
            })
        
        # Create DataFrame and write to sheet
        df = pd.DataFrame(toc_data)
        
        # Sort by page number (ascending) as primary sort
        df = df.sort_values(
            by=['Page', 'Section', 'Table Title'],
            key=lambda x: pd.to_numeric(x, errors='coerce') if x.name == 'Page' else x.astype(str).str.lower().fillna('')
        )
        
        df.to_excel(writer, sheet_name='TOC', index=False)
        
        # Auto-adjust column widths
        get_col_letter = get_column_letter_func or ExcelUtils.get_column_letter
        worksheet = writer.sheets['TOC']
        for idx, col in enumerate(df.columns):
            col_letter = get_col_letter(idx)
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            calculated_len = max(max_content_len, header_len) + 2
            max_len = min(calculated_len, 50)
            worksheet.column_dimensions[col_letter].width = max_len
    
    @classmethod
    def create_index_sheet(
        cls,
        writer: pd.ExcelWriter,
        tables: List[Dict[str, Any]],
        tables_by_title: Dict[str, List[Dict[str, Any]]],
        clean_title_func=None,
        normalize_title_func=None,
        get_column_letter_func=None
    ) -> None:
        """
        Create Index sheet with comprehensive table metadata.
        
        Columns: Source, PageNo, Table_ID, Location_ID, Section, Table Title, Link
        
        Location_ID = <pageNo>_<Table_IndexID_perpage>
        Section is included to show why tables with same title might be separate.
        """
        index_data = []
        
        # Track tables per page to generate Location_ID
        page_table_counts = {}
        
        # Track unique logical tables to assign Table_ID (Section + Title)
        logical_table_ids = {}
        next_table_id = 1
        
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            section = metadata.get('section_name', '')
            
            # Clean title to identify logical table
            cleaned_title = clean_title_func(title) if clean_title_func else title
            normalized_title = normalize_title_func(cleaned_title) if normalize_title_func else cleaned_title.lower()
            
            # Create grouping key: Section + Title
            section_fixed = ExcelUtils.fix_ocr_broken_words(section) if section else ''
            section_normalized = re.sub(r'\s+', ' ', section_fixed).strip().lower() if section_fixed else ''
            if section_normalized:
                grouping_key = f"{section_normalized}::{normalized_title}"
            else:
                grouping_key = f"default::{normalized_title}"
            
            # Assign Table_ID based on unique Section + Title combination
            if grouping_key not in logical_table_ids:
                logical_table_ids[grouping_key] = str(next_table_id)
                next_table_id += 1
            
            table_id = logical_table_ids[grouping_key]
            
            # Get page number
            page_no = metadata.get('page_no', 'N/A')
            
            # Generate Location_ID
            if page_no != 'N/A':
                if page_no not in page_table_counts:
                    page_table_counts[page_no] = 0
                page_table_counts[page_no] += 1
                location_id = f"{page_no}_{page_table_counts[page_no]}"
            else:
                location_id = ''
            
            # Clean section
            section_clean = ExcelUtils.fix_ocr_broken_words(section) if section else ''
            section_clean = re.sub(r'\s+', ' ', section_clean).strip() if section_clean else ''
            
            index_data.append({
                'Source': metadata.get('source_doc', 'Unknown'),
                'PageNo': page_no,
                'Table_ID': table_id,
                'Location_ID': location_id,
                'Section': section_clean,
                'Table Title': title,
                'Link': table_id
            })
        
        df = pd.DataFrame(index_data)
        
        # Ensure columns in correct order
        REQUIRED_COLUMNS = ['Source', 'PageNo', 'Table_ID', 'Location_ID', 'Section', 'Table Title', 'Link']
        cols_to_keep = [c for c in REQUIRED_COLUMNS if c in df.columns]
        if cols_to_keep:
            df = df[cols_to_keep]
        
        df.to_excel(writer, sheet_name='Index', index=False)
        
        # Auto-adjust column widths
        get_col_letter = get_column_letter_func or ExcelUtils.get_column_letter
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            col_letter = get_col_letter(idx)
            
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            max_len = max(max_content_len, header_len) + 2
            
            # Apply reasonable limits based on column type
            if col == 'Table Title':
                max_len = min(max_len, 60)
            elif col == 'Section':
                max_len = min(max_len, 25)
            elif col in ['Source', 'Table_ID', 'Location_ID']:
                max_len = min(max_len, 25)
            elif col == 'PageNo':
                max_len = min(max_len, 10)
            elif col == 'Link':
                max_len = min(max_len, 15)
            else:
                max_len = min(max_len, 20)
            
            worksheet.column_dimensions[col_letter].width = max_len
