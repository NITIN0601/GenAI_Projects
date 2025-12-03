"""
Prompt Loader Module.

Responsible for loading prompt templates and few-shot examples from the YAML configuration.
Implements a Singleton pattern to ensure prompts are loaded only once.
"""

import os
import yaml
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

try:
    from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
except ImportError:
    try:
        from langchain.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
    except ImportError:
        logger.error("LangChain not found. Please install langchain-core or langchain.")
        raise


class PromptLoader:
    """
    Singleton class to load and manage prompt templates from configuration.
    """
    _instance = None
    _prompts: Dict[str, Any] = {}
    _few_shot_examples: List[Dict[str, str]] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            cls._instance._load_prompts()
        return cls._instance

    def _load_prompts(self):
        """Load prompts from YAML file."""
        # Determine path to prompts.yaml
        # Assuming config/prompts.yaml is relative to the project root
        # We can try to find it relative to this file or use a setting
        
        # Try to find config directory relative to project root
        # This file is in src/prompts/loader.py -> ../../config/prompts.yaml
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "config", "prompts.yaml")
        
        if not os.path.exists(config_path):
            logger.error(f"Prompts configuration file not found at {config_path}")
            # Fallback or raise error? For now, we'll log and keep empty
            return

        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                
            self._prompts = data.get('prompts', {})
            self._few_shot_examples = data.get('few_shot_examples', [])
            
            logger.info(f"Loaded {len(self._prompts)} prompts and {len(self._few_shot_examples)} few-shot examples from {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load prompts configuration: {e}")

    def get_prompt_template(self, prompt_name: str) -> Optional[PromptTemplate]:
        """
        Get a LangChain PromptTemplate by name.
        
        Args:
            prompt_name: Name of the prompt in the YAML config
            
        Returns:
            PromptTemplate object or None if not found
        """
        prompt_config = self._prompts.get(prompt_name)
        if not prompt_config:
            logger.warning(f"Prompt '{prompt_name}' not found in configuration")
            return None
            
        return PromptTemplate(
            template=prompt_config['template'],
            input_variables=prompt_config.get('input_variables', [])
        )

    def get_chat_prompt_template(self, system_prompt_name: str, human_prompt_name: str) -> Optional[ChatPromptTemplate]:
        """
        Get a LangChain ChatPromptTemplate by combining system and human prompts.
        
        Args:
            system_prompt_name: Name of the system prompt in YAML
            human_prompt_name: Name of the human prompt in YAML
            
        Returns:
            ChatPromptTemplate object
        """
        system_config = self._prompts.get(system_prompt_name)
        human_config = self._prompts.get(human_prompt_name)
        
        if not system_config or not human_config:
            logger.warning(f"Prompts '{system_prompt_name}' or '{human_prompt_name}' not found")
            return None
            
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_config['template']),
            HumanMessagePromptTemplate.from_template(human_config['template'])
        ])

    def get_raw_prompt(self, prompt_name: str) -> Optional[str]:
        """Get the raw template string."""
        prompt_config = self._prompts.get(prompt_name)
        if not prompt_config:
            return None
        return prompt_config['template']

    def get_few_shot_examples(self) -> List[Dict[str, str]]:
        """Get the list of few-shot examples."""
        return self._few_shot_examples


# Global accessor
def get_prompt_loader() -> PromptLoader:
    """Get the global PromptLoader instance."""
    return PromptLoader()
