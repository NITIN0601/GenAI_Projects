# Project Code Files Reference

This document provides a consolidated list of all code files referenced in the project documentation.

## 1. Core Implementation & Pipeline

| File Name | File Path |
| :--- | :--- |
| `orchestrate_pipeline.py` | `src/pipeline/orchestrate_pipeline.py` |
| `merge_csv_pipeline.py` | `src/pipeline/merge_csv_pipeline.py` |
| `index_sheet_resequencer.py` | `src/index_sheet_resequencer.py` |
| `run_table_view.py` | `src/table_view/run_table_view.py` |
| `master_table_index_generator.py` | `src/table_view/master_table_index_generator.py` |
| `table_view_generator.py` | `src/table_view/table_view_generator.py` |

## 2. CSV Extraction Infrastructure

| File Name | File Path |
| :--- | :--- |
| `exporter.py` | `src/infrastructure/extraction/exporters/csv_exporter/exporter.py` |
| `category_separator.py` | `src/infrastructure/extraction/exporters/csv_exporter/category_separator.py` |
| `metadata_injector.py` | `src/infrastructure/extraction/exporters/csv_exporter/metadata_injector.py` |
| `data_formatter.py` | `src/infrastructure/extraction/exporters/csv_exporter/data_formatter.py` |
| `data_normalizer.py` | `src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py` |
| `metadata_extractor.py` | `src/infrastructure/extraction/exporters/csv_exporter/metadata_extractor.py` |
| `index_builder.py` | `src/infrastructure/extraction/exporters/csv_exporter/index_builder.py` |
| `csv_writer.py` | `src/infrastructure/extraction/exporters/csv_exporter/csv_writer.py` |
| `constants.py` | `src/infrastructure/extraction/exporters/csv_exporter/constants.py` |
| `__init__.py` | `src/infrastructure/extraction/exporters/csv_exporter/__init__.py` |
| `run_csv_export.py` | `src/infrastructure/extraction/exporters/run_csv_export.py` |

## 3. Shared Utilities

| File Name | File Path |
| :--- | :--- |
| `table_merger.py` | `src/infrastructure/extraction/exporters/table_merger.py` |
| `block_detection.py` | `src/infrastructure/extraction/exporters/block_detection.py` |
| `index_manager.py` | `src/infrastructure/extraction/exporters/index_manager.py` |
| `base_exporter.py` | `src/infrastructure/extraction/exporters/base_exporter.py` |
| `excel_exporter.py` | `src/infrastructure/extraction/exporters/excel_exporter.py` |
| `report_exporter.py` | `src/infrastructure/extraction/exporters/report_exporter.py` |
| `toc_builder.py` | `src/infrastructure/extraction/exporters/toc_builder.py` |

## 4. Scripts

| File Name | File Path |
| :--- | :--- |
| `test_index_resequencer.py` | `scripts/test_index_resequencer.py` |
| `normalize_csv_data.py` | `scripts/normalize_csv_data.py` |
| `export_with_normalization.py` | `scripts/export_with_normalization.py` |
| `verify_vertical_merge.py` | `scripts/verify_vertical_merge.py` |
| `diagnose_splits.py` | `scripts/diagnose_splits.py` |
| `inspect_page_extraction.py` | `scripts/inspect_page_extraction.py` |
| `test_title_extraction.py` | `scripts/test_title_extraction.py` |
| `download_documents.py` | `scripts/download_documents.py` |
| `migrate_vectordb.py` | `scripts/migrate_vectordb.py` |
| `audit_imports.py` | `scripts/audit_imports.py` |
| `verify_imports.py` | `scripts/verify_imports.py` |

## 5. Tests

| File Name | File Path |
| :--- | :--- |
| `test_category_separator.py` | `tests/unit/test_category_separator.py` |
| `test_metadata_injector.py` | `tests/unit/test_metadata_injector.py` |
| `test_data_normalizer.py` | `tests/test_data_normalizer.py` |
| `test_formatter.py` | `tests/unit/test_formatter.py` |
| `test_enhanced_formatter.py` | `tests/unit/test_enhanced_formatter.py` |
| `test_data_formatter.py` | `tests/unit/test_data_formatter.py` |
| `test_table_merger.py` | `tests/unit/test_table_merger.py` |
| `test_header_flattening.py` | `tests/unit/test_header_flattening.py` |
| `test_spanning_headers.py` | `tests/unit/test_spanning_headers.py` |
| `test_multi_row_header_normalizer.py` | `tests/unit/test_multi_row_header_normalizer.py` |
| `test_consolidated_exporter.py` | `tests/unit/test_consolidated_exporter.py` |
| `test_extraction.py` | `tests/integration/test_extraction.py` |
| `test_real_tables.py` | `tests/integration/test_real_tables.py` |
| `test_system.py` | `tests/system/test_system.py` |
| `test_merge_simple.py` | `tests/test_merge_simple.py` |
| `test_category_separator_standalone.py` | `test_category_separator_standalone.py` |
