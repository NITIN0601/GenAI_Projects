
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from config.settings import settings

# Mock settings for testing
os.environ["EMBEDDING_PROVIDER"] = "custom"
os.environ["EB_URL"] = "https://example.com/embed"
os.environ["EB_MODEL"] = "custom-embed"
os.environ["UNIQUE_ID"] = "test-id"
os.environ["BEARER_TOKEN"] = "test-token"
os.environ["EB_DIMENSION"] = "1024" # Test specific dimension

# Reload settings/env
settings.EMBEDDING_PROVIDER = "custom"
settings.EB_URL = "https://example.com/embed"
settings.EB_MODEL = "custom-embed"
settings.UNIQUE_ID = "test-id"
settings.BEARER_TOKEN = "test-token"
settings.EB_DIMENSION = 1024

try:
    print("Testing EmbeddingManager with custom dimension...")
    from src.embeddings.manager import get_embedding_manager
    
    # Force re-initialization if singleton exists
    import src.embeddings.manager
    src.embeddings.manager._embedding_manager = None
    
    embedding_manager = get_embedding_manager()
    info = embedding_manager.get_provider_info()
    
    print(f"Provider Info: {info}")
    
    if info['dimension'] == 1024:
        print("SUCCESS: Dimension 1024 correctly picked up from settings.")
    else:
        print(f"FAILURE: Expected dimension 1024, got {info['dimension']}")

    # Test with a different dimension to ensure it's dynamic
    print("\nTesting with different dimension (768)...")
    settings.EB_DIMENSION = 768
    src.embeddings.manager._embedding_manager = None # Reset singleton
    
    embedding_manager_2 = get_embedding_manager()
    info_2 = embedding_manager_2.get_provider_info()
    print(f"Provider Info: {info_2}")
    
    if info_2['dimension'] == 768:
        print("SUCCESS: Dimension 768 correctly picked up from settings.")
    else:
        print(f"FAILURE: Expected dimension 768, got {info_2['dimension']}")

except Exception as e:
    print(f"\nFAILURE: {e}")
    import traceback
    traceback.print_exc()
