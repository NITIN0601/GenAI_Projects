"""LLM manager using Ollama (FREE & LOCAL)."""

from typing import Optional, Dict, Any
import requests
import json

from config.settings import settings


class LLMManager:
    """
    LLM integration using Ollama (FREE & LOCAL).
    No API keys required! Runs completely on your machine.
    
    Supported models:
    - llama3.2 (recommended, fast)
    - llama3.1
    - mistral
    - mixtral
    - phi3
    """
    
    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize LLM manager.
        
        Args:
            model_name: Ollama model name
            base_url: Ollama API base URL
        """
        self.model_name = model_name or settings.LLM_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.api_url = f"{self.base_url}/api/generate"
        
        print(f"LLM Manager initialized with model: {self.model_name}")
        
        # Check if Ollama is running
        self._check_ollama()
    
    def _check_ollama(self):
        """Check if Ollama is running and model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if not any(self.model_name in name for name in model_names):
                    print(f"\n⚠️  Model '{self.model_name}' not found in Ollama.")
                    print(f"Available models: {', '.join(model_names)}")
                    print(f"\nTo install the model, run:")
                    print(f"  ollama pull {self.model_name}")
                else:
                    print(f"✓ Model '{self.model_name}' is available")
            else:
                print("⚠️  Could not connect to Ollama")
        except requests.exceptions.RequestException:
            print("\n⚠️  Ollama is not running!")
            print("Please start Ollama:")
            print("  1. Install: https://ollama.ai")
            print("  2. Run: ollama serve")
            print(f"  3. Pull model: ollama pull {self.model_name}")
    
    def generate(
        self,
        prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False
    ) -> str:
        """
        Generate response from LLM.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            Generated text
        """
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=120  # 2 minute timeout for generation
            )
            
            if response.status_code == 200:
                if stream:
                    # Handle streaming response
                    full_response = ""
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line)
                            if 'response' in data:
                                full_response += data['response']
                    return full_response
                else:
                    # Handle non-streaming response
                    result = response.json()
                    return result.get('response', '')
            else:
                error_msg = f"LLM API error: {response.status_code} - {response.text}"
                print(error_msg)
                return f"Error: {error_msg}"
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to Ollama: {e}"
            print(error_msg)
            return f"Error: {error_msg}"
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response with context (for RAG).
        
        Args:
            query: User query
            context: Retrieved context
            system_prompt: System prompt template
            
        Returns:
            Generated answer
        """
        if system_prompt is None:
            from config.prompts import FINANCIAL_ANALYSIS_PROMPT
            system_prompt = FINANCIAL_ANALYSIS_PROMPT
        
        # Format prompt
        prompt = system_prompt.format(context=context, question=query)
        
        return self.generate(prompt)
    
    def check_availability(self) -> bool:
        """
        Check if LLM is available.
        
        Returns:
            True if available, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


# Global LLM manager instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get or create global LLM manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
