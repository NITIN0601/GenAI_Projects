"""
Custom API provider for LLM and Embedding models.

Supports bearer token authentication and custom endpoints.
Compatible with the existing provider system.
"""

import os
import requests
import logging
from src.utils import get_logger
import json
from typing import List, Dict, Any, Optional, Union
import urllib3

from src.infrastructure.embeddings.providers import EmbeddingProvider
from src.infrastructure.llm.providers.base import LLMProvider
from config.settings import settings

# Disable SSL warnings for custom endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


def model_request(url: str, data: dict, model_type: str, testing: bool = False, headers: Dict[str, str] = None):
    """
    Sends a POST request to the specified model API and returns a summary of the response.

    Args:
        url (str): The API endpoint URL.
        data (dict): The payload to send in the request.
        model_type (str): Type of model ('LLM' or 'EB').
        testing (bool): Flag to determine the return type for LLM/EB.
        headers (dict): Headers to send with the request.

    Returns:
        dict, str, list: Parsed model response content/embedding or summary dict.
        None: If an error occurs.
    """
    logger.debug(f"Testing {model_type} Model...")

    def parse_response(
        response_json: Dict[str, Any],
        model_type: str,
        testing: bool = False
    ) -> Union[Dict[str, Any], str, list, None]:
        """
        Parses the API response based on the model type.
        """
        if model_type == "LLM":
            try:
                content = response_json["choices"][0]["message"]["content"]
                usage = response_json.get('usage', {})
                if testing:
                    return {
                        "Model_Type": model_type,
                        "Model_Name": response_json.get('model'),
                        "Response_Type": type(content).__name__,
                        "Response_Length": len(content),
                        "Usage_Consumed": {
                            'prompt_tokens': usage.get('prompt_tokens'),
                            'completion_tokens': usage.get('completion_tokens'),
                            'total_tokens': usage.get('total_tokens')
                        }
                    }
                else:
                    return content
            except (KeyError, IndexError) as e:
                raise ValueError(f"Invalid LLM response structure: {e}") from e

        elif model_type == "EB":
            try:
                embedding = response_json['data'][0]['embedding']
                if testing:
                    return {
                        "Model_Type": model_type,
                        "Model_Name": response_json.get('model'),
                        "Response_Type": type(embedding).__name__,
                        "Response_Length": len(embedding),
                        "Usage_Consumed": response_json.get('usage', {})
                    }
                else:
                    return embedding
            except (KeyError, IndexError) as e:
                raise ValueError(f"Invalid EB response structure: {e}") from e

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    try:
        response = requests.post(url, headers=headers, json=data, verify=False)
        # logger.debug(f"HTTP Status Code: {response.status_code}")
        response.raise_for_status()

        return parse_response(response.json(), model_type, testing)

    except requests.exceptions.HTTPError as http_err:
        logger.info(f"HTTP error occurred: {http_err}")
        if http_err.response is not None:
             logger.info(f"Response Content: {http_err.response.text}")
        raise
    except requests.exceptions.ConnectionError as conn_err:
        logger.info(f"Connection error occurred: {conn_err}")
        raise
    except requests.exceptions.Timeout as timeout_err:
        logger.info(f"Timeout error occurred: {timeout_err}")
        raise
    except requests.exceptions.RequestException as req_error:
        logger.info(f"General Request Error: {req_error}")
        raise
    except json.JSONDecodeError as json_error:
        logger.info(f"Failed to parse JSON response: {json_error}")
        raise
    except ValueError as val_error:
        logger.info(f"Data parsing error: {val_error}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

    return None


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
        bearer_token: Optional[str] = None,
        dimension: Optional[int] = None
    ):
        """
        Initialize custom API embedding provider.
        """
        self.api_url = api_url or settings.EB_URL or os.getenv('EB_URL')
        self.model_name = model_name or settings.EB_MODEL or os.getenv('EB_MODEL')
        self.unique_id = unique_id or settings.UNIQUE_ID or os.getenv('UNIQUE_ID')
        self.bearer_token = bearer_token or settings.BEARER_TOKEN or os.getenv('BEARER_TOKEN')
        
        # Try to get dimension from settings or env, fallback to auto-detect later
        self.dimension = dimension or settings.EB_DIMENSION
        if self.dimension is None:
            env_dim = os.getenv('EB_DIMENSION')
            if env_dim:
                try:
                    self.dimension = int(env_dim)
                except ValueError:
                    pass
        
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
        
        # Connection pooling for better performance
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._session.verify = False  # Match existing behavior
        
        logger.info(f"Custom API Embedding Provider initialized: {self.model_name}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using custom API.
        """
        data = {
            "model": self.model_name,
            "input": text
        }
        
        try:
            response = self._session.post(self.api_url, json=data)
            response.raise_for_status()
            return response.json()['data'][0]['embedding']
        except Exception as e:
            # Fallback to non-session request
            return model_request(self.api_url, data, "EB", testing=False, headers=self.headers)
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Attempts batch API call first, falls back to sequential if not supported.
        """
        if not texts:
            return []
        
        # Try batch API call first (many APIs support this)
        try:
            data = {
                "model": self.model_name,
                "input": texts  # Send all texts at once
            }
            response = self._session.post(self.api_url, json=data)
            response.raise_for_status()
            result = response.json()
            
            # Extract embeddings in order
            embeddings = [item['embedding'] for item in sorted(result['data'], key=lambda x: x.get('index', 0))]
            logger.debug(f"Batch embedding succeeded for {len(texts)} texts")
            return embeddings
            
        except Exception as e:
            logger.debug(f"Batch API not supported, falling back to sequential: {e}")
            # Fallback to sequential (for APIs that don't support batch)
            embeddings = []
            for text in texts:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            return embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension."""
        if self.dimension:
            return self.dimension
            
        # Fallback to auto-detection
        try:
            test_embedding = self.generate_embedding("test")
            self.dimension = len(test_embedding)
            return self.dimension
        except Exception:
            return 384 # Fallback
    
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
    - LLM_MODEL_CUSTOM: LLM model name
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
        """
        self.api_url = api_url or settings.LLM_URL or os.getenv('LLM_URL')
        # Use LLM_MODEL_CUSTOM preference, fallback to LLM_MODEL
        self.model_name = model_name or settings.LLM_MODEL_CUSTOM or os.getenv('LLM_MODEL_CUSTOM') or os.getenv('LLM_MODEL')
        self.unique_id = unique_id or settings.UNIQUE_ID or os.getenv('UNIQUE_ID')
        self.bearer_token = bearer_token or settings.BEARER_TOKEN or os.getenv('BEARER_TOKEN')
        self.temperature = temperature
        
        if not all([self.api_url, self.model_name, self.unique_id, self.bearer_token]):
            raise ValueError(
                "Missing required environment variables: LLM_URL, LLM_MODEL_CUSTOM (or LLM_MODEL), UNIQUE_ID, BEARER_TOKEN"
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
        """
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False
        }
        
        if max_tokens:
            data["max_tokens"] = max_tokens
        
        return model_request(self.api_url, data, "LLM", testing=False, headers=self.headers)
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate text with context (for RAG).
        """
        if system_prompt is None:
             # Avoid circular import if possible, or import inside method
             try:
                 from src.prompts import FINANCIAL_ANALYSIS_PROMPT
                 system_prompt = FINANCIAL_ANALYSIS_PROMPT
             except ImportError:
                 system_prompt = "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        prompt = system_prompt.format(context=context, question=query)
        
        return self.generate(prompt)

    def check_availability(self) -> bool:
        """Check if LLM is available."""
        try:
            self.generate("test", max_tokens=5)
            return True
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"custom-{self.model_name}"


# Factory functions for easy integration
def get_custom_embedding_provider() -> CustomAPIEmbeddingProvider:
    """Get custom API embedding provider instance."""
    return CustomAPIEmbeddingProvider()


def get_custom_llm_provider() -> CustomAPILLMProvider:
    """Get custom API LLM provider instance."""
    return CustomAPILLMProvider()
