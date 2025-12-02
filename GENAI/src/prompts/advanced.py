"""
Advanced prompting techniques.

This module contains prompts for advanced reasoning techniques:
- Chain-of-Thought (CoT)
- ReAct (Reasoning + Acting)
"""

from langchain_core.prompts import PromptTemplate


# ============================================================================
# CHAIN-OF-THOUGHT (CoT) PROMPT
# ============================================================================

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


# ============================================================================
# REACT-STYLE PROMPT (Reasoning + Acting)
# ============================================================================

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


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'COT_PROMPT',
    'REACT_PROMPT',
]
