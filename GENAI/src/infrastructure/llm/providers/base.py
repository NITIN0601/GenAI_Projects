"""
Provider abstraction layer for LLMs.

Supports:
- OpenAI (GPT-4, GPT-3.5-turbo)
- Ollama (llama3.2, mistral, etc.)
- Custom API
- Easy switching via configuration
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os

from src.utils import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from LLM."""
        pass
    
    @abstractmethod
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate response with context (for RAG)."""
        pass
    
    @abstractmethod
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name."""
        pass


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider (GPT-4, GPT-3.5-turbo)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo"
    ):
        """
        Initialize OpenAI LLM provider.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model name (gpt-4, gpt-3.5-turbo, gpt-4-turbo)
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
        
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)
        
        logger.info(f"OpenAI LLM initialized: {model}")
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from LLM."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate response with context (for RAG)."""
        if system_prompt is None:
            from src.prompts import FINANCIAL_ANALYSIS_PROMPT
            system_prompt = FINANCIAL_ANALYSIS_PROMPT
        
        # Format prompt
        prompt = system_prompt.format(context=context, question=query)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a financial analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        return response.choices[0].message.content
    
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        try:
            # Test with minimal request
            self.client.models.list()
            return True
        except Exception:
            return False
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"openai-{self.model}"


class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider (local, free)."""
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434"
    ):
        """
        Initialize Ollama LLM provider.
        
        Args:
            model: Ollama model name (llama3.2, mistral, etc.)
            base_url: Ollama API base URL
        """
        import requests
        
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.requests = requests
        
        logger.info(f"Ollama LLM initialized: {model}")
        self._check_ollama()
    
    def _check_ollama(self):
        """Check if Ollama is running."""
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if not any(self.model in name for name in model_names):
                    logger.warning(f"Model '{self.model}' not found")
                    logger.info(f"To install: ollama pull {self.model}")
                else:
                    logger.info(f"Model '{self.model}' available")
        except Exception:
            logger.warning("Ollama not running. Start with: ollama serve")
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from LLM."""
        payload = {
            "model": self.model,
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
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Error: {e}"
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate response with context (for RAG)."""
        if system_prompt is None:
            from src.prompts import FINANCIAL_ANALYSIS_PROMPT
            system_prompt = FINANCIAL_ANALYSIS_PROMPT
        
        prompt = system_prompt.format(context=context, question=query)
        return self.generate(prompt)
    
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"ollama-{self.model}"


class LLMManager:
    """
    Unified LLM manager with provider abstraction.
    
    Supports:
    - OpenAI (GPT-4, GPT-3.5-turbo)
    - Ollama (llama3.2, mistral, etc.)
    - Custom API
    """
    
    def __init__(
        self,
        provider: str = "ollama",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize LLM manager.
        
        Args:
            provider: "openai", "ollama", or "custom"
            model: Model name (provider-specific)
            api_key: API key for cloud providers
            base_url: Base URL for Ollama
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "openai":
            model = model or "gpt-3.5-turbo"
            self.provider = OpenAILLMProvider(api_key=api_key, model=model)
        elif self.provider_name == "ollama":
            model = model or "llama3.2"
            base_url = base_url or "http://localhost:11434"
            self.provider = OllamaLLMProvider(model=model, base_url=base_url)
        elif self.provider_name == "custom":
            # Import inside method to avoid circular import
            from src.infrastructure.embeddings.providers.custom_api_provider import get_custom_llm_provider
            self.provider = get_custom_llm_provider()
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: 'openai', 'ollama', 'custom'"
            )
        
        logger.info(f"LLM Manager: {self.provider.get_provider_name()}")
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from LLM."""
        return self.provider.generate(prompt, temperature, max_tokens)
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate response with context (for RAG)."""
        return self.provider.generate_with_context(query, context, system_prompt)
    
    def check_availability(self) -> bool:
        """Check if LLM is available."""
        return self.provider.check_availability()
    
    def get_provider_info(self) -> dict:
        """Get provider information."""
        return {
            "provider": self.provider_name,
            "model": self.provider.get_provider_name(),
            "available": self.provider.check_availability()
        }


# Global instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> LLMManager:
    """
    Get or create global LLM manager.
    
    Args:
        provider: "openai" or "ollama" (default: from config)
        model: Model name (default: from config)
        api_key: API key for cloud providers
    """
    global _llm_manager
    
    # Use config if not specified
    if provider is None:
        from config.settings import settings
        provider = getattr(settings, 'LLM_PROVIDER', 'ollama')
    
    if _llm_manager is None:
        _llm_manager = LLMManager(
            provider=provider,
            model=model,
            api_key=api_key
        )
    
    return _llm_manager
