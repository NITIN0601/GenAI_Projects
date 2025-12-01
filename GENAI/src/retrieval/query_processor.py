"""
Complete query processing pipeline.
Orchestrates query understanding, vector search, and table consolidation.
"""

from typing import List, Dict, Any, Optional
import pandas as pd

from src.retrieval.query_understanding import QueryUnderstanding, QueryType, ParsedQuery, get_query_understanding
from src.rag.consolidation.multi_year import TableConsolidationEngine, get_consolidation_engine
from src.models.schemas import RAGQuery, RAGResponse
from src.retrieval.retriever import get_retriever
from src.llm.manager import get_llm_manager
from src.cache.backends.redis_cache import get_redis_cache
from src.vector_store.stores.chromadb_store import VectorStore, get_vector_store
from src.embeddings.manager import get_embedding_manager


class QueryProcessor:
    """
    Complete query processing pipeline.
    Handles all 7 query types with intelligent routing.
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        query_understanding: Optional[QueryUnderstanding] = None,
        consolidation_engine: Optional[TableConsolidationEngine] = None
    ):
        """Initialize query processor with components."""
        self.vector_store = vector_store or get_vector_store()
        self.query_understanding = query_understanding or get_query_understanding()
        self.consolidation_engine = consolidation_engine or get_consolidation_engine()
        self.embedding_manager = get_embedding_manager()
    
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
        """
        Handle Type 1: Specific Value Query.
        Example: "What was net revenue in Q1 2025?"
        """
        # Build search query
        search_text = " ".join(parsed_query.financial_concepts + parsed_query.time_periods)
        
        # Search at row level
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        # Search at row level
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        # Extract specific values
        values = []
        # Convert to list of dicts for consistency
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
            "values": values[:5],  # Top 5 most relevant
            "total_results": len(results)
        }
    
    def _handle_comparison(
        self,
        parsed_query: ParsedQuery,
        top_k: int
    ) -> Dict[str, Any]:
        """
        Handle Type 2: Comparison Query.
        Example: "Compare net revenues between Q1 2025 and Q1 2024"
        """
        # Search for the metric across periods
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        # Convert to list of dicts
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        # Consolidate into comparison table
        df = self.consolidation_engine.consolidate_same_table_different_periods(results)
        
        # Calculate changes if we have multiple periods
        if len(df.columns) > 2:  # Row Label + at least 2 periods
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
        """
        Handle Type 3: Trend Query.
        Example: "Show net revenue trend for last 4 quarters"
        """
        # Search for metric across all periods
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        # Remove specific period filter to get all periods
        filters.pop("period_quarter", None)
        filters.pop("period_label", None)
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        # Convert to list of dicts
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        # Consolidate and sort by period
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
        """
        Handle Type 4: Aggregation Query.
        Example: "What was average revenue across all quarters?"
        """
        # Get all values for the metric
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        # Convert to list of dicts
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        # Extract numeric values
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
        
        # Calculate aggregations
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
        """
        Handle Type 5: Multi-Document Consolidation.
        Example: "Show net revenues from all documents"
        """
        # Search across all documents
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        # Remove document-specific filters
        filters.pop("document_id", None)
        
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        
        # Convert to list of dicts
        results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
        
        # Consolidate by period
        df = self.consolidation_engine.consolidate_same_table_different_periods(results)
        
        # Get unique documents
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
        """
        Handle Type 6: Cross-Table Query.
        Example: "Show revenues from income statement and cash from cash flow statement"
        """
        # Search for each table type separately
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
            
            # Convert to list of dicts
            results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in results_with_scores]
            
            results_by_table[table_type] = results
        
        # Consolidate cross-table results
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
        """
        Handle Type 7: Hierarchical Query.
        Example: "Show me all revenue line items and their sub-items"
        """
        # Search for parent row
        search_text = " ".join(parsed_query.financial_concepts)
        
        filters = parsed_query.metadata_filters.copy()
        filters["embedding_level"] = "row"
        
        # First, find the parent row
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
        
        # Get the parent row label
        parent_label = parent_results[0].get("metadata", {}).get("row_label")
        
        # Now search for all child rows
        filters["parent_row"] = parent_label
        child_results_with_scores = self.vector_store.similarity_search_with_score(
            query=search_text,
            k=top_k,
            filter=filters
        )
        child_results = [{"metadata": doc.metadata, "content": doc.page_content} for doc, _ in child_results_with_scores]
        
        # Combine parent and children
        all_results = parent_results[:1] + child_results
        
        # Consolidate with hierarchy preserved
        df = self.consolidation_engine.consolidate_hierarchical(all_results)
        
        return {
            "query_type": "hierarchical",
            "query": parsed_query.original_query,
            "table": df.to_dict(orient="records"),
            "table_html": df.to_html(index=False),
            "parent_item": parent_label,
            "child_count": len(child_results)
        }


# Singleton instance
_query_processor = None

def get_query_processor() -> QueryProcessor:
    """Get singleton query processor."""
    global _query_processor
    if _query_processor is None:
        _query_processor = QueryProcessor()
    return _query_processor
