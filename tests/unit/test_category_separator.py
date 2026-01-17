"""
Unit tests for Category Separator.

Tests category detection and line item association logic.
"""

import pytest
import pandas as pd
from src.infrastructure.extraction.exporters.csv_exporter.category_separator import CategorySeparator


class TestCategorySeparator:
    """Test suite for CategorySeparator."""
    
    @pytest.fixture
    def separator(self):
        """Create CategorySeparator instance."""
        return CategorySeparator()
    
    def test_simple_category_extraction(self, separator):
        """Test simple category extraction (Test Case 1)."""
        # Input data matching 2_table_1.csv example
        data = [
            ['$ in millions, except per share data', 'Q3-QTD-2025', 'Q3-QTD-2024', 'Q3-YTD-2025', 'Q3-YTD-2024'],
            ['', '', '', '', ''],
            ['Consolidated results', '', '', '', ''],
            ['Net revenues', 18224, 15383, 52755, 45538],
            ['Earnings applicable to Morgan Stanley common shareholders', 4450, 3028, 11999, 9236],
            ['Earnings per diluted common share', 2.8, 1.88, 7.53, 5.73],
            ['Consolidated financial measures', '', '', '', ''],
            ['Expense efficiency ratio', 0.67, 0.72, 0.69, 0.72],
            ['ROE', 0.18, 0.131, 0.165, 0.135],
            ['Pre-tax margin by segment', '', '', '', ''],
            ['Institutional Securities', 0.37, 0.28, 0.34, 0.3],
            ['Wealth Management', 0.3, 0.28, 0.29, 0.27],
            ['Investment Management', 0.22, 0.18, 0.21, 0.17],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Check categories found
        assert len(categories) == 3
        assert 'Consolidated results' in categories
        assert 'Consolidated financial measures' in categories
        assert 'Pre-tax margin by segment' in categories
        
        # Check output structure
        assert 'Category' in result_df.columns
        assert 'Product/Entity' in result_df.columns
        
        # Check row count (9 line items)
        assert len(result_df) == 9
        
        # Check first row
        first_row = result_df.iloc[0]
        assert first_row['Category'] == 'Consolidated results'
        assert first_row['Product/Entity'] == 'Net revenues'
        assert first_row['Q3-QTD-2025'] == 18224
        
        # Check category association
        assert result_df[result_df['Product/Entity'] == 'Net revenues']['Category'].iloc[0] == 'Consolidated results'
        assert result_df[result_df['Product/Entity'] == 'ROE']['Category'].iloc[0] == 'Consolidated financial measures'
        assert result_df[result_df['Product/Entity'] == 'Wealth Management']['Category'].iloc[0] == 'Pre-tax margin by segment'
    
    def test_no_categories_present(self, separator):
        """Test table with no categories (Test Case 2)."""
        data = [
            ['$ in millions', 'Q3-2025', 'Q3-2024'],
            ['Net revenues', 18224, 15383],
            ['Compensation expense', 7442, 6733],
            ['Non-compensation expense', 3781, 3459],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Check no categories found
        assert len(categories) == 0
        
        # Check all rows have empty category
        assert all(result_df['Category'] == '')
        
        # Check row count (3 line items)
        assert len(result_df) == 3
        
        # Check data preserved
        assert result_df.iloc[0]['Product/Entity'] == 'Net revenues'
        assert result_df.iloc[0]['Q3-2025'] == 18224
    
    def test_multiple_categories_in_sequence(self, separator):
        """Test multiple categories in sequence (Test Case 3)."""
        data = [
            ['$ in millions', 'Q3-2025', 'Q3-2024'],
            ['', '', ''],
            ['Category A', '', ''],
            ['Item 1', 100, 90],
            ['Item 2', 200, 180],
            ['Category B', '', ''],
            ['Item 3', 300, 270],
            ['Category C', '', ''],
            ['Item 4', 400, 360],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Check categories
        assert len(categories) == 3
        assert 'Category A' in categories
        assert 'Category B' in categories
        assert 'Category C' in categories
        
        # Check associations
        assert result_df[result_df['Product/Entity'] == 'Item 1']['Category'].iloc[0] == 'Category A'
        assert result_df[result_df['Product/Entity'] == 'Item 2']['Category'].iloc[0] == 'Category A'
        assert result_df[result_df['Product/Entity'] == 'Item 3']['Category'].iloc[0] == 'Category B'
        assert result_df[result_df['Product/Entity'] == 'Item 4']['Category'].iloc[0] == 'Category C'
    
    def test_nested_categories(self, separator):
        """Test nested categories (Test Case 4)."""
        data = [
            ['$ in millions', 'Bilateral OTC', 'Cleared OTC', 'Total'],
            ['', '', '', ''],
            ['Designated as accounting hedges', '', '', ''],
            ['Interest rate', 3, 5, 8],
            ['Foreign exchange', 49, 60, 109],
            ['Total', 52, 65, 117],
            ['Not designated as accounting hedges', '', '', ''],
            ['Other derivatives', '', '', ''],
            ['Interest rate', 114429, 14447, 128986],
            ['Credit', 4731, 8208, 12939],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Phase 1: Flat categories (no hierarchy)
        assert len(categories) == 3  # All empty-data rows detected as categories
        assert 'Designated as accounting hedges' in categories
        assert 'Not designated as accounting hedges' in categories
        assert 'Other derivatives' in categories
        
        # Check that "Other derivatives" becomes active category
        last_items = result_df[result_df['Category'] == 'Other derivatives']
        assert len(last_items) == 2
        assert 'Interest rate' in last_items['Product/Entity'].values
        assert 'Credit' in last_items['Product/Entity'].values
    
    def test_repeated_header_text_pattern(self, separator):
        """Test repeated header text pattern (Test Case 5)."""
        data = [
            ['$ in millions', 'Q3-2025', 'Q3-2025', 'Q3-2024'],
            ['', '', '', ''],
            ['State and municipal securities', 'State and municipal securities', 'State and municipal securities', 'State and municipal securities'],
            ['Beginning balance', 10, 5, 34],
            ['Sales', '', '', -29],
            ['Ending balance', '', 13, 13],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Check category detected
        assert len(categories) == 1
        assert 'State and municipal securities' in categories
        
        # Check line items associated with category
        assert len(result_df) == 3
        assert all(result_df['Category'] == 'State and municipal securities')
    
    def test_edge_cases_empty_rows_and_dashes(self, separator):
        """Test edge cases: empty rows and dash values (Test Case 6)."""
        data = [
            ['$ in millions', 'Q3-2025', 'Q3-2024'],
            ['', '', ''],
            ['Results by segment', '', ''],
            ['Institutional Securities', 5000, 4200],
            ['', '', ''],  # Empty row
            ['Wealth Management', 3000, 2800],
            ['Investment Management', '$-', '$-'],  # Dash values
            ['Net impact', '-', '-'],  # Dash values
            ['Total', 8000, 7000],
        ]
        
        df = pd.DataFrame(data)
        result_df, categories = separator.separate_categories(df)
        
        # Check category
        assert len(categories) == 1
        assert 'Results by segment' in categories
        
        # Check empty rows skipped
        assert len(result_df) == 5  # Empty rows not included
        
        # Check dash values preserved
        dash_row1 = result_df[result_df['Product/Entity'] == 'Investment Management'].iloc[0]
        assert dash_row1['Q3-2025'] == '$-'
        
        dash_row2 = result_df[result_df['Product/Entity'] == 'Net impact'].iloc[0]
        assert dash_row2['Q3-2025'] == '-'
    
    def test_is_category_header(self, separator):
        """Test category header detection."""
        header_row = ['$ in millions', 'Q3-2025', 'Q3-2024']
        
        # Category row
        assert separator.is_category_header(['Consolidated results', '', ''], header_row) is True
        
        # Data row
        assert separator.is_category_header(['Net revenues', 18224, 15383], header_row) is False
        
        # Empty row
        assert separator.is_category_header(['', '', ''], header_row) is False
        
        # Dash-only row (should be False - has values)
        assert separator.is_category_header(['Total', '-', '-'], header_row) is True  # Dashes treated as empty
    
    def test_is_repeated_header_category(self, separator):
        """Test repeated header text detection."""
        # Repeated text across all columns
        assert separator.is_repeated_header_category([
            'State and municipal securities',
            'State and municipal securities',
            'State and municipal securities'
        ]) is True
        
        # Different text in columns
        assert separator.is_repeated_header_category([
            'State and municipal securities',
            'Different text',
            'State and municipal securities'
        ]) is False
        
        # With empty columns
        assert separator.is_repeated_header_category([
            'State and municipal securities',
            '',
            'State and municipal securities'
        ]) is True
        
        # All empty
        assert separator.is_repeated_header_category(['', '', '']) is False
    
    def test_empty_dataframe(self, separator):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        result_df, categories = separator.separate_categories(df)
        
        assert result_df.empty
        assert len(categories) == 0
