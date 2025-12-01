
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    print("Importing EmbeddingManager...")
    from src.embeddings.manager import get_embedding_manager
    
    print("Getting manager...")
    manager = get_embedding_manager()
    
    print(f"Model: {manager.model_name}")
    print(f"Device: {manager.device}")
    
    texts = ["Hello world", "Financial report"]
    print("Generating embeddings...")
    embeddings = manager.embed_documents(texts)
    
    print(f"Generated {len(embeddings)} embeddings")
    print(f"Dimension: {len(embeddings[0])}")
    print("Success!")
    
except Exception as e:
    print(f"Error: {e}")
