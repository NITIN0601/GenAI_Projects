"""
Prompt Loader Module.

Responsible for loading prompt templates and few-shot examples from the YAML configuration.
Implements a Singleton pattern with caching to ensure prompts are loaded and created only once.
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
    
    Features:
    - Loads prompts once from YAML on first access
    - Caches created PromptTemplate objects for performance
    - Provides lazy loading of individual prompts
    """
    _instance = None
    _prompts: Dict[str, Any] = {}
    _few_shot_examples: List[Dict[str, str]] = []
    
    # Cache for created PromptTemplate objects
    _template_cache: Dict[str, PromptTemplate] = {}
    _chat_template_cache: Dict[str, ChatPromptTemplate] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            cls._instance._load_prompts()
        return cls._instance

    def _load_prompts(self):
        """Load prompts from YAML file."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "config", "prompts.yaml")
        
        if not os.path.exists(config_path):
            logger.error(f"Prompts configuration file not found at {config_path}")
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
        Get a LangChain PromptTemplate by name (cached).
        
        Args:
            prompt_name: Name of the prompt in the YAML config
            
        Returns:
            PromptTemplate object or None if not found
        """
        # Check cache first
        if prompt_name in self._template_cache:
            return self._template_cache[prompt_name]
        
        prompt_config = self._prompts.get(prompt_name)
        if not prompt_config:
            logger.warning(f"Prompt '{prompt_name}' not found in configuration")
            return None
        
        # Create and cache
        template = PromptTemplate(
            template=prompt_config['template'],
            input_variables=prompt_config.get('input_variables', [])
        )
        self._template_cache[prompt_name] = template
        return template

    def get_chat_prompt_template(self, system_prompt_name: str, human_prompt_name: str) -> Optional[ChatPromptTemplate]:
        """
        Get a LangChain ChatPromptTemplate by combining system and human prompts (cached).
        
        Args:
            system_prompt_name: Name of the system prompt in YAML
            human_prompt_name: Name of the human prompt in YAML
            
        Returns:
            ChatPromptTemplate object
        """
        cache_key = f"{system_prompt_name}:{human_prompt_name}"
        
        # Check cache first
        if cache_key in self._chat_template_cache:
            return self._chat_template_cache[cache_key]
        
        system_config = self._prompts.get(system_prompt_name)
        human_config = self._prompts.get(human_prompt_name)
        
        if not system_config or not human_config:
            logger.warning(f"Prompts '{system_prompt_name}' or '{human_prompt_name}' not found")
            return None
        
        # Create and cache
        template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_config['template']),
            HumanMessagePromptTemplate.from_template(human_config['template'])
        ])
        self._chat_template_cache[cache_key] = template
        return template

    def get_raw_prompt(self, prompt_name: str) -> Optional[str]:
        """Get the raw template string."""
        prompt_config = self._prompts.get(prompt_name)
        if not prompt_config:
            return None
        return prompt_config['template']

    def get_few_shot_examples(self) -> List[Dict[str, str]]:
        """Get the list of few-shot examples."""
        return self._few_shot_examples
    
    def clear_cache(self):
        """Clear all cached templates (useful for testing/reloading)."""
        self._template_cache.clear()
        self._chat_template_cache.clear()
        logger.info("Prompt template cache cleared")


# Global accessor
def get_prompt_loader() -> PromptLoader:
    """Get the global PromptLoader instance."""
    return PromptLoader()
