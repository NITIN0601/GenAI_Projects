"""
Unit tests for MetadataInjector.

Tests metadata column injection functionality.
"""

import pytest
import pandas as pd
from src.infrastructure.extraction.exporters.csv_exporter.metadata_injector import (
    MetadataInjector,
    get_metadata_injector,
)


class TestMetadataInjector:
    """Test suite for MetadataInjector class."""
    
    @pytest.fixture
    def injector(self):
        """Create MetadataInjector instance."""
        return MetadataInjector()
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame with existing columns."""
        return pd.DataFrame({
            'Category': ['Cat1', 'Cat2', 'Cat3'],
            'Product/Entity': ['Prod1', 'Prod2', 'Prod3'],
            'Q1-2025': [100, 200, 300],
            'Q2-2025': [150, 250, 350],
        })
    
    def test_initialization(self):
        """Test MetadataInjector initialization."""
        injector = MetadataInjector()
        assert injector is not None
        assert hasattr(injector, 'logger')
    
    def test_factory_function(self):
        """Test get_metadata_injector factory function."""
        injector = get_metadata_injector()
        assert isinstance(injector, MetadataInjector)
    
    def test_inject_all_metadata(self, injector, sample_df):
        """Test injecting all three metadata columns."""
        result = injector.inject_metadata_columns(
            sample_df,
            source='10q0925.pdf_pg7',
            section='Business Segment Results',
            table_title='Selected Financial Information'
        )
        
        # Check columns added
        assert 'Source' in result.columns
        assert 'Section' in result.columns
        assert 'Table Title' in result.columns
        
        # Check column order (metadata columns first)
        expected_order = ['Source', 'Section', 'Table Title', 'Category', 'Product/Entity', 'Q1-2025', 'Q2-2025']
        assert list(result.columns) == expected_order
        
        # Check values
        assert all(result['Source'] == '10q0925.pdf_pg7')
        assert all(result['Section'] == 'Business Segment Results')
        assert all(result['Table Title'] == 'Selected Financial Information')
        
        # Check existing data preserved
        assert list(result['Category']) == ['Cat1', 'Cat2', 'Cat3']
        assert list(result['Product/Entity']) == ['Prod1', 'Prod2', 'Prod3']
    
    def test_inject_empty_metadata(self, injector, sample_df):
        """Test injecting with empty metadata strings."""
        result = injector.inject_metadata_columns(
            sample_df,
            source='',
            section='',
            table_title=''
        )
        
        # Check columns added
        assert 'Source' in result.columns
        assert 'Section' in result.columns
        assert 'Table Title' in result.columns
        
        # Check values are empty strings
        assert all(result['Source'] == '')
        assert all(result['Section'] == '')
        assert all(result['Table Title'] == '')
        
        # Check existing data preserved
        assert len(result) == len(sample_df)
        assert list(result['Category']) == ['Cat1', 'Cat2', 'Cat3']
    
    def test_inject_partial_metadata(self, injector, sample_df):
        """Test injecting with some metadata missing."""
        result = injector.inject_metadata_columns(
            sample_df,
            source='10q0925.pdf_pg7',
            section='',
            table_title='Selected Financial Information'
        )
        
        # Check all columns added
        assert 'Source' in result.columns
        assert 'Section' in result.columns
        assert 'Table Title' in result.columns
        
        # Check values
        assert all(result['Source'] == '10q0925.pdf_pg7')
        assert all(result['Section'] == '')
        assert all(result['Table Title'] == 'Selected Financial Information')
    
    def test_inject_with_default_params(self, injector, sample_df):
        """Test injecting with default parameter values."""
        result = injector.inject_metadata_columns(sample_df)
        
        # Check columns added
        assert 'Source' in result.columns
        assert 'Section' in result.columns
        assert 'Table Title' in result.columns
        
        # Check default empty values
        assert all(result['Source'] == '')
        assert all(result['Section'] == '')
        assert all(result['Table Title'] == '')
    
    def test_inject_empty_dataframe(self, injector):
        """Test injecting metadata into empty DataFrame."""
        empty_df = pd.DataFrame()
        result = injector.inject_metadata_columns(
            empty_df,
            source='test.pdf_pg1',
            section='Test Section',
            table_title='Test Title'
        )
        
        # Should return empty DataFrame unchanged
        assert result.empty
        assert len(result.columns) == 0
    
    def test_inject_single_row(self, injector):
        """Test injecting metadata into single-row DataFrame."""
        single_row_df = pd.DataFrame({
            'Category': ['Cat1'],
            'Value': [100]
        })
        
        result = injector.inject_metadata_columns(
            single_row_df,
            source='test.pdf_pg1',
            section='Test Section',
            table_title='Test Title'
        )
        
        # Check structure
        assert len(result) == 1
        assert list(result.columns) == ['Source', 'Section', 'Table Title', 'Category', 'Value']
        
        # Check values
        assert result['Source'].iloc[0] == 'test.pdf_pg1'
        assert result['Section'].iloc[0] == 'Test Section'
        assert result['Table Title'].iloc[0] == 'Test Title'
    
    def test_inject_preserves_data_types(self, injector):
        """Test that data types are preserved after injection."""
        df = pd.DataFrame({
            'Category': ['A', 'B', 'C'],
            'IntCol': [1, 2, 3],
            'FloatCol': [1.1, 2.2, 3.3],
            'BoolCol': [True, False, True]
        })
        
        result = injector.inject_metadata_columns(
            df,
            source='test.pdf_pg1',
            section='Test',
            table_title='Test'
        )
        
        # Check data types preserved
        assert result['IntCol'].dtype == df['IntCol'].dtype
        assert result['FloatCol'].dtype == df['FloatCol'].dtype
        assert result['BoolCol'].dtype == df['BoolCol'].dtype
        
        # Check values preserved
        assert list(result['IntCol']) == [1, 2, 3]
        assert list(result['FloatCol']) == [1.1, 2.2, 3.3]
        assert list(result['BoolCol']) == [True, False, True]
    
    def test_inject_with_special_characters(self, injector, sample_df):
        """Test injecting metadata with special characters."""
        result = injector.inject_metadata_columns(
            sample_df,
            source='10q-2025.pdf_pg7',
            section='Fair Value & Credit Protection (Sold)',
            table_title='Table #1: Summary "Results"'
        )
        
        # Check values with special characters
        assert all(result['Source'] == '10q-2025.pdf_pg7')
        assert all(result['Section'] == 'Fair Value & Credit Protection (Sold)')
        assert all(result['Table Title'] == 'Table #1: Summary "Results"')
    
    def test_inject_does_not_modify_original(self, injector, sample_df):
        """Test that original DataFrame is not modified."""
        original_columns = list(sample_df.columns)
        original_shape = sample_df.shape
        
        result = injector.inject_metadata_columns(
            sample_df,
            source='test.pdf_pg1',
            section='Test',
            table_title='Test'
        )
        
        # Original DataFrame should be unchanged
        assert list(sample_df.columns) == original_columns
        assert sample_df.shape == original_shape
        
        # Result should be different
        assert 'Source' not in sample_df.columns
        assert 'Source' in result.columns
    
    def test_inject_with_existing_metadata_columns(self, injector):
        """Test behavior when metadata columns already exist."""
        df = pd.DataFrame({
            'Source': ['old_source'],
            'Section': ['old_section'],
            'Table Title': ['old_title'],
            'Category': ['Cat1'],
            'Value': [100]
        })
        
        # This should still work and add new columns (pandas allows duplicate column names)
        result = injector.inject_metadata_columns(
            df,
            source='new_source',
            section='new_section',
            table_title='new_title'
        )
        
        # New metadata should be in first 3 columns
        assert result.iloc[0, 0] == 'new_source'  # First Source column
        assert result.iloc[0, 1] == 'new_section'  # First Section column
        assert result.iloc[0, 2] == 'new_title'  # First Table Title column
    
    def test_inject_large_dataframe(self, injector):
        """Test injecting metadata into large DataFrame."""
        large_df = pd.DataFrame({
            'Category': [f'Cat{i}' for i in range(1000)],
            'Value': list(range(1000))
        })
        
        result = injector.inject_metadata_columns(
            large_df,
            source='test.pdf_pg1',
            section='Test Section',
            table_title='Test Title'
        )
        
        # Check all rows have metadata
        assert len(result) == 1000
        assert all(result['Source'] == 'test.pdf_pg1')
        assert all(result['Section'] == 'Test Section')
        assert all(result['Table Title'] == 'Test Title')
        
        # Check data integrity
        assert list(result['Category']) == [f'Cat{i}' for i in range(1000)]
        assert list(result['Value']) == list(range(1000))
