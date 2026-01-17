"""
Excel to CSV Exporter.

Main orchestrator class for migrating Excel workbooks to CSV format.
Follows the Manager pattern used throughout the codebase.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import re

import pandas as pd

from src.utils import get_logger
from src.core import get_paths
from .constants import (
    CSVExportSettings,
    TableDetectionPatterns,
    ExportStatus,
)
from .metadata_extractor import SheetMetadataExtractor, TableBlock
from .index_builder import EnhancedIndexBuilder
from .csv_writer import CSVWriter
from .category_separator import CategorySeparator
from .data_formatter import DataFormatter
from .metadata_injector import MetadataInjector
from .data_normalizer import DataNormalizer

logger = get_logger(__name__)


@dataclass
class WorkbookExportResult:
    """Result of exporting a single workbook."""
    
    workbook_name: str
    status: ExportStatus = ExportStatus.SUCCESS
    
    # Counts
    sheets_processed: int = 0
    tables_exported: int = 0
    csv_files_created: int = 0
    
    # Output paths
    output_dir: str = ""
    index_file: str = ""
    csv_files: List[str] = field(default_factory=list)
    
    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return self.status in (ExportStatus.SUCCESS, ExportStatus.PARTIAL_SUCCESS)


@dataclass
class ExportSummary:
    """Summary of full export operation."""
    
    workbooks_processed: int = 0
    total_sheets: int = 0
    total_tables: int = 0
    total_csv_files: int = 0
    
    results: Dict[str, WorkbookExportResult] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return all(r.success for r in self.results.values()) if self.results else False


class ExcelToCSVExporter:
    """
    Main exporter class - orchestrates Excel to CSV migration.
    
    Following Google's "Manager" pattern used in:
    - VectorDBManager
    - PipelineManager
    - SearchOrchestrator
    
    Usage:
        exporter = get_csv_exporter()
        result = exporter.export_workbook(xlsx_path, output_dir)
        # or
        summary = exporter.export_all(source_dir, output_base)
    """
    
    def __init__(
        self,
        source_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        enable_category_separation: bool = True,
        enable_data_formatting: bool = True,
        enable_metadata_injection: bool = True,
        enable_data_normalization: bool = False
    ):
        """
        Initialize exporter.
        
        Args:
            source_dir: Source directory containing xlsx files
            output_dir: Base output directory for CSV files
            enable_category_separation: Enable category separation feature
            enable_data_formatting: Enable data formatting feature (currency & percentage)
            enable_metadata_injection: Enable metadata injection feature (Source, Section, Table Title)
            enable_data_normalization: Enable data normalization feature (wide to long format)
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        paths = get_paths()
        self.source_dir = source_dir or Path(paths.data_dir) / "processed"
        self.output_dir = output_dir or Path(paths.data_dir) / "csv_output"
        self.enable_category_separation = enable_category_separation
        self.enable_data_formatting = enable_data_formatting
        self.enable_metadata_injection = enable_metadata_injection
        self.enable_data_normalization = enable_data_normalization
        
        # Components
        self.metadata_extractor = SheetMetadataExtractor()
        self.index_builder = EnhancedIndexBuilder()
        self.csv_writer = CSVWriter()
        self.category_separator = CategorySeparator() if enable_category_separation else None
        self.data_formatter = DataFormatter() if enable_data_formatting else None
        self.metadata_injector = MetadataInjector() if enable_metadata_injection else None
        self.data_normalizer = DataNormalizer() if enable_data_normalization else None
    
    def export_all(
        self,
        source_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ) -> ExportSummary:
        """
        Export all workbooks in source directory.
        
        Args:
            source_dir: Override source directory
            output_dir: Override output base directory
            
        Returns:
            ExportSummary with results for all workbooks
        """
        source = source_dir or self.source_dir
        output_base = output_dir or self.output_dir
        
        # Find xlsx files
        xlsx_files = list(source.glob("*_tables.xlsx"))
        
        if not xlsx_files:
            self.logger.warning(f"No xlsx files found in {source}")
            return ExportSummary(errors=[f"No xlsx files found in {source}"])
        
        self.logger.info(f"Found {len(xlsx_files)} workbooks to export")
        
        summary = ExportSummary()
        
        for xlsx_path in xlsx_files:
            # Create output directory per workbook
            # e.g., 10q0925_tables.xlsx -> csv_output/10q0925/
            workbook_name = xlsx_path.stem.replace('_tables', '')
            workbook_output_dir = output_base / workbook_name
            
            result = self.export_workbook(xlsx_path, workbook_output_dir)
            
            summary.results[workbook_name] = result
            summary.workbooks_processed += 1
            summary.total_sheets += result.sheets_processed
            summary.total_tables += result.tables_exported
            summary.total_csv_files += result.csv_files_created
            
            if result.errors:
                summary.errors.extend(result.errors)
        
        self.logger.info(
            f"Export complete: {summary.workbooks_processed} workbooks, "
            f"{summary.total_tables} tables, {summary.total_csv_files} CSV files"
        )
        
        return summary
    
    def export_workbook(
        self,
        xlsx_path: Path,
        output_dir: Path
    ) -> WorkbookExportResult:
        """
        Export a single Excel workbook to CSV files.
        
        Creates:
        - output_dir/Index.csv
        - output_dir/1.csv, 2.csv, ... (for single-table sheets)
        - output_dir/3_table_1.csv, 3_table_2.csv (for multi-table sheets)
        
        Args:
            xlsx_path: Path to Excel workbook
            output_dir: Output directory for CSV files
            
        Returns:
            WorkbookExportResult with export details
        """
        workbook_name = xlsx_path.stem
        result = WorkbookExportResult(
            workbook_name=workbook_name,
            output_dir=str(output_dir)
        )
        
        self.logger.info(f"Exporting workbook: {xlsx_path.name}")
        
        try:
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Load workbook
            xlsx = pd.ExcelFile(xlsx_path)
            sheet_names = xlsx.sheet_names
            
            # Separate Index and table sheets
            index_df = None
            index_metadata_map: Dict[str, List[dict]] = {}
            table_metadata: Dict[str, List[TableBlock]] = {}
            csv_file_mapping: Dict[str, List[str]] = {}
            
            # Load Index sheet first to build metadata map
            if 'Index' in sheet_names:
                index_df = pd.read_excel(xlsx, sheet_name='Index')
                if self.enable_metadata_injection:
                    index_metadata_map = self._build_index_metadata_map(index_df)
                    self.logger.debug(f"Built metadata map for {len(index_metadata_map)} sheets")
            
            for sheet_name in sheet_names:
                if sheet_name in TableDetectionPatterns.SKIP_SHEETS:
                    continue
                
                # Process table sheet
                sheet_result = self._process_sheet(
                    xlsx=xlsx,
                    sheet_name=sheet_name,
                    output_dir=output_dir,
                    index_metadata=index_metadata_map.get(sheet_name, [])
                )
                
                if sheet_result:
                    tables, csv_files = sheet_result
                    table_metadata[sheet_name] = tables
                    csv_file_mapping[sheet_name] = csv_files
                    
                    result.sheets_processed += 1
                    result.tables_exported += len(tables)
                    result.csv_files_created += len(csv_files)
                    result.csv_files.extend(csv_files)
            
            # Build and write enhanced Index
            if index_df is not None:
                enhanced_index = self.index_builder.build_enhanced_index(
                    original_index=index_df,
                    table_metadata=table_metadata,
                    csv_file_mapping=csv_file_mapping
                )
                
                index_path = output_dir / CSVExportSettings.INDEX_FILENAME
                if self.csv_writer.write_index_csv(enhanced_index, index_path):
                    result.index_file = str(index_path)
                    result.csv_files_created += 1
                else:
                    result.errors.append(f"Failed to write Index CSV")
            else:
                result.warnings.append("No Index sheet found in workbook")
            
            # Determine final status
            if result.errors:
                result.status = ExportStatus.PARTIAL_SUCCESS if result.csv_files_created > 0 else ExportStatus.FAILED
            else:
                result.status = ExportStatus.SUCCESS
            
            self.logger.info(
                f"Exported {workbook_name}: {result.sheets_processed} sheets, "
                f"{result.tables_exported} tables, {result.csv_files_created} CSV files"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to export workbook {xlsx_path}: {e}", exc_info=True)
            result.status = ExportStatus.FAILED
            result.errors.append(str(e))
        
        return result
    
    def _build_index_metadata_map(self, index_df: pd.DataFrame) -> Dict[str, List[dict]]:
        """
        Build mapping from sheet_name to list of table metadata from Index sheet.
        
        Uses the Link column to determine which sheet each table belongs to.
        For multi-table sheets, orders metadata by row appearance.
        
        Args:
            index_df: Index DataFrame (from original Index sheet)
            
        Returns:
            Dict mapping sheet_name to list of metadata dicts.
            Each metadata dict contains: Section, Table Title, Source, PageNo
        """
        metadata_map: Dict[str, List[dict]] = {}
        
        for _, row in index_df.iterrows():
            # Get Link column which tells us the sheet
            # Examples: '→ 1', '→ 2', '→ 147'
            link = str(row.get('Link', '')).strip()
            if not link:
                continue
            
            # Parse sheet number from link
            # Pattern: '→ 147' -> sheet_name='147'
            sheet_match = re.search(r'→\s*(\d+)', link)
            if not sheet_match:
                continue
            
            sheet_name = sheet_match.group(1)
            
            # Build metadata dict for this table
            table_meta = {
                'Section': str(row.get('Section', '')).strip(),
                'Table Title': str(row.get('Table Title', '')).strip(),
                'Source': str(row.get('Source', '')).strip(),
                'PageNo': str(row.get('PageNo', '')).strip(),
            }
            
            # Add to map
            if sheet_name not in metadata_map:
                metadata_map[sheet_name] = []
            metadata_map[sheet_name].append(table_meta)
        
        # Assign Table_Index based on order within each sheet
        for sheet_name, tables in metadata_map.items():
            for idx, table_meta in enumerate(tables, start=1):
                table_meta['Table_Index'] = idx
        
        return metadata_map
    
    def _process_sheet(
        self,
        xlsx: pd.ExcelFile,
        sheet_name: str,
        output_dir: Path,
        index_metadata: List[dict] = None
    ) -> Optional[Tuple[List[TableBlock], List[str]]]:
        """
        Process a single table sheet.
        
        Args:
            xlsx: Excel file object
            sheet_name: Name of the sheet to process
            output_dir: Output directory for CSV files
            index_metadata: List of metadata dicts for tables in this sheet
        
        Returns:
            Tuple of (List[TableBlock], List[csv_filenames]) or None on error
        """
        if index_metadata is None:
            index_metadata = []
        
        try:
            # Load sheet without header (to preserve all rows)
            sheet_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
            
            # Extract tables
            tables = self.metadata_extractor.extract_all_tables(
                sheet_df=sheet_df,
                sheet_name=sheet_name
            )
            
            if not tables:
                self.logger.debug(f"No tables found in sheet '{sheet_name}'")
                return None
            
            # Export each table to CSV
            csv_files = []
            
            for table in tables:
                if table.data_df is None or table.data_df.empty:
                    continue
                
                # Apply category separation if enabled
                df_to_write = table.data_df
                has_categories = False
                
                if self.category_separator:
                    categorized_df, categories_found = self.category_separator.separate_categories(table.data_df)
                    
                    if not categorized_df.empty:
                        df_to_write = categorized_df
                        has_categories = True
                        
                        # Update table metadata with categories
                        if categories_found:
                            category_str = ", ".join(categories_found)
                            table.metadata['Category_Parent'] = category_str
                            self.logger.debug(
                                f"Sheet {sheet_name} table {table.table_index}: "
                                f"Found {len(categories_found)} categories"
                            )
                
                # Apply data formatting if enabled
                if self.data_formatter:
                    # Get table header from first column name or metadata
                    table_header = None
                    if not df_to_write.empty and len(df_to_write.columns) > 0:
                        # Try to get from metadata first
                        table_header = table.metadata.get('first_column_header')
                        # Fallback to first column name
                        if not table_header:
                            table_header = str(df_to_write.columns[0])
                    
                    df_to_write = self.data_formatter.format_table(
                        df_to_write, 
                        table_header=table_header
                    )
                    
                    self.logger.debug(
                        f"Sheet {sheet_name} table {table.table_index}: "
                        f"Applied data formatting"
                    )
                
                # Inject metadata columns if enabled
                if self.metadata_injector:
                    # Find metadata for this specific table
                    table_meta = None
                    for meta in index_metadata:
                        if meta.get('Table_Index') == table.table_index:
                            table_meta = meta
                            break
                    
                    # Extract metadata fields
                    section = ""
                    table_title = ""
                    source = ""
                    
                    if table_meta:
                        section = table_meta.get('Section', '')
                        table_title = table_meta.get('Table Title', '')
                        
                        # Construct Source from Source + PageNo
                        source_pdf = table_meta.get('Source', '')
                        page_no = table_meta.get('PageNo', '')
                        if source_pdf and page_no:
                            source = f"{source_pdf}_pg{page_no}"
                    
                    # Log warning if metadata is incomplete
                    if not section or not table_title or not source:
                        self.logger.warning(
                            f"Incomplete metadata for sheet {sheet_name} table {table.table_index}: "
                            f"section={section!r}, table_title={table_title!r}, source={source!r}"
                        )
                    
                    # Inject columns
                    df_to_write = self.metadata_injector.inject_metadata_columns(
                        df_to_write,
                        source=source or '',
                        section=section or '',
                        table_title=table_title or ''
                    )
                    
                    self.logger.debug(
                        f"Sheet {sheet_name} table {table.table_index}: "
                        f"Injected metadata columns"
                    )
                
                # Apply data normalization if enabled (must be last step)
                if self.data_normalizer:
                    df_to_write = self.data_normalizer.normalize_table(df_to_write)
                    
                    self.logger.debug(
                        f"Sheet {sheet_name} table {table.table_index}: "
                        f"Applied data normalization (wide to long format)"
                    )
                
                # Determine filename
                if len(tables) == 1:
                    filename = CSVExportSettings.TABLE_FILENAME_PATTERN.format(
                        sheet_id=sheet_name
                    )
                else:
                    filename = CSVExportSettings.MULTI_TABLE_FILENAME_PATTERN.format(
                        sheet_id=sheet_name,
                        table_index=table.table_index
                    )
                
                csv_path = output_dir / filename
                
                # Include headers if category separation or metadata injection was applied
                include_header = has_categories or (self.metadata_injector is not None)
                
                if self.csv_writer.write_table_csv(df_to_write, csv_path, include_header=include_header):
                    csv_files.append(filename)
                else:
                    self.logger.warning(f"Failed to write {csv_path}")

            
            return (tables, csv_files)
            
        except Exception as e:
            self.logger.error(f"Error processing sheet '{sheet_name}': {e}")
            return None


def get_csv_exporter(
    source_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    enable_category_separation: bool = True,
    enable_data_formatting: bool = True,
    enable_metadata_injection: bool = True,
    enable_data_normalization: bool = False
) -> ExcelToCSVExporter:
    """
    Factory function for ExcelToCSVExporter.
    
    Args:
        source_dir: Optional source directory override
        output_dir: Optional output directory override
        enable_category_separation: Enable category separation feature
        enable_data_formatting: Enable data formatting feature (currency & percentage)
        enable_metadata_injection: Enable metadata injection feature (Source, Section, Table Title)
        enable_data_normalization: Enable data normalization feature (wide to long format)
        
    Returns:
        Configured ExcelToCSVExporter instance
    """
    return ExcelToCSVExporter(
        source_dir=source_dir, 
        output_dir=output_dir,
        enable_category_separation=enable_category_separation,
        enable_data_formatting=enable_data_formatting,
        enable_metadata_injection=enable_metadata_injection,
        enable_data_normalization=enable_data_normalization
    )
