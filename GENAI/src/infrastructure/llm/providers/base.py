"""
LLM Provider Implementations.

Direct LLM provider classes for use cases where LangChain is not needed.
These implement the core.interfaces.LLMProvider protocol.

Supports:
- OpenAI (GPT-4, GPT-3.5-turbo)
- Ollama (llama3.2, mistral, etc.)
- Custom API (via separate module)

For LangChain integration, use:
    from src.infrastructure.llm import get_llm_manager
    
For direct provider access:
    from src.infrastructure.llm.providers import OllamaLLMProvider
    provider = OllamaLLMProvider(model="llama3.2")
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Iterator
import os
import warnings

from src.utils import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Implements the core.interfaces.LLMProvider protocol.
    All concrete providers must implement these methods.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Model name/identifier."""
        ...
    
    def is_available(self) -> bool:
        """Check if provider is available and ready."""
        return self.check_availability()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Dict with 'status' (ok/error) and optional details
        """
        try:
            available = self.check_availability()
            return {
                "status": "ok" if available else "error",
                "provider": self.name,
                "model": self.model,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.name,
                "error": str(e),
            }
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs: Any
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific options
            
        Returns:
            Generated text
        """
        ...
    
    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Async version of generate.
        
        Default implementation calls sync version.
        Override for true async support.
        """
        return self.generate(prompt, system_prompt, **kwargs)
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream text generation.
        
        Default implementation yields complete response.
        Override for true streaming support.
        
        Yields:
            Text chunks as they're generated
        """
        yield self.generate(prompt, system_prompt, **kwargs)
    
    @abstractmethod
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        ...
    
    def get_provider_name(self) -> str:
        """Get provider name (backward compatibility)."""
        return self.name
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response with context (for RAG).
        
        Convenience method that formats query with context.
        
        Args:
            query: User query
            context: Retrieved context
            system_prompt: Optional system instruction
            
        Returns:
            Generated response
        """
        if system_prompt is None:
            from src.prompts import FINANCIAL_ANALYSIS_PROMPT
            system_prompt = FINANCIAL_ANALYSIS_PROMPT
        
        prompt = system_prompt.format(context=context, question=query)
        return self.generate(prompt)


class OpenAILLMProvider(LLMProvider):
    """
    OpenAI LLM provider (GPT-4, GPT-3.5-turbo).
    
    Example:
        >>> provider = OpenAILLMProvider(model="gpt-4")
        >>> response = provider.generate("Explain quantum computing")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        organization: Optional[str] = None,
    ):
        """
        Initialize OpenAI LLM provider.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model name (gpt-4, gpt-3.5-turbo, gpt-4-turbo)
            organization: Optional organization ID
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter"
            )
        
        self._model = model
        self.client = openai.OpenAI(
            api_key=self.api_key,
            organization=organization,
        )
        
        logger.info(f"OpenAI LLM initialized: {model}")
    
    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "openai"
    
    @property
    def model(self) -> str:
        """Model name/identifier."""
        return self._model
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs: Any
    ) -> str:
        """Generate response from OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream response from OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            stream=True,
            **kwargs
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def check_availability(self) -> bool:
        """Check if OpenAI is available."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class OllamaLLMProvider(LLMProvider):
    """
    Ollama LLM provider (local, free).
    
    Example:
        >>> provider = OllamaLLMProvider(model="llama3.2")
        >>> response = provider.generate("Hello!")
    """
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        check_on_init: bool = True,
    ):
        """
        Initialize Ollama LLM provider.
        
        Args:
            model: Ollama model name (llama3.2, mistral, etc.)
            base_url: Ollama API base URL
            check_on_init: Check if Ollama is running during init
        """
        import requests
        
        self._model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.chat_url = f"{base_url}/api/chat"
        self.requests = requests
        
        logger.info(f"Ollama LLM initialized: {model}")
        
        if check_on_init:
            self._check_ollama()
    
    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "ollama"
    
    @property
    def model(self) -> str:
        """Model name/identifier."""
        return self._model
    
    def _check_ollama(self) -> None:
        """Check if Ollama is running and model is available."""
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if not any(self._model in name for name in model_names):
                    logger.warning(f"Model '{self._model}' not found")
                    logger.info(f"To install: ollama pull {self._model}")
                else:
                    logger.info(f"Model '{self._model}' available")
        except Exception:
            logger.warning("Ollama not running. Start with: ollama serve")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs: Any
    ) -> str:
        """Generate response from Ollama."""
        # Use chat API for system prompt support
        if system_prompt:
            return self._generate_chat(prompt, system_prompt, temperature, max_tokens)
        
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = self.requests.post(
                self.api_url,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                raise RuntimeError(f"Ollama error: {response.status_code}")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    def _generate_chat(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using chat API with system prompt."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        response = self.requests.post(
            self.chat_url,
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json().get('message', {}).get('content', '')
        else:
            raise RuntimeError(f"Ollama error: {response.status_code}")
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream response from Ollama."""
        if system_prompt:
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": True,
                "options": {"temperature": temperature}
            }
            url = self.chat_url
        else:
            payload = {
                "model": self._model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": temperature}
            }
            url = self.api_url
        
        try:
            with self.requests.post(url, json=payload, stream=True, timeout=120) as response:
                for line in response.iter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if system_prompt:
                            content = data.get('message', {}).get('content', '')
                        else:
                            content = data.get('response', '')
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise
    
    def check_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Factory functions for convenience
def create_openai_provider(
    model: str = "gpt-3.5-turbo",
    api_key: Optional[str] = None
) -> OpenAILLMProvider:
    """Create an OpenAI provider instance."""
    return OpenAILLMProvider(model=model, api_key=api_key)


def create_ollama_provider(
    model: str = "llama3.2",
    base_url: str = "http://localhost:11434"
) -> OllamaLLMProvider:
    """Create an Ollama provider instance."""
    return OllamaLLMProvider(model=model, base_url=base_url)
