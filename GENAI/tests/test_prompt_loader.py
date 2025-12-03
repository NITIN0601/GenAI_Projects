"""
Test PromptLoader.
"""

import sys
import os
import unittest

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.prompts.loader import get_prompt_loader
from src.prompts.base import FINANCIAL_ANALYSIS_PROMPT, FINANCIAL_CHAT_PROMPT
from src.prompts.advanced import COT_PROMPT
from src.prompts.few_shot import FINANCIAL_EXAMPLES

class TestPromptLoader(unittest.TestCase):
    def setUp(self):
        self.loader = get_prompt_loader()

    def test_loader_initialization(self):
        self.assertIsNotNone(self.loader)
        self.assertTrue(len(self.loader._prompts) > 0)

    def test_get_prompt_template(self):
        prompt = self.loader.get_prompt_template("financial_analysis")
        self.assertIsNotNone(prompt)
        self.assertIn("financial analyst assistant", prompt.template)
        self.assertIn("context", prompt.input_variables)

    def test_base_prompts_loaded(self):
        self.assertIsNotNone(FINANCIAL_ANALYSIS_PROMPT)
        self.assertIsNotNone(FINANCIAL_CHAT_PROMPT)
        # Check if template content is correct
        self.assertIn("financial analyst assistant", FINANCIAL_ANALYSIS_PROMPT.template)

    def test_advanced_prompts_loaded(self):
        self.assertIsNotNone(COT_PROMPT)
        self.assertIn("Step-by-step reasoning", COT_PROMPT.template)

    def test_few_shot_examples_loaded(self):
        self.assertTrue(len(FINANCIAL_EXAMPLES) > 0)
        self.assertIn("question", FINANCIAL_EXAMPLES[0])
        self.assertIn("context", FINANCIAL_EXAMPLES[0])
        self.assertIn("answer", FINANCIAL_EXAMPLES[0])

if __name__ == '__main__':
    unittest.main()
