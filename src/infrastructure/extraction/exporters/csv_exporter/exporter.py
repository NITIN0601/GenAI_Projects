"""
Excel to CSV Exporter.

Main orchestrator class for migrating Excel workbooks to CSV format.
Follows the Manager pattern used throughout the codebase.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

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
        output_dir: Optional[Path] = None
    ):
        """
        Initialize exporter.
        
        Args:
            source_dir: Source directory containing xlsx files
            output_dir: Base output directory for CSV files
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        paths = get_paths()
        self.source_dir = source_dir or Path(paths.data_dir) / "processed"
        self.output_dir = output_dir or Path(paths.data_dir) / "csv_output"
        
        # Components
        self.metadata_extractor = SheetMetadataExtractor()
        self.index_builder = EnhancedIndexBuilder()
        self.csv_writer = CSVWriter()
    
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
            table_metadata: Dict[str, List[TableBlock]] = {}
            csv_file_mapping: Dict[str, List[str]] = {}
            
            for sheet_name in sheet_names:
                if sheet_name in TableDetectionPatterns.SKIP_SHEETS:
                    if sheet_name == 'Index':
                        index_df = pd.read_excel(xlsx, sheet_name=sheet_name)
                    continue
                
                # Process table sheet
                sheet_result = self._process_sheet(
                    xlsx=xlsx,
                    sheet_name=sheet_name,
                    output_dir=output_dir
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
    
    def _process_sheet(
        self,
        xlsx: pd.ExcelFile,
        sheet_name: str,
        output_dir: Path
    ) -> Optional[tuple]:
        """
        Process a single table sheet.
        
        Returns:
            Tuple of (List[TableBlock], List[csv_filenames]) or None on error
        """
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
                
                if self.csv_writer.write_table_csv(table.data_df, csv_path):
                    csv_files.append(filename)
                else:
                    self.logger.warning(f"Failed to write {csv_path}")
            
            return (tables, csv_files)
            
        except Exception as e:
            self.logger.error(f"Error processing sheet '{sheet_name}': {e}")
            return None


def get_csv_exporter(
    source_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> ExcelToCSVExporter:
    """
    Factory function for ExcelToCSVExporter.
    
    Args:
        source_dir: Optional source directory override
        output_dir: Optional output directory override
        
    Returns:
        Configured ExcelToCSVExporter instance
    """
    return ExcelToCSVExporter(source_dir=source_dir, output_dir=output_dir)
