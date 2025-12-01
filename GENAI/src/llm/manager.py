"""LLM manager using LangChain and Ollama."""

from typing import Optional, Any, List
import logging
from langchain_ollama import ChatOllama
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMManager:
    """
    LLM integration using LangChain and Ollama.
    
    Wraps LangChain's ChatOllama to provide a unified interface
    compatible with the rest of the application while leveraging
    LangChain's capabilities.
    """
    
    def __init__(
        self, 
        model_name: Optional[str] = None, 
        base_url: Optional[str] = None,
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ):
        """
        Initialize LLM manager.
        
        Args:
            model_name: Ollama model name
            base_url: Ollama API base URL
            callbacks: LangChain callbacks
        """
        self.model_name = model_name or settings.LLM_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.callbacks = callbacks or []
        
        logger.info(f"Initializing LangChain LLM with model: {self.model_name}")
        
        # Initialize LangChain ChatOllama
        self.llm: BaseChatModel = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=settings.LLM_TEMPERATURE,
            callbacks=self.callbacks,
            keep_alive="5m"  # Keep model loaded for 5 minutes
        )
        
    def generate(
        self,
        prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response using LangChain.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (override)
            max_tokens: Maximum tokens (override)
            stream: Whether to stream (not fully supported in this wrapper yet)
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        # Update runtime settings if needed
        if temperature is not None:
            self.llm.temperature = temperature
            
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise e

    def get_langchain_model(self) -> BaseChatModel:
        """Return the underlying LangChain model object."""
        return self.llm
        
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        try:
            # Simple ping
            self.llm.invoke("test")
            return True
        except Exception:
            return False


# Global LLM manager instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get or create global LLM manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
