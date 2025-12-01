
import sys
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vector_store.stores.faiss_store import get_faiss_store
from src.retrieval.retriever import get_retriever
from src.retrieval.query_processor import get_query_processor
from langchain_core.documents import Document

def verify_faiss_store():
    print("\n--- Verifying FAISS Store (LangChain Interface) ---")
    store = get_faiss_store()
    
    # Test add_texts
    texts = ["Apple revenue was $100B in 2024", "Microsoft revenue was $90B in 2024"]
    metadatas = [{"source": "report1", "year": 2024}, {"source": "report2", "year": 2024}]
    
    # Debug: Check embeddings
    print("Generating embeddings...")
    embeddings = store.embedding_function.embed_documents(texts)
    print(f"Generated {len(embeddings)} embeddings")
    if embeddings:
        print(f"Embedding type: {type(embeddings[0])}")
        print(f"Embedding length: {len(embeddings[0])}")
        import numpy as np
        print(f"Embedding shape: {np.array(embeddings).shape}")
    
    ids = store.add_texts(texts, metadatas=metadatas)
    print(f"Added {len(ids)} documents")
    
    # Test similarity_search_with_score
    results = store.similarity_search_with_score("revenue 2024", k=2)
    print(f"Found {len(results)} results")
    for doc, score in results:
        print(f"Content: {doc.page_content}, Score: {score}")
        assert isinstance(doc, Document)
        assert "year" in doc.metadata

def verify_retriever():
    print("\n--- Verifying Retriever ---")
    retriever = get_retriever()
    results = retriever.retrieve("revenue", top_k=2)
    print(f"Retrieved {len(results)} chunks")
    if results:
        print(f"First result: {results[0]}")
        assert "content" in results[0]
        assert "metadata" in results[0]

def verify_query_processor():
    print("\n--- Verifying Query Processor ---")
    processor = get_query_processor()
    # Mock query understanding to avoid LLM calls if possible, but for now let's try a real flow
    # Assuming QueryUnderstanding mocks or works without heavy dependencies
    try:
        result = processor.process_query("What was revenue in 2024?", top_k=2)
        print("Query processed successfully")
        print(result)
    except Exception as e:
        print(f"Query processing failed (expected if LLM not configured): {e}")

if __name__ == "__main__":
    try:
        verify_faiss_store()
        verify_retriever()
        # verify_query_processor() # Skip for now to avoid LLM dependency issues in this script
        print("\nVerification Successful!")
    except Exception as e:
        print(f"\nVerification Failed: {e}")
        sys.exit(1)
