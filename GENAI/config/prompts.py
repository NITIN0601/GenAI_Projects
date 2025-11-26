"""Prompt templates for financial analysis."""

FINANCIAL_ANALYSIS_PROMPT = """You are a financial analyst assistant. Answer questions based on the provided financial data from SEC filings (10-K and 10-Q reports).

Context from financial tables:
{context}

Question: {question}

Instructions:
1. Provide accurate answers based ONLY on the provided context
2. If the information is not in the context, say "I don't have that information in the provided data"
3. Always cite the source (table name, page number, and document)
4. For numerical data, include the exact values and units
5. Be concise but complete

Answer:"""

TABLE_COMPARISON_PROMPT = """You are analyzing financial tables from multiple periods. Compare the data and provide insights.

Tables:
{context}

Question: {question}

Instructions:
1. Compare values across different periods (quarters/years)
2. Calculate percentage changes where relevant
3. Highlight significant trends or anomalies
4. Cite specific tables and periods
5. Use clear formatting for numbers

Analysis:"""

METADATA_EXTRACTION_PROMPT = """Extract structured metadata from this table title and context.

Table Title: {title}
Page Number: {page_no}
Document: {filename}

Extract:
- Table Type (Balance Sheet, Income Statement, Cash Flow, etc.)
- Fiscal Period (if mentioned)
- Any specific categories or subcategories

Return as JSON."""

CITATION_PROMPT = """Format the answer with proper citations.

Answer: {answer}
Sources: {sources}

Format as:
[Answer text]

Sources:
- [Table Name] (Page X, Document Y)
"""
