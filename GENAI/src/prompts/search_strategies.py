"""
Retrieval strategy prompt templates.

This module contains prompts for advanced retrieval strategies:
- HyDE (Hypothetical Document Embeddings)
- Multi-Query (Query Expansion)
"""

from langchain_core.prompts import PromptTemplate


# ============================================================================
# HYDE PROMPT
# ============================================================================

HYDE_TEMPLATE = """Given the following question about financial data, write a detailed, factual answer as it would appear in a 10-K or 10-Q SEC filing.

Question: {query}

Write a paragraph that would answer this question in a financial document (focus on facts, numbers, and financial terminology):"""

HYDE_PROMPT = PromptTemplate(
    template=HYDE_TEMPLATE,
    input_variables=["query"]
)


# ============================================================================
# MULTI-QUERY PROMPT
# ============================================================================

MULTI_QUERY_TEMPLATE = """You are an AI assistant helping to improve search results for financial data queries.

Given a user question, generate {num_queries} different versions of the question that could help find relevant information in financial documents (10-K, 10-Q filings).

Original question: {query}

Generate {num_queries} alternative phrasings or related questions (one per line):
1."""

MULTI_QUERY_PROMPT = PromptTemplate(
    template=MULTI_QUERY_TEMPLATE,
    input_variables=["num_queries", "query"]
)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'HYDE_PROMPT',
    'MULTI_QUERY_PROMPT',
]
