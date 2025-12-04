"""LLM manager using LangChain and Ollama/Custom Providers."""

from typing import Optional, Any, List, Dict
import logging
from langchain_community.chat_models import ChatOllama
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration

from config.settings import settings

logger = logging.getLogger(__name__)


class CustomLangChainWrapper(BaseChatModel):
    """Wrapper to make CustomAPILLMProvider compatible with LangChain."""
    
    provider: Any = None
    
    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    @property
    def _llm_type(self) -> str:
        return "custom-api"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Convert messages to prompt
        # This is a simple conversion. For better results, the custom provider 
        # should ideally support list of messages if the API supports it.
        # But based on the user's code, it takes a single string prompt or messages list.
        # The CustomAPILLMProvider.generate takes a prompt string.
        # However, CustomAPILLMProvider.generate constructs a messages list internally:
        # "messages": [{"role": "user", "content": prompt}]
        
        # So we should probably construct a single prompt string from the history
        # OR update CustomAPILLMProvider to accept messages.
        # For now, let's concat.
        
        prompt = ""
        for m in messages:
            if isinstance(m, SystemMessage):
                prompt += f"System: {m.content}\n"
            elif isinstance(m, HumanMessage):
                prompt += f"User: {m.content}\n"
            elif isinstance(m, AIMessage):
                prompt += f"Assistant: {m.content}\n"
            else:
                prompt += f"{m.content}\n"
        
        # Remove trailing newline
        prompt = prompt.strip()

        # Generate
        # We use generate() which takes a string prompt
        response = self.provider.generate(prompt)

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=response))])


class LLMManager:
    """
    LLM integration using LangChain.
    
    Supports:
    - Ollama (via ChatOllama)
    - Custom API (via CustomLangChainWrapper)
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
            model_name: Model name
            base_url: API base URL
            callbacks: LangChain callbacks
        """
        self.provider_type = settings.LLM_PROVIDER
        self.callbacks = callbacks or []
        
        if self.provider_type == "custom":
            self.model_name = model_name or settings.LLM_MODEL_CUSTOM
            logger.info(f"Initializing Custom LLM: {self.model_name}")
            
            # Import inside method to avoid circular import
            from src.embeddings.providers.custom_api_provider import get_custom_llm_provider
            custom_provider = get_custom_llm_provider()
            self.llm = CustomLangChainWrapper(provider=custom_provider)
            
        elif self.provider_type == "openai":
            self.model_name = model_name or settings.OPENAI_MODEL
            logger.info(f"Initializing OpenAI LLM: {self.model_name}")
            
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=self.model_name,
                api_key=settings.OPENAI_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                callbacks=self.callbacks
            )
            
        else:
            # Default to Ollama
            self.model_name = model_name or settings.LLM_MODEL or settings.OLLAMA_MODEL
            self.base_url = base_url or settings.OLLAMA_BASE_URL
            
            logger.info(f"Initializing LangChain Ollama LLM: {self.model_name}")
            
            self.llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=settings.LLM_TEMPERATURE,
                callbacks=self.callbacks,
                keep_alive="5m"
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
        """
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        # Update runtime settings if needed (only for Ollama for now)
        if temperature is not None and hasattr(self.llm, 'temperature'):
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
