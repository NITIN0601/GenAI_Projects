"""
Metadata Column Injector.

Injects Source, Section, and Table Title columns into table DataFrames.
Includes fallback strategies for missing metadata.
"""

from typing import Optional, Dict
import pandas as pd
from src.utils import get_logger

logger = get_logger(__name__)


class MetadataFallbackStrategy:
    """Provide fallback strategies for missing metadata."""
    
    @staticmethod
    def extract_from_sheet_name(sheet_name: str) -> Dict[str, str]:
        """
        Extract metadata from sheet name patterns.
        
        Examples:
            - "51_table_3" → table number 3 from sheet 51
            - "2_Business_Segment" → Business Segment from sheet 2
        
        Returns:
            Dictionary with extracted metadata fields
        """
        metadata = {"section": "", "table_title": "", "source": ""}
        
        # Pattern: {sheet_num}_{descriptive_name}
        parts = sheet_name.split('_')
        if len(parts) > 1:
            # Use descriptive part as table title if available
            descriptive = '_'.join(parts[1:]).replace('_', ' ').title()
            metadata["table_title"] = descriptive if descriptive != "Table" else ""
        
        return metadata
    
    @staticmethod
    def extract_from_dataframe(df: pd.DataFrame) -> Dict[str, str]:
        """
        Extract metadata from DataFrame content heuristically.
        
        Strategy:
        1. Check first few rows for title-like content
        2. Look for source information in headers or footers
        3. Detect section from categorical patterns
        
        Returns:
            Dictionary with extracted metadata fields
        """
        metadata = {"section": "", "table_title": "", "source": ""}
        
        if df.empty or len(df.columns) == 0:
            return metadata
        
        # Check first column for potential title
        first_col = df.iloc[:, 0].tolist()[:3]  # First 3 rows
        for val in first_col:
            if isinstance(val, str) and len(val) > 10 and len(val) < 100:
                # Potential title: not too short, not too long
                if not any(char.isdigit() for char in val[:5]):  # Doesn't start with numbers
                    metadata["table_title"] = val
                    break
        
        return metadata
    
    @staticmethod
    def generate_placeholder(sheet_name: str = "", table_index: int = 0) -> Dict[str, str]:
        """
        Generate placeholder metadata with clear indicators.
        
        Returns:
            Dictionary with placeholder metadata
        """
        return {
            "section": "[MISSING]",
            "table_title": f"[AUTO] Table from {sheet_name}" if sheet_name else f"[AUTO] Table {table_index}",
            "source": f"[AUTO] Sheet {sheet_name}" if sheet_name else "[AUTO] Unknown"
        }


class MetadataInjector:
    """Injects metadata columns into table DataFrames with fallback support."""
    
    def __init__(self, enable_fallback: bool = True):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.enable_fallback = enable_fallback
        self.fallback_strategy = MetadataFallbackStrategy()
        self.metadata_missing_count = 0
        self.fallback_used_count = 0
    
    def inject_metadata_columns(
        self,
        df: pd.DataFrame,
        source: str = "",
        section: str = "",
        table_title: str = "",
        sheet_name: str = "",
        table_index: int = 0
    ) -> pd.DataFrame:
        """
        Add Source, Section, and Table Title columns to DataFrame.
        
        Columns are inserted at the beginning in order:
        Source | Section | Table Title | [existing columns]
        
        Args:
            df: Input DataFrame
            source: Source reference (e.g., '10q0925.pdf_pg7')
            section: Section name from Index
            table_title: Table title from Index
            sheet_name: Sheet name for fallback strategies
            table_index: Table index for fallback strategies
            
        Returns:
            DataFrame with metadata columns prepended
        """
        if df.empty:
            return df
        
        # Check if metadata is complete
        metadata = {"source": source, "section": section, "table_title": table_title}
        is_complete = all(metadata.values())
        
        if not is_complete and self.enable_fallback:
            self.metadata_missing_count += 1
            
            # Try fallback strategies in order
            fallback_meta = {}
            
            # Strategy 1: Extract from sheet name
            if sheet_name:
                fallback_meta.update(self.fallback_strategy.extract_from_sheet_name(sheet_name))
            
            # Strategy 2: Extract from DataFrame content
            if not fallback_meta.get("table_title"):
                fallback_meta.update(self.fallback_strategy.extract_from_dataframe(df))
            
            # Strategy 3: Generate placeholder
            if not any(fallback_meta.values()):
                fallback_meta = self.fallback_strategy.generate_placeholder(sheet_name, table_index)
            
            # Merge with original metadata (original takes priority)
            for field in ["section", "table_title", "source"]:
                if not metadata.get(field) and fallback_meta.get(field):
                    metadata[field] = fallback_meta[field]
                    self.logger.info(f"Used fallback for {field}: {fallback_meta[field]}")
                    self.fallback_used_count += 1
        
        result_df = df.copy()
        
        # Insert columns in reverse order to get correct final order
        # Final order: Source | Section | Table Title | [existing columns]
        result_df.insert(0, 'Table Title', metadata.get('table_title', ''))
        result_df.insert(0, 'Section', metadata.get('section', ''))
        result_df.insert(0, 'Source', metadata.get('source', ''))
        
        return result_df
    
    def get_statistics(self) -> Dict[str, int]:
        """Get metadata injection statistics."""
        return {
            "metadata_missing_count": self.metadata_missing_count,
            "fallback_used_count": self.fallback_used_count
        }
    
    def generate_metadata_quality_report(self) -> str:
        """Generate report on metadata quality."""
        stats = self.get_statistics()
        
        report = "# Metadata Quality Report\n\n"
        report += f"**Tables with Missing Metadata:** {stats['metadata_missing_count']}\n"
        report += f"**Fallback Values Used:** {stats['fallback_used_count']}\n\n"
        
        # Add recommendations
        report += "## Recommendations\n\n"
        if stats['metadata_missing_count'] > 0:
            report += "> [!WARNING]\n"
            report += f"> {stats['metadata_missing_count']} tables had incomplete metadata.\n"
            report += "> Review generated fallback values and update Index.csv as needed.\n"
            report += "> Look for values marked with [MISSING] or [AUTO] tags.\n"
        else:
            report += "> [!SUCCESS]\n"
            report += "> All tables have complete metadata!\n"
        
        return report


def get_metadata_injector(enable_fallback: bool = True) -> MetadataInjector:
    """Factory function for MetadataInjector."""
    return MetadataInjector(enable_fallback=enable_fallback)

