
import sys
import os
import numpy as np
import faiss

print(f"FAISS version: {faiss.__version__}")

try:
    dimension = 384
    index = faiss.IndexFlatIP(dimension)
    print(f"Index created. Dimension: {dimension}")
    
    # Create dummy vector
    vec = np.random.rand(1, dimension).astype('float32')
    faiss.normalize_L2(vec)
    
    print("Adding vector...")
    index.add(vec)
    print(f"Vector added. Total: {index.ntotal}")
    
    # Search
    print("Searching...")
    D, I = index.search(vec, 1)
    print(f"Search result: {I}")
    
    print("Basic FAISS test passed.")
    
except Exception as e:
    print(f"Error: {e}")
