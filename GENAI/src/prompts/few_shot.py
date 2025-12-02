"""
Few-shot learning components for financial query prompting.

Provides curated examples to improve LLM response quality through in-context learning.
"""

from typing import List, Dict, Optional
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.example_selectors import SemanticSimilarityExampleSelector


# ============================================================================
# CURATED FEW-SHOT EXAMPLES
# ============================================================================

FINANCIAL_EXAMPLES = [
    {
        "question": "What was the total revenue in Q1 2024?",
        "context": "Consolidated Statement of Income - Q1 2024\nNet revenues: $15,234 million",
        "answer": "The total net revenues in Q1 2024 were $15,234 million. (Source: 10-Q Q1 2024, Consolidated Statement of Income, Page 5)"
    },
    {
        "question": "Compare net income between Q1 2024 and Q1 2023",
        "context": "Net Income: Q1 2024: $3,456M | Q1 2023: $3,123M",
        "answer": "Net income increased by $333 million (10.7%) from $3,123 million in Q1 2023 to $3,456 million in Q1 2024. This represents solid year-over-year growth. (Source: Consolidated Statement of Income, 10-Q Q1 2024)"
    },
    {
        "question": "What were the total assets as of March 31, 2024?",
        "context": "Consolidated Balance Sheet - March 31, 2024\nTotal assets: $1,234,567 million",
        "answer": "Total assets as of March 31, 2024 were $1,234,567 million. (Source: 10-Q Q1 2024, Consolidated Balance Sheet, Page 3)"
    },
    {
        "question": "How did investment banking revenues perform in Q2 2024?",
        "context": "Business Segments - Q2 2024\nInvestment Banking: Advisory: $456M, Underwriting: $789M, Total: $1,245M",
        "answer": "Investment banking revenues in Q2 2024 totaled $1,245 million, comprising $456 million from advisory services and $789 million from underwriting activities. (Source: 10-Q Q2 2024, Business Segments, Page 12)"
    },
    {
        "question": "What was the percentage change in trading revenues?",
        "context": "Trading Revenues: Q1 2024: $5,678M | Q4 2023: $4,890M | Change: +$788M (+16.1%)",
        "answer": "Trading revenues increased by 16.1%, rising from $4,890 million in Q4 2023 to $5,678 million in Q1 2024, an increase of $788 million. (Source: 10-Q Q1 2024, Revenue Analysis)"
    },
    {
        "question": "What is the company's tier 1 capital ratio?",
        "context": "Regulatory Capital Ratios - Q1 2024\nCommon Equity Tier 1 (CET1) ratio: 15.2%",
        "answer": "The Common Equity Tier 1 (CET1) capital ratio was 15.2% as of Q1 2024, which is well above regulatory minimum requirements. (Source: 10-Q Q1 2024, Regulatory Capital, Page 45)"
    },
    {
        "question": "How many employees does the company have?",
        "context": "Employees: March 31, 2024: 80,000 | December 31, 2023: 78,500",
        "answer": "As of March 31, 2024, the company had approximately 80,000 employees, an increase of 1,500 from 78,500 at year-end 2023. (Source: 10-Q Q1 2024, Page 2)"
    },
    {
        "question": "What was the return on equity?",
        "context": "Performance Metrics - Q1 2024\nNet income: $3,456M | Average shareholders' equity: $92,000M | ROE: 15.0%",
        "answer": "The return on equity (ROE) for Q1 2024 was 15.0%, calculated as net income of $3,456 million divided by average shareholders' equity of $92,000 million (annualized). (Source: 10-Q Q1 2024, Financial Highlights)"
    }
]


# Example template for formatting
EXAMPLE_TEMPLATE = """
Question: {question}
Context: {context}
Answer: {answer}
"""


# ============================================================================
# FEW-SHOT MANAGER
# ============================================================================

class FewShotManager:
    """
    Manages few-shot examples for financial queries.
    
    Provides semantic similarity-based example selection to dynamically
    choose the most relevant examples for a given query.
    """
    
    def __init__(self, embedding_function=None, k: int = 3):
        """
        Initialize few-shot manager.
        
        Args:
            embedding_function: Embedding function for semantic similarity
            k: Number of examples to retrieve
        """
        self.k = k
        self.examples = FINANCIAL_EXAMPLES
        self.embedding_function = embedding_function
        self._example_selector = None
    
    def get_example_selector(self):
        """Get or create semantic similarity example selector."""
        if self._example_selector is None and self.embedding_function:
            try:
                from langchain_community.vectorstores import FAISS
                
                self._example_selector = SemanticSimilarityExampleSelector.from_examples(
                    self.examples,
                    self.embedding_function,
                    FAISS,
                    k=self.k
                )
            except Exception as e:
                # Fallback to returning all examples if selector fails
                pass
        
        return self._example_selector
    
    def get_examples(self, query: str) -> List[Dict]:
        """
        Get relevant examples for a query.
        
        Args:
            query: User query
            
        Returns:
            List of relevant examples
        """
        selector = self.get_example_selector()
        
        if selector:
            # Use semantic similarity
            return selector.select_examples({"question": query})
        else:
            # Fallback: return first k examples
            return self.examples[:self.k]
    
    def get_few_shot_prompt(self) -> FewShotPromptTemplate:
        """
        Get few-shot prompt template.
        
        Returns:
            FewShotPromptTemplate configured with examples
        """
        example_prompt = PromptTemplate.from_template(EXAMPLE_TEMPLATE)
        
        selector = self.get_example_selector()
        
        if selector:
            # Dynamic example selection
            prompt = FewShotPromptTemplate(
                example_selector=selector,
                example_prompt=example_prompt,
                suffix="Now answer this question using the context provided:\n\nQuestion: {question}\nContext: {context}\nAnswer:",
                input_variables=["question", "context"]
            )
        else:
            # Static examples
            prompt = FewShotPromptTemplate(
                examples=self.examples[:self.k],
                example_prompt=example_prompt,
                suffix="Now answer this question using the context provided:\n\nQuestion: {question}\nContext: {context}\nAnswer:",
                input_variables=["question", "context"]
            )
        
        return prompt


# Global instance
_few_shot_manager: Optional[FewShotManager] = None


def get_few_shot_manager(embedding_function=None) -> FewShotManager:
    """Get global few-shot manager instance."""
    global _few_shot_manager
    if _few_shot_manager is None:
        _few_shot_manager = FewShotManager(embedding_function=embedding_function)
    return _few_shot_manager


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'FINANCIAL_EXAMPLES',
    'EXAMPLE_TEMPLATE',
    'FewShotManager',
    'get_few_shot_manager',
]
