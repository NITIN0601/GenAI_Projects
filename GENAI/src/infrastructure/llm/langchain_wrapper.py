"""
LangChain Wrappers for Custom LLM Providers.

Provides adapter classes to make custom API providers compatible with
LangChain's BaseChatModel interface.
"""

from typing import Optional, Any, List

from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration

from src.utils import get_logger

logger = get_logger(__name__)


class CustomLangChainWrapper(BaseChatModel):
    """
    Wrapper to make CustomAPILLMProvider compatible with LangChain.
    
    Converts LangChain message format to string prompts for custom API providers.
    
    Example:
        >>> from src.infrastructure.embeddings.providers.custom_api_provider import get_custom_llm_provider
        >>> provider = get_custom_llm_provider()
        >>> wrapper = CustomLangChainWrapper(provider=provider)
        >>> response = wrapper.invoke([HumanMessage(content="Hello")])
    """
    
    provider: Any = None
    
    def __init__(self, provider: Any):
        """
        Initialize the wrapper.
        
        Args:
            provider: Custom LLM provider instance with generate() method
        """
        super().__init__()
        self.provider = provider

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "custom-api"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate a response from a list of messages.
        
        Converts LangChain messages to a single prompt string for the custom provider.
        
        Args:
            messages: List of LangChain message objects
            stop: Optional stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional arguments
            
        Returns:
            ChatResult with generated response
        """
        # Convert messages to prompt string
        prompt = self._messages_to_prompt(messages)

        # Generate using the custom provider
        try:
            response = self.provider.generate(prompt)
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=response))]
            )
        except Exception as e:
            logger.error(f"Custom LLM generation failed: {e}")
            raise
    
    def _messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        """
        Convert a list of messages to a single prompt string.
        
        Args:
            messages: List of LangChain message objects
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        for message in messages:
            if isinstance(message, SystemMessage):
                prompt_parts.append(f"System: {message.content}")
            elif isinstance(message, HumanMessage):
                prompt_parts.append(f"User: {message.content}")
            elif isinstance(message, AIMessage):
                prompt_parts.append(f"Assistant: {message.content}")
            else:
                prompt_parts.append(str(message.content))
        
        return "\n".join(prompt_parts)
