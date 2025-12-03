"""
Few-shot learning components for financial query prompting.

Provides curated examples to improve LLM response quality through in-context learning.

Refactored to load examples from config/prompts.yaml via PromptLoader.
"""

from typing import List, Dict, Optional
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.example_selectors import SemanticSimilarityExampleSelector

from src.prompts.loader import get_prompt_loader

# Initialize loader
_loader = get_prompt_loader()

# ============================================================================
# CURATED FEW-SHOT EXAMPLES
# ============================================================================

# Load examples from loader
FINANCIAL_EXAMPLES = _loader.get_few_shot_examples()


# Example template for formatting
EXAMPLE_TEMPLATE = _loader.get_raw_prompt("few_shot_example")
if not EXAMPLE_TEMPLATE:
    # Fallback if not found in config
    EXAMPLE_TEMPLATE = """
Question: {question}
Context: {context}
Answer: {answer}
"""

# Suffix template
SUFFIX_TEMPLATE = _loader.get_raw_prompt("few_shot_suffix")
if not SUFFIX_TEMPLATE:
    SUFFIX_TEMPLATE = "Now answer this question using the context provided:\n\nQuestion: {question}\nContext: {context}\nAnswer:"


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
                suffix=SUFFIX_TEMPLATE,
                input_variables=["question", "context"]
            )
        else:
            # Static examples
            prompt = FewShotPromptTemplate(
                examples=self.examples[:self.k],
                example_prompt=example_prompt,
                suffix=SUFFIX_TEMPLATE,
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
