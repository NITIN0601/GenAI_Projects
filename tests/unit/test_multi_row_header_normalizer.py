"""
Comprehensive tests for MultiRowHeaderNormalizer.

Tests all 8 pattern groups with variations to ensure dynamic pattern detection works.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.multi_row_header_normalizer import MultiRowHeaderNormalizer, normalize_headers, normalize_header


class TestPatternGroup1_PointInTime:
    """Group 1: Simple point-in-time (At/As of Month Day, Year)"""
    
    def test_at_march_31(self):
        """At March 31, 2024 → Q1-2024"""
        result = normalize_header("At March 31, 2024")
        assert result == "Q1-2024"
    
    def test_at_june_30(self):
        """At June 30, 2024 → Q2-2024"""
        result = normalize_header("At June 30, 2024")
        assert result == "Q2-2024"
    
    def test_at_september_30(self):
        """At September 30, 2024 → Q3-2024"""
        result = normalize_header("At September 30, 2024")
        assert result == "Q3-2024"
    
    def test_at_december_31(self):
        """At December 31, 2024 → Q4-2024"""
        result = normalize_header("At December 31, 2024")
        assert result == "Q4-2024"
    
    def test_as_of_variation(self):
        """As of March 31, 2025 → Q1-2025"""
        result = normalize_header("As of March 31, 2025")
        assert result == "Q1-2025"
    
    def test_abbreviated_month(self):
        """At Dec 31, 2023 → Q4-2023"""
        result = normalize_header("At Dec 31, 2023")
        assert result == "Q4-2023"


class TestPatternGroup2_PeriodBased:
    """Group 2: Period-based (Three/Six/Nine Months Ended)"""
    
    def test_three_months_ended_march(self):
        """Three Months Ended March 31, 2024 → Q1-QTD-2024"""
        result = normalize_header("Three Months Ended March 31, 2024")
        assert result == "Q1-QTD-2024"
    
    def test_three_months_ended_june(self):
        """Three Months Ended June 30, 2024 → Q2-QTD-2024"""
        result = normalize_header("Three Months Ended June 30, 2024")
        assert result == "Q2-QTD-2024"
    
    def test_six_months_ended_june(self):
        """Six Months Ended June 30, 2024 → Q2-YTD-2024"""
        result = normalize_header("Six Months Ended June 30, 2024")
        assert result == "Q2-YTD-2024"
    
    def test_nine_months_ended_september(self):
        """Nine Months Ended September 30, 2024 → Q3-YTD-2024"""
        result = normalize_header("Nine Months Ended September 30, 2024")
        assert result == "Q3-YTD-2024"
    
    def test_year_ended(self):
        """Year Ended December 31, 2023 → YTD-2023"""
        result = normalize_header("Year Ended December 31, 2023")
        assert result == "YTD-2023"


class TestPatternGroup2_MultiRow:
    """Group 2: Multi-row spanning headers (Table2 pattern)"""
    
    def test_table2_three_rows(self):
        """Split period/month/year across 3 rows"""
        header_rows = [
            ['', 'Three Months Ended', '', 'Six Months Ended', ''],
            ['', 'March 31,', '', 'June 30,', ''],
            ['$ in millions', '2023', '2024', '2023', '2024'],
        ]
        result = normalize_headers(header_rows)
        assert result['normalized_headers'][0] == '$ in millions'
        assert result['normalized_headers'][1] == 'Q1-QTD-2023'
        assert result['normalized_headers'][2] == 'Q1-QTD-2024'
        assert result['normalized_headers'][3] == 'Q2-YTD-2023'
        assert result['normalized_headers'][4] == 'Q2-YTD-2024'
    
    def test_table2_with_nine_months(self):
        """Including Nine Months Ended"""
        header_rows = [
            ['', 'Nine Months Ended', ''],
            ['', 'September 30,', ''],
            ['$ in millions', '2023', '2024'],
        ]
        result = normalize_headers(header_rows)
        assert result['normalized_headers'][1] == 'Q3-YTD-2023'
        assert result['normalized_headers'][2] == 'Q3-YTD-2024'


class TestPatternGroup3_NonDateColumns:
    """Group 3: Period + non-date columns (% Change)"""
    
    def test_percent_change_preserved(self):
        """% Change should be preserved as-is"""
        result = normalize_header("% Change")
        assert result == "% Change"
    
    def test_total_preserved(self):
        """Total should be preserved as-is"""
        result = normalize_header("Total")
        assert result == "Total"
    
    def test_table5_with_percent_change(self):
        """Period columns + % Change"""
        header_rows = [
            ['', 'Three Months Ended', '', '%'],
            ['', 'March 31,', '', 'Change'],
            ['$ in millions', '2023', '2024', ''],
        ]
        result = normalize_headers(header_rows)
        assert 'Q1-QTD' in result['normalized_headers'][1]
        # % Change - combined from rows
        assert '2024' in result['normalized_headers'][2]


class TestPatternGroup4_CategoryCombinations:
    """Group 4: Period + category combinations"""
    
    def test_table6_period_with_categories(self):
        """Period header spanning category sub-columns"""
        header_rows = [
            ['', 'Three Months Ended June 30, 2024', '', '', ''],
            ['$ in millions', 'Trading', 'Fees', 'Net Interest', 'Total'],
        ]
        result = normalize_headers(header_rows)
        assert 'Q2-QTD-2024' in result['normalized_headers'][1]
        assert 'Trading' in result['normalized_headers'][1]
    
    def test_table8_segments(self):
        """Point-in-time + segment columns"""
        header_rows = [
            ['', 'At December 31, 2023', '', ''],
            ['$ in millions', 'IS', 'WM', 'Total'],
        ]
        result = normalize_headers(header_rows)
        assert 'Q4-2023' in result['normalized_headers'][1]


class TestPatternGroup5_NestedHeaders:
    """Group 5: Nested/complex headers with L1 prefix"""
    
    def test_table4_with_l1_prefix(self):
        """L1 prefix (Average Monthly Balance) + period + year"""
        header_rows = [
            ['', 'Average Monthly Balance', ''],
            ['', 'Three Months Ended March 31,', ''],
            ['$ in millions', '2023', '2024'],
        ]
        result = normalize_headers(header_rows)
        assert result['l1_headers'][1] == 'Average Monthly Balance'
        assert 'Q1-QTD' in result['normalized_headers'][1]


class TestPatternGroup6_FiscalQuarter:
    """Group 6: Fiscal quarter notation (4Q 2024)"""
    
    def test_4q_notation(self):
        """4Q 2024 → 4Q-2024"""
        result = normalize_header("4Q 2024")
        assert result == "4Q-2024"
    
    def test_1q_notation(self):
        """1Q 2025 → 1Q-2025"""
        result = normalize_header("1Q 2025")
        assert result == "1Q-2025"
    
    def test_fiscal_no_space(self):
        """4Q2024 → 4Q-2024"""
        result = normalize_header("4Q2024")
        assert result == "4Q-2024"


class TestPatternGroup7_CombinedDates:
    """Group 7: Combined dates (At X and Y)"""
    
    def test_combined_dates(self):
        """At June 30, 2024 and December 31, 2023"""
        result = normalize_header("At June 30, 2024 and December 31, 2023")
        assert 'Q2-2024' in result
        assert 'Q4-2023' in result


class TestPatternGroup8_Specialized:
    """Group 8: Specialized patterns"""
    
    def test_dollar_in_millions_preserved(self):
        """$ in millions should be preserved"""
        result = normalize_header("$ in millions")
        assert result == "$ in millions"
    
    def test_dollar_in_billions_preserved(self):
        """$ in billions should be preserved"""
        result = normalize_header("$ in billions")
        assert result == "$ in billions"
    
    def test_inflows_preserved(self):
        """Inflows should be preserved"""
        result = normalize_header("Inflows")
        assert result == "Inflows"


class TestEdgeCases:
    """Edge cases and variations"""
    
    def test_empty_header(self):
        """Empty string should return empty"""
        result = normalize_header("")
        assert result == ""
    
    def test_year_only_with_10k(self):
        """Year only with 10-K source → YTD-YEAR"""
        result = normalize_header("2024", "10k1224.pdf")
        assert result == "YTD-2024"
    
    def test_lowercase_variations(self):
        """Handle lowercase input"""
        result = normalize_header("at march 31, 2024")
        assert result == "Q1-2024"
    
    def test_extra_whitespace(self):
        """Handle extra whitespace"""
        result = normalize_header("  At  March   31,   2024  ")
        assert result == "Q1-2024"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
