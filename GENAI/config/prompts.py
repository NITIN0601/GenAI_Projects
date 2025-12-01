"""
Prompt templates using LangChain.

Industry standard: Prompt Management
- Uses PromptTemplate and ChatPromptTemplate
- Type-checked inputs
- Reusable templates
"""

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Financial Analysis Prompt
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

# HyDE Prompt
HYDE_TEMPLATE = """Given the following question about financial data, write a detailed, factual answer as it would appear in a 10-K or 10-Q SEC filing.

Question: {query}

Write a paragraph that would answer this question in a financial document (focus on facts, numbers, and financial terminology):"""

HYDE_PROMPT = PromptTemplate(
    template=HYDE_TEMPLATE,
    input_variables=["query"]
)

# Multi-Query Prompt
MULTI_QUERY_TEMPLATE = """You are an AI assistant helping to improve search results for financial data queries.

Given a user question, generate {num_queries} different versions of the question that could help find relevant information in financial documents.

Original question: {query}

Generate {num_queries} alternative phrasings or related questions (one per line):"""

MULTI_QUERY_PROMPT = PromptTemplate(
    template=MULTI_QUERY_TEMPLATE,
    input_variables=["num_queries", "query"]
)

# Citation Prompt
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

# Table Comparison Prompt
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

# Metadata Extraction Prompt
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
# ADVANCED PROMPTING TECHNIQUES
# ============================================================================

# Chain-of-Thought (CoT) Prompt
COT_TEMPLATE = """You are a financial analyst assistant. Answer the question step-by-step, showing your reasoning.

Context from financial tables:
{context}

Question: {question}

Let's think through this step-by-step:
1. Identify the relevant data in the context
2. Perform any necessary calculations
3. Formulate a complete answer
4. Cite your sources with document name, table, and page number

Step-by-step reasoning:"""

COT_PROMPT = PromptTemplate(
    template=COT_TEMPLATE,
    input_variables=["context", "question"]
)

# ReAct-style Prompt (Reasoning + Acting)
REACT_TEMPLATE = """You are a financial analyst assistant that can reason about and answer questions.

Context:
{context}

Question: {question}

Think step-by-step about how to answer this question:

Thought 1: What information do I need from the context?
Action 1: Identify relevant tables and data points
Observation 1: [Extract key data]

Thought 2: What calculations or comparisons are needed?
Action 2: Perform analysis
Observation 2: [Show results]

Thought 3: What is the final answer?
Action 3: Formulate response with citations

Final Answer:"""

REACT_PROMPT = PromptTemplate(
    template=REACT_TEMPLATE,
    input_variables=["context", "question"]
)
