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
    },
    # ============================================================================
    # TABLE CONSOLIDATION EXAMPLES
    # ============================================================================
    {
        "question": "Show me net revenues for all quarters from 2020 to 2025 and save as CSV",
        "context": "Found net revenues data across multiple quarters: Q1-Q4 2020, Q1-Q4 2021, Q1-Q4 2022, Q1-Q4 2023, Q1-Q4 2024, Q1-Q2 2025",
        "answer": "I've consolidated net revenues across all quarters from 2020 to 2025 into a time-series table with dates as columns (2020-03-31, 2020-06-30, etc.). The table has been saved as CSV to outputs/consolidated_tables/net_revenues_2020_2025.csv. The data shows quarterly progression with values ranging from $10,234M (Q1 2020) to $15,234M (Q2 2025). (Source: Multiple 10-Q and 10-K filings, 2020-2025)"
    },
    {
        "question": "Consolidate total assets from 2022 to 2024 and export to Excel with transpose",
        "context": "Total assets data available for year-ends: Dec 31 2022, Dec 31 2023, Dec 31 2024",
        "answer": "I've consolidated total assets for 2022-2024 and transposed the table so years are in rows and metrics in columns. The Excel file has been saved to outputs/consolidated_tables/total_assets_2022_2024.xlsx. The data shows: 2022: $1,234,567M, 2023: $1,345,678M, 2024: $1,456,789M, representing steady growth. (Source: 10-K filings 2022-2024, Consolidated Balance Sheets)"
    },
    {
        "question": "Get me a consolidated view of net income across all available years",
        "context": "Net income data found for: 2020, 2021, 2022, 2023, 2024, 2025 (partial)",
        "answer": "I've created a consolidated time-series table of net income across all available years (2020-2025). The table uses year-end dates as column headers (2020-12-31, 2021-12-31, etc.) and has been saved as CSV. Key insights: Net income grew from $8,123M (2020) to $14,567M (2024), a 79% increase over 4 years. (Source: 10-K Annual Reports 2020-2024, Consolidated Statements of Income)"
    },
    {
        "question": "Compare investment banking revenues quarterly from Q1 2023 to Q2 2025 and save as Excel",
        "context": "Investment banking revenue data available for Q1 2023 through Q2 2025 (10 quarters)",
        "answer": "I've consolidated investment banking revenues for 10 quarters (Q1 2023 - Q2 2025) into a time-series Excel file saved at outputs/consolidated_tables/investment_banking_revenues_Q1_2023_Q2_2025.xlsx. The table shows quarterly dates (2023-03-31, 2023-06-30, etc.) with values ranging from $1,123M to $1,456M. Notable trend: 18% growth from Q1 2023 to Q2 2025. (Source: 10-Q filings Q1 2023 - Q2 2025, Business Segment data)"
    },
    {
        "question": "Show total liabilities trend from 2020-2024 in CSV format with dates",
        "context": "Total liabilities data: 2020-12-31, 2021-12-31, 2022-12-31, 2023-12-31, 2024-12-31",
        "answer": "I've created a time-series CSV file of total liabilities from 2020-2024 with year-end dates as columns. File saved to outputs/consolidated_tables/total_liabilities_2020_2024.csv. The data shows: 2020: $987,654M, 2021: $1,012,345M, 2022: $1,098,765M, 2023: $1,156,789M, 2024: $1,234,567M. This represents a 25% increase over the 4-year period. (Source: 10-K Annual Reports 2020-2024, Consolidated Balance Sheets)"
    },
    {
        "question": "Consolidate cash and cash equivalents for all quarters and transpose the table",
        "context": "Cash data available for all quarters from Q1 2020 to Q2 2025 (22 quarters)",
        "answer": "I've consolidated cash and cash equivalents across 22 quarters (Q1 2020 - Q2 2025) and transposed the table with quarters in rows. Saved as outputs/consolidated_tables/cash_equivalents_all_quarters_transposed.xlsx. The transposed format makes it easier to see the progression: Starting at $45,678M (Q1 2020) and ending at $67,890M (Q2 2025), showing strong liquidity growth. (Source: 10-Q and 10-K filings 2020-2025, Consolidated Balance Sheets)"
    },
    {
        "question": "Give me shareholders equity from 2021 to 2025 as a time series Excel file",
        "context": "Shareholders equity data: 2021, 2022, 2023, 2024, 2025 year-ends",
        "answer": "I've created a time-series Excel file of shareholders equity for 2021-2025 with year-end dates (2021-12-31 through 2025-12-31) as column headers. File saved to outputs/consolidated_tables/shareholders_equity_2021_2025.xlsx. Values show consistent growth: $78,901M (2021) to $95,678M (2025), a 21% increase. (Source: 10-K Annual Reports 2021-2025, Consolidated Balance Sheets, Equity section)"
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
