"""
Custom API provider for LLM and Embedding models.

Supports bearer token authentication and custom endpoints.
Compatible with the existing provider system.
"""

import os
import requests
import logging
from typing import List, Dict, Any, Optional
import urllib3

from embeddings.providers import EmbeddingProvider, LLMProvider

# Disable SSL warnings for custom endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class CustomAPIEmbeddingProvider(EmbeddingProvider):
    """
    Custom API embedding provider with bearer token authentication.
    
    Uses environment variables:
    - EB_URL: Embedding API endpoint
    - EB_MODEL: Embedding model name
    - UNIQUE_ID: Unique identifier for requests
    - BEARER_TOKEN: Authentication token
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        unique_id: Optional[str] = None,
        bearer_token: Optional[str] = None
    ):
        """
        Initialize custom API embedding provider.
        
        Args:
            api_url: API endpoint (defaults to EB_URL env var)
            model_name: Model name (defaults to EB_MODEL env var)
            unique_id: Unique ID (defaults to UNIQUE_ID env var)
            bearer_token: Bearer token (defaults to BEARER_TOKEN env var)
        """
        self.api_url = api_url or os.getenv('EB_URL')
        self.model_name = model_name or os.getenv('EB_MODEL')
        self.unique_id = unique_id or os.getenv('UNIQUE_ID')
        self.bearer_token = bearer_token or os.getenv('BEARER_TOKEN')
        
        if not all([self.api_url, self.model_name, self.unique_id, self.bearer_token]):
            raise ValueError(
                "Missing required environment variables: EB_URL, EB_MODEL, UNIQUE_ID, BEARER_TOKEN"
            )
        
        self.headers = {
            "accept": "application/json",
            "Unique-Id": self.unique_id,
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Custom API Embedding Provider initialized: {self.model_name}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using custom API.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        data = {
            "model": self.model_name,
            "input": text
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=data,
                verify=False  # Disable SSL verification
            )
            response.raise_for_status()
            
            response_json = response.json()
            embedding = response_json['data'][0]['embedding']
            
            return embedding
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Custom API embedding request failed: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"Invalid embedding response structure: {e}")
            raise ValueError(f"Invalid embedding response: {e}")
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        # Generate one at a time (can be optimized if API supports batch)
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension by generating a test embedding."""
        test_embedding = self.generate_embedding("test")
        return len(test_embedding)
    
    def get_dimension(self) -> int:
        """Get embedding dimension (alias for compatibility)."""
        return self.get_embedding_dimension()
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"custom-{self.model_name}"


class CustomAPILLMProvider(LLMProvider):
    """
    Custom API LLM provider with bearer token authentication.
    
    Uses environment variables:
    - LLM_URL: LLM API endpoint
    - LLM_MODEL: LLM model name
    - UNIQUE_ID: Unique identifier for requests
    - BEARER_TOKEN: Authentication token
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        unique_id: Optional[str] = None,
        bearer_token: Optional[str] = None,
        temperature: float = 0.0
    ):
        """
        Initialize custom API LLM provider.
        
        Args:
            api_url: API endpoint (defaults to LLM_URL env var)
            model_name: Model name (defaults to LLM_MODEL env var)
            unique_id: Unique ID (defaults to UNIQUE_ID env var)
            bearer_token: Bearer token (defaults to BEARER_TOKEN env var)
            temperature: Sampling temperature
        """
        self.api_url = api_url or os.getenv('LLM_URL')
        self.model_name = model_name or os.getenv('LLM_MODEL')
        self.unique_id = unique_id or os.getenv('UNIQUE_ID')
        self.bearer_token = bearer_token or os.getenv('BEARER_TOKEN')
        self.temperature = temperature
        
        if not all([self.api_url, self.model_name, self.unique_id, self.bearer_token]):
            raise ValueError(
                "Missing required environment variables: LLM_URL, LLM_MODEL, UNIQUE_ID, BEARER_TOKEN"
            )
        
        self.headers = {
            "accept": "application/json",
            "Unique-Id": self.unique_id,
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Custom API LLM Provider initialized: {self.model_name}")
    
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using custom API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature or self.temperature,
            "stream": False
        }
        
        if max_tokens:
            data["max_tokens"] = max_tokens
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=data,
                verify=False  # Disable SSL verification
            )
            response.raise_for_status()
            
            response_json = response.json()
            content = response_json["choices"][0]["message"]["content"]
            
            return content
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Custom API LLM request failed: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"Invalid LLM response structure: {e}")
            raise ValueError(f"Invalid LLM response: {e}")
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text with context (for RAG).
        
        Args:
            query: User query
            context: Retrieved context
            max_tokens: Maximum tokens
            
        Returns:
            Generated answer
        """
        prompt = f"""Context:
{context}

Question: {query}

Answer based on the context above:"""
        
        return self.generate(prompt, max_tokens=max_tokens)


# Factory functions for easy integration
def get_custom_embedding_provider() -> CustomAPIEmbeddingProvider:
    """Get custom API embedding provider instance."""
    return CustomAPIEmbeddingProvider()


def get_custom_llm_provider() -> CustomAPILLMProvider:
    """Get custom API LLM provider instance."""
    return CustomAPILLMProvider()
