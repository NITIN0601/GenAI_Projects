"""
Query understanding and routing system for financial RAG queries.
Supports 7 query types with intelligent routing.
"""

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import re
from datetime import datetime
from dataclasses import dataclass


class QueryType(Enum):
    """Types of queries the system can handle."""
    SPECIFIC_VALUE = "specific_value"  # "What was net revenue in Q1 2025?"
    COMPARISON = "comparison"  # "Compare revenues Q1 2025 vs Q1 2024"
    TREND = "trend"  # "Show revenue trend for last 4 quarters"
    AGGREGATION = "aggregation"  # "Average revenue across all quarters"
    MULTI_DOCUMENT = "multi_document"  # "Show revenues from all documents"
    CROSS_TABLE = "cross_table"  # "Show revenue and cash flow"
    HIERARCHICAL = "hierarchical"  # "Show all revenue line items"


@dataclass
class ParsedQuery:
    """Structured representation of a parsed query."""
    query_type: QueryType
    financial_concepts: List[str]  # ["net_revenue", "total_assets"]
    time_periods: List[str]  # ["Q1 2025", "March 31, 2025"]
    companies: List[str]  # ["Morgan Stanley"]
    operations: List[str]  # ["compare", "trend", "average"]
    table_types: List[str]  # ["income_statement", "balance_sheet"]
    canonical_labels: List[str]  # Mapped from financial_concepts
    metadata_filters: Dict[str, Any]  # For vector search
    original_query: str


class QueryUnderstanding:
    """
    Analyzes and understands user queries.
    Maps natural language to structured query format.
    """
    
    def __init__(self):
        """Initialize query understanding with mappings."""
        # Financial concept mappings
        self.concept_mappings = {
            # Revenue concepts
            "revenue": ["net_revenues", "total_revenues", "revenues"],
            "net revenue": ["net_revenues"],
            "total revenue": ["total_revenues"],
            "sales": ["net_revenues", "sales"],
            
            # Income concepts
            "profit": ["net_income", "income_before_taxes"],
            "net income": ["net_income"],
            "earnings": ["net_income", "earnings"],
            "income": ["net_income", "income_before_taxes"],
            
            # Asset concepts
            "assets": ["total_assets"],
            "total assets": ["total_assets"],
            "cash": ["cash_and_cash_equivalents"],
            
            # Liability concepts
            "liabilities": ["total_liabilities"],
            "debt": ["total_debt", "long_term_debt", "short_term_debt"],
            "borrowings": ["borrowings", "total_borrowings"],
            
            # Equity concepts
            "equity": ["total_equity", "shareholders_equity"],
            
            # Expense concepts
            "expenses": ["total_expenses", "operating_expenses"],
            "operating expenses": ["operating_expenses"],
            
            # Special tables
            "contractual principal": ["loans_and_other_debt", "nonaccrual_loans", "borrowings"],
            "fair value": ["loans_and_other_debt", "nonaccrual_loans", "borrowings"]
        }
        
        # Table type mappings
        self.table_type_mappings = {
            "income statement": "income_statement",
            "balance sheet": "balance_sheet",
            "cash flow": "cash_flow_statement",
            "cash flow statement": "cash_flow_statement",
            "statement of cash flows": "cash_flow_statement"
        }
        
        # Operation keywords
        self.operation_keywords = {
            "compare": ["compare", "comparison", "versus", "vs", "compared to"],
            "trend": ["trend", "progression", "over time", "historical"],
            "average": ["average", "mean", "avg"],
            "sum": ["sum", "total", "aggregate"],
            "growth": ["growth", "increase", "change"],
            "all": ["all", "every", "each"]
        }
    
    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse natural language query into structured format.
        
        Args:
            query: Natural language query
        
        Returns:
            ParsedQuery object with extracted entities
        """
        query_lower = query.lower()
        
        # Determine query type
        query_type = self._determine_query_type(query_lower)
        
        # Extract entities
        financial_concepts = self._extract_financial_concepts(query_lower)
        time_periods = self._extract_time_periods(query)
        companies = self._extract_companies(query)
        operations = self._extract_operations(query_lower)
        table_types = self._extract_table_types(query_lower)
        
        # Map to canonical labels
        canonical_labels = self._map_to_canonical(financial_concepts)
        
        # Build metadata filters
        metadata_filters = self._build_metadata_filters(
            canonical_labels, time_periods, companies, table_types
        )
        
        return ParsedQuery(
            query_type=query_type,
            financial_concepts=financial_concepts,
            time_periods=time_periods,
            companies=companies,
            operations=operations,
            table_types=table_types,
            canonical_labels=canonical_labels,
            metadata_filters=metadata_filters,
            original_query=query
        )
    
    def _determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query."""
        # Check for comparison keywords
        if any(kw in query for kw in self.operation_keywords["compare"]):
            return QueryType.COMPARISON
        
        # Check for trend keywords
        if any(kw in query for kw in self.operation_keywords["trend"]):
            return QueryType.TREND
        
        # Check for aggregation keywords
        if any(kw in query for kw in self.operation_keywords["average"]) or \
           any(kw in query for kw in self.operation_keywords["sum"]):
            return QueryType.AGGREGATION
        
        # Check for multi-document keywords
        if any(kw in query for kw in self.operation_keywords["all"]) and "document" in query:
            return QueryType.MULTI_DOCUMENT
        
        # Check for hierarchical keywords
        if "breakdown" in query or "sub-items" in query or "line items" in query:
            return QueryType.HIERARCHICAL
        
        # Check for cross-table (multiple table types mentioned)
        table_mentions = sum(1 for table_type in self.table_type_mappings.keys() if table_type in query)
        if table_mentions > 1:
            return QueryType.CROSS_TABLE
        
        # Default to specific value
        return QueryType.SPECIFIC_VALUE
    
    def _extract_financial_concepts(self, query: str) -> List[str]:
        """Extract financial concepts from query."""
        concepts = []
        
        for concept, _ in self.concept_mappings.items():
            if concept in query:
                concepts.append(concept)
        
        return concepts
    
    def _extract_time_periods(self, query: str) -> List[str]:
        """Extract time periods from query."""
        periods = []
        
        # Pattern for quarters: Q1 2025, Q2 2024, etc.
        quarter_pattern = r'Q[1-4]\s*\d{4}'
        quarters = re.findall(quarter_pattern, query, re.IGNORECASE)
        periods.extend(quarters)
        
        # Pattern for dates: March 31, 2025
        date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
        dates = re.findall(date_pattern, query, re.IGNORECASE)
        periods.extend(dates)
        
        # Pattern for years: 2025, 2024
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        periods.extend(years)
        
        return list(set(periods))  # Remove duplicates
    
    def _extract_companies(self, query: str) -> List[str]:
        """Extract company names from query."""
        companies = []
        
        # Common company names
        company_patterns = [
            "Morgan Stanley",
            "Goldman Sachs",
            "JP Morgan",
            "Bank of America",
            "Citigroup"
        ]
        
        for company in company_patterns:
            if company.lower() in query.lower():
                companies.append(company)
        
        return companies
    
    def _extract_operations(self, query: str) -> List[str]:
        """Extract operations from query."""
        operations = []
        
        for operation, keywords in self.operation_keywords.items():
            if any(kw in query for kw in keywords):
                operations.append(operation)
        
        return operations
    
    def _extract_table_types(self, query: str) -> List[str]:
        """Extract table types from query."""
        table_types = []
        
        for table_name, table_type in self.table_type_mappings.items():
            if table_name in query:
                table_types.append(table_type)
        
        return list(set(table_types))
    
    def _map_to_canonical(self, financial_concepts: List[str]) -> List[str]:
        """Map financial concepts to canonical labels."""
        canonical = []
        
        for concept in financial_concepts:
            if concept in self.concept_mappings:
                canonical.extend(self.concept_mappings[concept])
        
        return list(set(canonical))
    
    def _build_metadata_filters(
        self,
        canonical_labels: List[str],
        time_periods: List[str],
        companies: List[str],
        table_types: List[str]
    ) -> Dict[str, Any]:
        """Build metadata filters for vector search."""
        filters = {}
        
        # Add canonical label filter
        if canonical_labels:
            if len(canonical_labels) == 1:
                filters["canonical_label"] = canonical_labels[0]
            else:
                filters["canonical_label"] = {"$in": canonical_labels}
        
        # Add period filters
        if time_periods:
            # Extract years and quarters
            years = []
            quarters = []
            
            for period in time_periods:
                # Check for quarter pattern
                quarter_match = re.search(r'Q([1-4])\s*(\d{4})', period, re.IGNORECASE)
                if quarter_match:
                    quarters.append(int(quarter_match.group(1)))
                    years.append(int(quarter_match.group(2)))
                
                # Check for year only
                year_match = re.search(r'\b(20\d{2})\b', period)
                if year_match:
                    years.append(int(year_match.group(1)))
            
            if years:
                if len(years) == 1:
                    filters["period_year"] = years[0]
                else:
                    filters["period_year"] = {"$in": list(set(years))}
            
            if quarters:
                if len(quarters) == 1:
                    filters["period_quarter"] = quarters[0]
                else:
                    filters["period_quarter"] = {"$in": list(set(quarters))}
        
        # Add company filter
        if companies:
            if len(companies) == 1:
                filters["company"] = companies[0]
            else:
                filters["company"] = {"$in": companies}
        
        # Add table type filter
        if table_types:
            if len(table_types) == 1:
                filters["table_type"] = table_types[0]
            else:
                filters["table_type"] = {"$in": table_types}
        
        return filters


# Singleton instance
_query_understanding = None

def get_query_understanding() -> QueryUnderstanding:
    """Get singleton query understanding instance."""
    global _query_understanding
    if _query_understanding is None:
        _query_understanding = QueryUnderstanding()
    return _query_understanding
