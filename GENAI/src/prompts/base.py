"""
Core financial analysis prompt templates.

This module contains the base prompts for financial Q&A, table analysis,
metadata extraction, and citation formatting.
"""

from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)


# ============================================================================
# FINANCIAL ANALYSIS PROMPTS
# ============================================================================

FINANCIAL_ANALYSIS_TEMPLATE = """You are a financial analyst assistant. Answer questions based on the provided financial data from SEC filings (10-K and 10-Q reports).

Context from financial tables:
{context}

Question: {question}

Instructions:
1. Provide accurate answers based ONLY on the provided context
2. If the information is not in the context, say "I don't have that information"
3. Always cite the source (table name, page number, and document)
4. For numerical data, include the exact values and units
5. Be concise but complete

Answer:"""

FINANCIAL_ANALYSIS_PROMPT = PromptTemplate(
    template=FINANCIAL_ANALYSIS_TEMPLATE,
    input_variables=["context", "question"]
)


# Chat Prompt Version (for ChatModels)
FINANCIAL_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "You are a financial analyst assistant. Answer questions based on the provided financial data."
    ),
    HumanMessagePromptTemplate.from_template(
        """Context:
{context}

Question: {question}

Provide accurate answers based ONLY on the context. Cite sources."""
    )
])


# ============================================================================
# TABLE ANALYSIS PROMPTS
# ============================================================================

TABLE_COMPARISON_TEMPLATE = """Compare the following financial tables and highlight key differences.

Table 1:
{table1}

Table 2:
{table2}

Focus on:
1. Significant changes in values
2. New or missing line items
3. Trends over time

Comparison:"""

TABLE_COMPARISON_PROMPT = PromptTemplate(
    template=TABLE_COMPARISON_TEMPLATE,
    input_variables=["table1", "table2"]
)


# ============================================================================
# METADATA EXTRACTION PROMPTS
# ============================================================================

METADATA_EXTRACTION_TEMPLATE = """Extract the following metadata from the text:
- Year
- Quarter
- Table Title
- Report Type (10-K/10-Q)

Text:
{text}

Return JSON format."""

METADATA_EXTRACTION_PROMPT = PromptTemplate(
    template=METADATA_EXTRACTION_TEMPLATE,
    input_variables=["text"]
)


# ============================================================================
# CITATION PROMPTS
# ============================================================================

CITATION_TEMPLATE = """Format the following answer with proper citations based on the metadata.

Answer: {answer}
Metadata: {metadata}

Format:
[Answer text]
(Source: [Document Name], Page [Page Number], Table [Table Name])"""

CITATION_PROMPT = PromptTemplate(
    template=CITATION_TEMPLATE,
    input_variables=["answer", "metadata"]
)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'FINANCIAL_ANALYSIS_PROMPT',
    'FINANCIAL_CHAT_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT',
]
