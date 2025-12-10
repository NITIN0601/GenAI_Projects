"""
LLM Manager - Unified LLM interface using LangChain.

Provides thread-safe singleton access to LLM providers with support for:
- Ollama (local, default)
- OpenAI (GPT-4, GPT-3.5-turbo)
- Custom API (bearer token)
- Local HuggingFace models

Example:
    >>> from src.infrastructure.llm import get_llm_manager
    >>> 
    >>> llm = get_llm_manager()
    >>> response = llm.generate("What is AI?")
    >>> print(response)
"""

from typing import Optional, Any, List, Dict, Iterator

from langchain_community.chat_models import ChatOllama
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings
from src.core.singleton import ThreadSafeSingleton
from src.utils import get_logger

logger = get_logger(__name__)


class LLMManager(metaclass=ThreadSafeSingleton):
    """
    LLM integration using LangChain.
    
    Thread-safe singleton manager for LLM providers.
    
    Supports:
    - Ollama (via ChatOllama) - default
    - OpenAI (via ChatOpenAI)
    - Custom API (via CustomLangChainWrapper)
    - Local HuggingFace (via HuggingFacePipeline)
    
    Attributes:
        provider_type: Current provider type (ollama, openai, custom, local)
        model_name: Model identifier
        llm: Underlying LangChain model
    """
    
    def __init__(
        self, 
        model_name: Optional[str] = None, 
        base_url: Optional[str] = None,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        provider: Optional[str] = None,
    ):
        """
        Initialize LLM manager.
        
        Args:
            model_name: Model name (uses settings default if not provided)
            base_url: API base URL (for Ollama)
            callbacks: LangChain callbacks for tracing/logging
            provider: Override provider type (uses settings default if not provided)
        """
        self.provider_type = provider or settings.LLM_PROVIDER
        self.callbacks = callbacks or []
        self._llm: Optional[BaseChatModel] = None
        
        # Initialize based on provider type
        self._initialize_provider(model_name, base_url)
    
    def _initialize_provider(
        self, 
        model_name: Optional[str], 
        base_url: Optional[str]
    ) -> None:
        """
        Initialize the appropriate LLM provider.
        
        Args:
            model_name: Model name override
            base_url: Base URL override
        """
        if self.provider_type == "custom":
            self._init_custom(model_name)
        elif self.provider_type == "openai":
            self._init_openai(model_name)
        elif self.provider_type == "local":
            self._init_local(model_name)
        else:
            # Default to Ollama
            self._init_ollama(model_name, base_url)
    
    def _init_custom(self, model_name: Optional[str]) -> None:
        """Initialize Custom API provider."""
        self.model_name = model_name or settings.LLM_MODEL_CUSTOM
        logger.info(f"Initializing Custom LLM: {self.model_name}")
        
        from src.infrastructure.llm.langchain_wrapper import CustomLangChainWrapper
        from src.infrastructure.embeddings.providers.custom_api_provider import get_custom_llm_provider
        
        custom_provider = get_custom_llm_provider()
        self._llm = CustomLangChainWrapper(provider=custom_provider)
    
    def _init_openai(self, model_name: Optional[str]) -> None:
        """Initialize OpenAI provider."""
        self.model_name = model_name or settings.OPENAI_MODEL
        logger.info(f"Initializing OpenAI LLM: {self.model_name}")
        
        from langchain_openai import ChatOpenAI
        
        self._llm = ChatOpenAI(
            model=self.model_name,
            api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None,
            temperature=settings.LLM_TEMPERATURE,
            callbacks=self.callbacks
        )
    
    def _init_local(self, model_name: Optional[str]) -> None:
        """Initialize local HuggingFace provider."""
        self.model_name = model_name or settings.LLM_MODEL_LOCAL
        logger.info(f"Initializing Local HuggingFace LLM: {self.model_name}")
        
        from langchain_huggingface import HuggingFacePipeline
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
        
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        
        pipe = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            max_length=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )
        
        self._llm = HuggingFacePipeline(pipeline=pipe)
    
    def _init_ollama(
        self, 
        model_name: Optional[str], 
        base_url: Optional[str]
    ) -> None:
        """Initialize Ollama provider (default)."""
        self.model_name = model_name or settings.LLM_MODEL or settings.OLLAMA_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        
        logger.info(f"Initializing Ollama LLM: {self.model_name}")
        
        self._llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=settings.LLM_TEMPERATURE,
            callbacks=self.callbacks,
            keep_alive="5m"
        )
    
    @property
    def llm(self) -> BaseChatModel:
        """Get the underlying LangChain model."""
        return self._llm
    
    @property
    def model(self) -> str:
        """Model name/identifier (implements LLMProvider protocol)."""
        return self.model_name
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return f"{self.provider_type}:{self.model_name}"
    
    def is_available(self) -> bool:
        """Check if provider is available (implements BaseProvider protocol)."""
        return self.check_availability()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            available = self.check_availability()
            return {
                "status": "ok" if available else "error",
                "provider": self.provider_type,
                "model": self.model_name,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider_type,
                "error": str(e),
            }
    
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response using LangChain.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature (overrides default)
            max_tokens: Maximum tokens (not used by all providers)
            stream: If True, use streaming (ignored, use stream() method instead)
            system_prompt: Optional system instruction
            
        Returns:
            Generated text response
        """
        messages = self._build_messages(prompt, system_prompt)
        
        # Update runtime settings if supported
        if temperature is not None and hasattr(self._llm, 'temperature'):
            self._llm.temperature = temperature
            
        try:
            response = self._llm.invoke(messages)
            # HuggingFacePipeline returns string, chat models return response objects
            if isinstance(response, str):
                return response
            return response.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """
        Async version of generate (implements LLMProvider protocol).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature
            **kwargs: Additional options
            
        Returns:
            Generated text
        """
        messages = self._build_messages(prompt, system_prompt)
        
        if temperature is not None and hasattr(self._llm, 'temperature'):
            self._llm.temperature = temperature
        
        try:
            response = await self._llm.ainvoke(messages)
            if isinstance(response, str):
                return response
            return response.content
        except Exception as e:
            logger.error(f"Async LLM generation failed: {e}")
            raise
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream text generation (implements LLMProvider protocol).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature
            **kwargs: Additional options
            
        Yields:
            Text chunks as they're generated
        """
        messages = self._build_messages(prompt, system_prompt)
        
        if temperature is not None and hasattr(self._llm, 'temperature'):
            self._llm.temperature = temperature
        
        try:
            for chunk in self._llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise
    
    def _build_messages(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> List[BaseMessage]:
        """
        Build message list from prompt and optional system prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            
        Returns:
            List of LangChain message objects
        """
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
    
    def get_langchain_model(self) -> BaseChatModel:
        """
        Return the underlying LangChain model object.
        
        Returns:
            LangChain BaseChatModel instance
        """
        return self._llm
        
    def check_availability(self) -> bool:
        """
        Check if LLM is available.
        
        Returns:
            True if LLM responds, False otherwise
        """
        try:
            self._llm.invoke("test")
            return True
        except Exception:
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information.
        
        Returns:
            Dict with provider details
        """
        return {
            "provider": self.provider_type,
            "model": self.model_name,
            "available": self.is_available(),
        }


def get_llm_manager(
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    **kwargs
) -> LLMManager:
    """
    Get or create global LLM manager instance.
    
    Thread-safe singleton accessor.
    
    Args:
        model_name: Model name (only used on first call)
        base_url: API base URL (only used on first call)
        callbacks: LangChain callbacks (only used on first call)
        **kwargs: Additional arguments
        
    Returns:
        LLMManager singleton instance
    """
    return LLMManager(
        model_name=model_name,
        base_url=base_url,
        callbacks=callbacks,
        **kwargs
    )


def reset_llm_manager() -> None:
    """
    Reset the LLM manager singleton.
    
    Useful for testing or reconfiguration.
    """
    LLMManager._reset_instance()
