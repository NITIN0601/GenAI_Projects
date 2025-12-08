"""
Query Processor - Complete query processing pipeline.

Provides thread-safe singleton access to query processing with support for:
- Query understanding and routing
- 7 query types (specific value, comparison, trend, aggregation, etc.)
- Table consolidation and formatting

Example:
    >>> from src.retrieval import get_query_processor
    >>> 
    >>> processor = get_query_processor()
    >>> results = processor.process_query("Compare revenues Q1 vs Q2")
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
import pandas as pd

from src.core.singleton import ThreadSafeSingleton
from src.retrieval.query_understanding import QueryUnderstanding, QueryType, ParsedQuery, get_query_understanding
from src.infrastructure.extraction.consolidation import TableConsolidationEngine, get_consolidation_engine
from src.domain import RAGQuery, RAGResponse
from src.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.infrastructure.vectordb.manager import VectorDBManager


class QueryProcessor(metaclass=ThreadSafeSingleton):
    """
    Complete query processing pipeline.
    
    Thread-safe singleton manager for query processing.
    
    Handles all 7 query types with intelligent routing.
    
    Attributes:
        vector_store: VectorDBManager instance
        query_understanding: Query understanding component
        consolidation_engine: Table consolidation component
    """
    
    def __init__(
        self,
        vector_store: Optional["VectorDBManager"] = None,
        query_understanding: Optional[QueryUnderstanding] = None,
        consolidation_engine: Optional[TableConsolidationEngine] = None
    ):
        """
        Initialize query processor with components.
        
        Args:
            vector_store: VectorDBManager instance (auto-created if None)
            query_understanding: Query understanding component (auto-created if None)
            consolidation_engine: Table consolidation component (auto-created if None)
        """
        self._vector_store = vector_store
        self._query_understanding = query_understanding
        self._consolidation_engine = consolidation_engine
        self._embedding_manager = None
    
    @property
    def vector_store(self) -> "VectorDBManager":
        """Get vector store (lazy initialization)."""
        if self._vector_store is None:
            from src.infrastructure.vectordb.manager import get_vectordb_manager
            self._vector_store = get_vectordb_manager()
        return self._vector_store
    
    @property
    def query_understanding(self) -> QueryUnderstanding:
        """Get query understanding (lazy initialization)."""
        if self._query_understanding is None:
            self._query_understanding = get_query_understanding()
        return self._query_understanding
    
    @property
    def consolidation_engine(self) -> TableConsolidationEngine:
        """Get consolidation engine (lazy initialization)."""
        if self._consolidation_engine is None:
            self._consolidation_engine = get_consolidation_engine()
        return self._consolidation_engine
    
    @property
    def embedding_manager(self):
        """Get embedding manager (lazy initialization)."""
        if self._embedding_manager is None:
            from src.infrastructure.embeddings.manager import get_embedding_manager
            self._embedding_manager = get_embedding_manager()
        return self._embedding_manager
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return "query-processor"
    
    def is_available(self) -> bool:
        """Check if processor is available (implements BaseProvider protocol)."""
        try:
            return self.vector_store.is_available()
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            available = self.is_available()
            return {
                "status": "ok" if available else "error",
                "vector_store": self.vector_store.name if self._vector_store else "not initialized",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def process_query(
        self,
        query: str,
        top_k: int = 50
    ) -> Dict[str, Any]:
        """
        Process a natural language query end-to-end.
        
        Args:
            query: Natural language query
            top_k: Number of results to retrieve
        
        Returns:
            Dict with results, table, and metadata
        """
        # Step 1: Parse and understand query
        parsed_query = self.query_understanding.parse_query(query)
        
        # Step 2: Route to appropriate handler
        handler = self._get_handler(parsed_query.query_type)
        
        # Step 3: Execute query
        results = handler(parsed_query, top_k)
        
        return results
    
    def _get_handler(self, query_type: QueryType):
        """Get appropriate handler for query type."""
        handlers = {
            QueryType.SPECIFIC_VALUE: self._handle_specific_value,
            QueryType.COMPARISON: self._handle_comparison,
            QueryType.TREND: self._handle_trend,
            QueryType.AGGREGATION: self._handle_aggregation,
            QueryType.MULTI_DOCUMENT: self._handle_multi_document,
            QueryType.CROSS_TABLE: self._handle_cross_table,
            QueryType.HIERARCHICAL: self._handle_hierarchical
        }
        return handlers.get(query_type, self._handle_specific_value)
    
    def _handle_specific_value(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 1: Specific Value Query."""
        search_text = " ".join(parsed_query.financial_concepts + parsed_query.time_periods)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        values = []
        results = []
        for doc, score in results_with_scores:
            metadata = doc.metadata
            values.append({
                "metric": metadata.get("row_label"),
                "period": metadata.get("period_label"),
                "value": metadata.get("value_display"),
                "source": metadata.get("filename"),
                "table": metadata.get("table_title")
            })
            results.append({"metadata": metadata, "content": doc.page_content})
        
        return {
            "query_type": "specific_value",
            "query": parsed_query.original_query,
            "values": values[:5],
            "total_results": len(results)
        }
    
    def _handle_comparison(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 2: Comparison Query."""
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        df = self.consolidation_engine.consolidate_same_table_different_periods(results)
        
        if len(df.columns) > 2:
            periods = [col for col in df.columns if col != "Row Label"]
            df = self.consolidation_engine.calculate_changes(df, periods)
        
        return {
            "query_type": "comparison",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "periods_compared": parsed_query.time_periods
        }
    
    def _handle_trend(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 3: Trend Query."""
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        filters.pop("period_quarter", None)
        filters.pop("period_label", None)
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        df = self.consolidation_engine.consolidate_same_table_different_periods(results)
        
        return {
            "query_type": "trend",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "metrics": parsed_query.financial_concepts
        }
    
    def _handle_aggregation(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 4: Aggregation Query."""
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        values = []
        for result in results:
            metadata = result.get("metadata", {})
            value_numeric = metadata.get("value_numeric")
            if value_numeric is not None:
                values.append({
                    "value": value_numeric,
                    "period": metadata.get("period_label"),
                    "metric": metadata.get("row_label")
                })
        
        numeric_values = [v["value"] for v in values]
        
        aggregations = {}
        if numeric_values:
            aggregations = {
                "count": len(numeric_values),
                "sum": sum(numeric_values),
                "average": sum(numeric_values) / len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values)
            }
        
        return {
            "query_type": "aggregation",
            "query": parsed_query.original_query,
            "aggregations": aggregations,
            "values": values,
            "operation": parsed_query.operations[0] if parsed_query.operations else "aggregate"
        }
    
    def _handle_multi_document(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 5: Multi-Document Consolidation."""
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        filters.pop("document_id", None)
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        df = self.consolidation_engine.consolidate_same_table_different_periods(results)
        
        documents = set()
        for result in results:
            metadata = result.get("metadata", {})
            documents.add(metadata.get("filename", "Unknown"))
        
        return {
            "query_type": "multi_document",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "documents_included": list(documents),
            "document_count": len(documents)
        }
    
    def _handle_cross_table(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 6: Cross-Table Query."""
        results_by_table = {}
        
        for table_type in parsed_query.table_types:
            search_text = " ".join(parsed_query.financial_concepts)
            
            filters = parsed_query.metadata_filters.copy()
            filters["table_type"] = table_type
            filters["embedding_level"] = "row"
            
            results_with_scores = self.vector_store.similarity_search_with_score(
                query=search_text,
                k=top_k // len(parsed_query.table_types),
                filter=filters
            )
            
            results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
            results_by_table[table_type] = results
        
        df = self.consolidation_engine.consolidate_cross_table(results_by_table)
        
        return {
            "query_type": "cross_table",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "tables_included": parsed_query.table_types
        }
    
    def _handle_hierarchical(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """Handle Type 7: Hierarchical Query."""
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        parent_results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=5,
            filter=filters
        )
        parent_results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in parent_results_with_scores]
        
        if not parent_results:
            return {
                "query_type": "hierarchical",
                "query": parsed_query.original_query,
                "error": "No matching parent row found"
            }
        
        parent_label = parent_results[0].get("metadata", {}).get("row_label")
        
        filters["parent_row"] = parent_label
        child_results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        child_results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in child_results_with_scores]
        
        all_results = parent_results[:1] + child_results
        
        df = self.consolidation_engine.consolidate_hierarchical(all_results)
        
        return {
            "query_type": "hierarchical",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "parent_item": parent_label,
            "child_count": len(child_results)
        }


def get_query_processor(
    vector_store: Optional["VectorDBManager"] = None,
    **kwargs
) -> QueryProcessor:
    """
    Get or create global query processor instance.
    
    Thread-safe singleton accessor.
    
    Args:
        vector_store: VectorDBManager instance (only used on first call)
        **kwargs: Additional arguments
        
    Returns:
        QueryProcessor singleton instance
    """
    return QueryProcessor(vector_store=vector_store, **kwargs)


def reset_query_processor() -> None:
    """
    Reset the query processor singleton.
    
    Useful for testing or reconfiguration.
    """
    QueryProcessor._reset_instance()
