# GENAI Scaling Guide

## Current Architecture (Single Machine)

The GENAI system currently runs on a single machine with:
- Local/cloud embedding providers
- File-based (FAISS) or server-based (ChromaDB, Redis) vector storage
- Local/cloud LLM providers

---

## Horizontal Scaling

Horizontal scaling adds more machines to handle load.

### Option 1: Stateless Workers + Redis

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                           │
│                    (nginx / HAProxy)                         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Worker 1   │    │   Worker 2   │    │   Worker 3   │
│  (GENAI API) │    │  (GENAI API) │    │  (GENAI API) │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │   Redis    │ │  Redis     │ │  Shared    │
        │  VectorDB  │ │   Cache    │ │  Storage   │
        └────────────┘ └────────────┘ └────────────┘
```

### Implementation Steps

1. **Add FastAPI Layer** (create `src/api/`)
```python
# src/api/main.py
from fastapi import FastAPI
from src.rag import RAGPipeline

app = FastAPI()

@app.post("/query")
async def query(question: str):
    pipeline = RAGPipeline()
    return pipeline.query(question)
```

2. **Switch to Redis VectorDB**
```bash
# In .env
VECTORDB_PROVIDER=redis
REDIS_VECTOR_HOST=redis-cluster.example.com
```

3. **Use Shared Storage**
```bash
# Mount NFS or use S3 for PDFs
RAW_DATA_DIR=/mnt/shared/raw_data
```

4. **Deploy with Docker**
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0"]
```

5. **Kubernetes Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: genai-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: genai-api
  template:
    spec:
      containers:
      - name: genai
        image: genai:latest
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
```

---

## Vertical Scaling

Vertical scaling increases resources on existing machines.

### GPU Acceleration

```bash
# In .env
EMBEDDING_PROVIDER=local
EMBEDDING_DEVICE=cuda  # Use GPU for embeddings

# Install GPU support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Memory Optimization

```python
# In config/settings.py
EMBEDDING_BATCH_SIZE=64  # Increase for more RAM
FAISS_INDEX_TYPE=ivf     # Use IVF for large datasets (10M+ vectors)
```

### Resource Recommendations

| Scale | PDFs | Chunks | RAM | CPU | GPU |
|-------|------|--------|-----|-----|-----|
| Small | <100 | <10K | 8GB | 4 cores | Optional |
| Medium | 100-1000 | 10K-100K | 32GB | 8 cores | Recommended |
| Large | 1000+ | 100K+ | 64GB+ | 16+ cores | Required |

---

## Scaling Decision Matrix

| Scenario | Horizontal | Vertical |
|----------|------------|----------|
| More concurrent users | ✅ Add workers | ❌ |
| Larger documents | ❌ | ✅ More RAM |
| Faster embeddings | ✅ Parallel workers | ✅ GPU |
| More vectors | ✅ Redis cluster | ✅ FAISS IVF |
| HA/Redundancy | ✅ Multiple replicas | ❌ |

---

## Production Checklist

### Before Horizontal Scaling
- [ ] Switch from FAISS to Redis VectorDB
- [ ] Add FastAPI/Flask API layer
- [ ] Use shared storage (NFS/S3) for PDFs
- [ ] Configure Redis for caching
- [ ] Add health check endpoints
- [ ] Set up load balancer

### Before Vertical Scaling
- [ ] Profile memory usage
- [ ] Enable GPU if available
- [ ] Tune batch sizes
- [ ] Configure FAISS index type
- [ ] Monitor with LangSmith

---

## Quick Start Commands

### Docker (Single Container)
```bash
docker build -t genai .
docker run -p 8000:8000 -v ./data:/app/data genai
```

### Docker Compose (Multi-Service)
```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - VECTORDB_PROVIDER=redis
      - REDIS_VECTOR_HOST=redis
  
  redis:
    image: redis/redis-stack:latest
    ports:
      - "6379:6379"
```

```bash
docker-compose up -d --scale api=3
```
