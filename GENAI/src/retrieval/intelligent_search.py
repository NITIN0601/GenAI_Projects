"""
Intelligent Search Strategy Module.

Analyzes user queries to determine optimal search filters and strategies.
Automatically extracts:
- Table names for title filtering
- Year/Quarter for temporal filtering
- Financial statement types
- Company references
"""

import re
import logging
from src.utils import get_logger
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = get_logger(__name__)


class QueryIntent(Enum):
    """Detected query intent types."""
    TABLE_LOOKUP = "table_lookup"  # Looking for specific table by name
    TEMPORAL_QUERY = "temporal_query"  # Looking for data from specific period
    COMPARATIVE = "comparative"  # Comparing data across periods
    FINANCIAL_METRIC = "financial_metric"  # Looking for specific metric
    GENERAL = "general"  # General question


@dataclass
class QueryAnalysis:
    """Result of query analysis."""
    original_query: str
    cleaned_query: str
    intent: QueryIntent
    filters: Dict[str, Any]
    search_fields: List[str]
    table_name: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[str] = None
    metrics: List[str] = field(default_factory=list)  # Fixed: use field() for mutable defaults
    confidence: float = 0.5


class QueryAnalyzer:
    """
    Analyzes user queries to extract search intent and filters.
    
    Detects:
    - Table names (e.g., "Consolidated Balance Sheet", "Income Statement")
    - Temporal references (e.g., "Q1 2024", "2023", "last quarter")
    - Financial metrics (e.g., "revenue", "net income", "assets")
    - Comparison patterns (e.g., "compare Q1 vs Q2")
    """
    
    # Common financial table names
    TABLE_PATTERNS = [
        r"consolidated\s+balance\s+sheet",
        r"consolidated\s+statement[s]?\s+of\s+income",
        r"consolidated\s+income\s+statement[s]?",
        r"consolidated\s+statement[s]?\s+of\s+cash\s+flow[s]?",
        r"consolidated\s+statement[s]?\s+of\s+comprehensive\s+income",
        r"consolidated\s+statement[s]?\s+of\s+changes\s+in\s+.*equity",
        r"selected\s+financial\s+(?:information|data)",
        r"notes?\s+to\s+(?:consolidated\s+)?financial\s+statements?",
        r"fair\s+value\s+(?:hierarchy|measurements?)",
        r"loans?\s+and\s+lending\s+commitments?",
        r"contractual\s+(?:obligations?|maturities)",
        r"segment\s+(?:information|results?|reporting)",
        r"revenue\s+(?:by\s+)?(?:segment|geography|product)",
        r"valuation\s+techniques?\s+(?:and\s+)?unobservable\s+inputs?",
        r"average\s+balances?\s+(?:and\s+)?interest\s+rates?",
        r"net\s+interest\s+income",
        r"trading\s+(?:assets?|liabilities|portfolio)",
        r"investment\s+securities?",
        r"allowance\s+for\s+(?:credit\s+)?loss(?:es)?",
        r"regulatory\s+capital",
        r"risk[- ]weighted\s+assets?",
        r"var\s+(?:measures?|statistics?)",
    ]
    
    # Quarter patterns
    QUARTER_PATTERNS = [
        r"q([1-4])\s*(?:20)?(\d{2})",  # Q1 24, Q1 2024
        r"(?:first|second|third|fourth)\s+quarter\s*(?:of\s*)?(?:20)?(\d{2})?",
        r"(?:march|june|september|december)\s*(?:20)?(\d{2})?",
    ]
    
    # Year patterns
    YEAR_PATTERNS = [
        r"(?:fy\s*|fiscal\s+year\s*)?20(\d{2})",
        r"(?:in|for|during)\s+20(\d{2})",
    ]
    
    # Financial metrics
    METRIC_PATTERNS = {
        "revenue": r"(?:net\s+)?revenues?|sales",
        "income": r"(?:net\s+)?income|earnings?|profit",
        "assets": r"(?:total\s+)?assets?",
        "liabilities": r"(?:total\s+)?liabilities?",
        "equity": r"(?:shareholders'?\s+)?equity|common\s+stock",
        "cash_flow": r"cash\s+flows?|operating\s+activities",
        "eps": r"(?:diluted\s+)?earnings?\s+per\s+share|eps",
        "margin": r"(?:profit|operating|gross)\s+margins?",
        "roa": r"return\s+on\s+assets?|roa",
        "roe": r"return\s+on\s+equity|roe|rotce",
        "capital": r"(?:regulatory\s+)?capital|tier\s+[12]",
        "fair_value": r"fair\s+values?|mark[- ]to[- ]market",
        "principal": r"(?:contractual\s+)?principal|unpaid\s+principal",
    }
    
    def __init__(self):
        # Compile patterns for efficiency
        self._table_patterns = [re.compile(p, re.IGNORECASE) for p in self.TABLE_PATTERNS]
        self._quarter_patterns = [re.compile(p, re.IGNORECASE) for p in self.QUARTER_PATTERNS]
        self._year_patterns = [re.compile(p, re.IGNORECASE) for p in self.YEAR_PATTERNS]
        self._metric_patterns = {k: re.compile(v, re.IGNORECASE) for k, v in self.METRIC_PATTERNS.items()}
    
    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a user query and extract search parameters.
        
        Returns a QueryAnalysis with detected filters and intent.
        """
        query_lower = query.lower().strip()
        filters = {}
        search_fields = ["content"]  # Default: search content
        
        # Detect table name
        table_name = self._extract_table_name(query_lower)
        if table_name:
            filters["table_title"] = table_name
            search_fields.append("table_title")
        
        # Detect temporal references
        year, quarter = self._extract_temporal(query_lower)
        if year:
            filters["year"] = year
        if quarter:
            filters["quarter"] = quarter
        
        # Detect metrics
        metrics = self._extract_metrics(query_lower)
        
        # Determine intent
        intent = self._determine_intent(query_lower, table_name, year, quarter, metrics)
        
        # Calculate confidence
        confidence = self._calculate_confidence(table_name, year, quarter, metrics)
        
        # Clean query for embedding search (remove temporal/table references)
        cleaned_query = self._clean_query(query_lower, table_name, year, quarter)
        
        return QueryAnalysis(
            original_query=query,
            cleaned_query=cleaned_query,
            intent=intent,
            filters=filters,
            search_fields=search_fields,
            table_name=table_name,
            year=year,
            quarter=quarter,
            metrics=metrics,
            confidence=confidence
        )
    
    def _extract_table_name(self, query: str) -> Optional[str]:
        """Extract table name from query."""
        for pattern in self._table_patterns:
            match = pattern.search(query)
            if match:
                # Return the matched table name (cleaned up)
                table_name = match.group(0).strip()
                # Capitalize properly
                return table_name.title()
        return None
    
    def _extract_temporal(self, query: str) -> Tuple[Optional[int], Optional[str]]:
        """Extract year and quarter from query."""
        year = None
        quarter = None
        
        # Try quarter patterns first
        for pattern in self._quarter_patterns:
            match = pattern.search(query)
            if match:
                groups = match.groups()
                if len(groups) >= 1 and groups[0]:
                    if groups[0].isdigit() and len(groups[0]) == 1:
                        quarter = f"Q{groups[0]}"
                    elif groups[0].lower() in ["first", "1"]:
                        quarter = "Q1"
                    elif groups[0].lower() in ["second", "2"]:
                        quarter = "Q2"
                    elif groups[0].lower() in ["third", "3"]:
                        quarter = "Q3"
                    elif groups[0].lower() in ["fourth", "4"]:
                        quarter = "Q4"
                if len(groups) >= 2 and groups[1]:
                    yr = int(groups[1])
                    year = 2000 + yr if yr < 100 else yr
                break
        
        # Try year patterns
        if not year:
            for pattern in self._year_patterns:
                match = pattern.search(query)
                if match:
                    yr = int(match.group(1))
                    year = 2000 + yr if yr < 100 else yr
                    break
        
        return year, quarter
    
    def _extract_metrics(self, query: str) -> List[str]:
        """Extract financial metrics mentioned in query."""
        metrics = []
        for metric_name, pattern in self._metric_patterns.items():
            if pattern.search(query):
                metrics.append(metric_name)
        return metrics
    
    def _determine_intent(
        self, 
        query: str, 
        table_name: Optional[str],
        year: Optional[int],
        quarter: Optional[str],
        metrics: List[str]
    ) -> QueryIntent:
        """Determine the primary intent of the query."""
        
        # Table lookup if specific table name found
        if table_name:
            return QueryIntent.TABLE_LOOKUP
        
        # Comparative if comparing patterns found
        compare_patterns = [r"compare", r"vs\.?", r"versus", r"between", r"difference"]
        if any(re.search(p, query, re.IGNORECASE) for p in compare_patterns):
            return QueryIntent.COMPARATIVE
        
        # Temporal if year/quarter specified
        if year or quarter:
            return QueryIntent.TEMPORAL_QUERY
        
        # Financial metric if metrics found
        if metrics:
            return QueryIntent.FINANCIAL_METRIC
        
        return QueryIntent.GENERAL
    
    def _calculate_confidence(
        self,
        table_name: Optional[str],
        year: Optional[int],
        quarter: Optional[str],
        metrics: List[str]
    ) -> float:
        """Calculate confidence score for the analysis."""
        confidence = 0.3  # Base confidence
        
        if table_name:
            confidence += 0.3
        if year:
            confidence += 0.15
        if quarter:
            confidence += 0.1
        if metrics:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _clean_query(
        self,
        query: str,
        table_name: Optional[str],
        year: Optional[int],
        quarter: Optional[str]
    ) -> str:
        """Clean query for embedding search."""
        cleaned = query
        
        # Remove table name if found (we'll use it as filter)
        if table_name:
            cleaned = re.sub(re.escape(table_name.lower()), "", cleaned, flags=re.IGNORECASE)
        
        # Remove temporal references
        for pattern in self._quarter_patterns + self._year_patterns:
            cleaned = re.sub(pattern, "", cleaned)
        
        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # If cleaned is too short, use original
        if len(cleaned) < 10:
            return query
        
        return cleaned


class IntelligentSearchStrategy:
    """
    Intelligent search strategy that combines query analysis with vector search.
    
    Automatically determines:
    - Which filters to apply
    - How many results to fetch
    - Whether to use hybrid search (filter + semantic)
    """
    
    def __init__(self, vectordb_manager):
        self.vectordb = vectordb_manager
        self.analyzer = QueryAnalyzer()
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Perform intelligent search based on query analysis.
        
        Returns:
            Dict with 'results', 'analysis', and 'strategy' info
        """
        # Analyze query
        analysis = self.analyzer.analyze(query)
        
        logger.info(f"Query intent: {analysis.intent.value}")
        logger.info(f"Detected filters: {analysis.filters}")
        
        # Determine search strategy
        if analysis.intent == QueryIntent.TABLE_LOOKUP and analysis.table_name:
            # Use filter-first strategy for table lookups
            results = self._filtered_search(analysis, top_k * 2)
        elif analysis.intent == QueryIntent.TEMPORAL_QUERY:
            # Use temporal filter with semantic search
            results = self._temporal_search(analysis, top_k)
        elif analysis.intent == QueryIntent.COMPARATIVE:
            # Fetch more results for comparison
            results = self._comparative_search(analysis, top_k * 2)
        else:
            # Standard semantic search with optional filters
            results = self._semantic_search(analysis, top_k)
        
        return {
            "results": results[:top_k],
            "analysis": analysis,
            "strategy": analysis.intent.value,
            "total_found": len(results)
        }
    
    def _filtered_search(self, analysis: QueryAnalysis, top_k: int) -> List:
        """Search with filters as primary strategy.
        
        Returns:
            List of search results from vector database
        """
        return self.vectordb.search(
            query=analysis.cleaned_query,
            top_k=top_k,
            filters=analysis.filters
        )
    
    def _temporal_search(self, analysis: QueryAnalysis, top_k: int) -> List:
        """Search with temporal filters.
        
        Returns:
            List of search results from vector database
        """
        return self.vectordb.search(
            query=analysis.cleaned_query,
            top_k=top_k,
            filters=analysis.filters
        )
    
    def _comparative_search(self, analysis: QueryAnalysis, top_k: int) -> List:
        """Search for comparative analysis (multiple periods).
        
        Returns:
            List of search results from vector database
        """
        # Remove specific year/quarter filters to get data from multiple periods
        filters = {k: v for k, v in analysis.filters.items() if k not in ["year", "quarter"]}
        
        return self.vectordb.search(
            query=analysis.original_query,
            top_k=top_k,
            filters=filters if filters else None
        )
    
    def _semantic_search(self, analysis: QueryAnalysis, top_k: int) -> List:
        """Standard semantic search.
        
        Returns:
            List of search results from vector database
        """
        filters = analysis.filters if analysis.filters else None
        return self.vectordb.search(
            query=analysis.original_query,
            top_k=top_k,
            filters=filters
        )


def get_search_strategy(vectordb_manager) -> IntelligentSearchStrategy:
    """Factory function to get search strategy instance."""
    return IntelligentSearchStrategy(vectordb_manager)
