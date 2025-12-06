# Enterprise RAG System Architecture

> **Version:** 2.1.0 | **Updated:** December 5, 2025

## Overview

This system follows **Clean Architecture** principles with a layered, decoupled design that enables:

- 🔌 **Plug-and-Play Components** - Swap LLM, embedding, or vector DB providers without code changes
- 📦 **Modular Scaling** - Each layer scales independently
- 🧪 **Testability** - Interfaces enable easy mocking
- 🔄 **Future-Proof** - Add new providers via interfaces

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Entry Points"
        CLI["CLI (main.py)"]
        API["Future: REST API"]
    end

    subgraph "Application Layer"
        QUC["QueryUseCase"]
        IUC["IngestUseCase"]
        ORCH["PipelineOrchestrator"]
    end

    subgraph "Domain Layer"
        TABLES["Tables<br/>TableMetadata, TableChunk"]
        DOCS["Documents<br/>DocumentMetadata"]
        QUERIES["Queries<br/>RAGQuery, RAGResponse"]
    end

    subgraph "Core Layer"
        PATHS["PathManager"]
        DEDUP["PDFDeduplicator"]
        IFACE["Interfaces<br/>LLMProvider, CacheProvider"]
        EXCEPT["Exceptions"]
    end

    subgraph "Infrastructure Layer"
        subgraph "Three-Tier Cache"
            ECACHE["ExtractionCache<br/>Tier 1 - 30 days"]
            EMBCACHE["EmbeddingCache<br/>Tier 2 - 90 days"]
            QCACHE["QueryCache<br/>Tier 3 - 24 hours"]
        end
    end

    subgraph "Provider Implementations"
        subgraph "LLM Providers"
            OLLAMA["Ollama"]
            OPENAI["OpenAI"]
            GROQ["Groq"]
        end
        subgraph "Embedding Providers"
            LOCAL["Local/HuggingFace"]
            OPENAI_EMB["OpenAI Embeddings"]
        end
        subgraph "Vector Stores"
            FAISS["FAISS"]
            CHROMA["ChromaDB"]
            REDIS["Redis Vector"]
        end
    end

    CLI --> ORCH
    CLI --> QUC
    API --> QUC

    ORCH --> IUC
    ORCH --> QUC
    
    QUC --> QUERIES
    QUC --> QCACHE
    IUC --> TABLES
    IUC --> DEDUP
    IUC --> ECACHE
    IUC --> EMBCACHE

    TABLES --> IFACE
    QUERIES --> IFACE
    
    ECACHE --> IFACE
    EMBCACHE --> IFACE
    QCACHE --> IFACE

    IFACE -.-> OLLAMA
    IFACE -.-> OPENAI
    IFACE -.-> GROQ
    IFACE -.-> LOCAL
    IFACE -.-> OPENAI_EMB
    IFACE -.-> FAISS
    IFACE -.-> CHROMA
    IFACE -.-> REDIS

    style CLI fill:#4CAF50,color:#fff
    style ORCH fill:#2196F3,color:#fff
    style QUC fill:#2196F3,color:#fff
    style IUC fill:#2196F3,color:#fff
    style IFACE fill:#FF9800,color:#fff
    style ECACHE fill:#9C27B0,color:#fff
    style EMBCACHE fill:#9C27B0,color:#fff
    style QCACHE fill:#9C27B0,color:#fff
```

---

## Layer Descriptions

### 🟢 Core Layer (`src/core/`)

The **shared kernel** - zero external dependencies within the project.

| Module | Purpose |
|--------|---------|
| `paths.py` | Cross-platform path management using `pathlib` |
| `deduplication.py` | SHA256 content-hash PDF deduplication |
| `exceptions.py` | Centralized exception hierarchy |
| `interfaces/` | Python Protocols for dependency injection |

**Key Principle:** Core never imports from other layers.

---

### 🔵 Domain Layer (`src/domain/`)

**Business entities** - pure data models with validation.

```
domain/
├── tables/       # TableMetadata, TableChunk, FinancialTable
├── documents/    # DocumentMetadata, PageLayout, Period
└── queries/      # RAGQuery, RAGResponse, SearchResult
```

**Key Principle:** Domain entities have no infrastructure dependencies.

---

### 🟣 Infrastructure Layer (`src/infrastructure/`)

**External integrations** and caching.

#### Three-Tier Caching System

```mermaid
flowchart LR
    PDF["PDF Upload"] --> T1
    
    subgraph "Tier 1: Extraction Cache"
        T1["Content Hash<br/>SHA256"]
        T1 --> |"30 day TTL"| EC["Extraction Result"]
    end
    
    EC --> T2
    
    subgraph "Tier 2: Embedding Cache"
        T2["Hash + Model"]
        T2 --> |"90 day TTL<br/>Model-aware"| EMB["Embeddings"]
    end
    
    EMB --> VDB["VectorDB"]
    
    QUERY["User Query"] --> T3
    
    subgraph "Tier 3: Query Cache"
        T3["Query + Filters + TopK"]
        T3 --> |"24 hour TTL<br/>Refreshable"| RESP["RAGResponse"]
    end
    
    style T1 fill:#E91E63,color:#fff
    style T2 fill:#9C27B0,color:#fff
    style T3 fill:#673AB7,color:#fff
```

| Cache | Key | TTL | Features |
|-------|-----|-----|----------|
| **Extraction** | Content SHA256 | 30 days | Survives file renames |
| **Embedding** | Hash + Model | 90 days | Invalidates on model change |
| **Query** | Query + Filters | 24 hours | `force_refresh` option |

---

### 🟠 Application Layer (`src/application/`)

**Use cases** that orchestrate domain + infrastructure.

```python
# QueryUseCase - handles query caching automatically
from src.application import get_query_use_case

uc = get_query_use_case()
response = uc.query("What was revenue?", force_refresh=False)
print(f"From cache: {response.from_cache}")
```

---

### ⚙️ Pipeline Layer (`src/pipeline/`)

**Orchestration** with modular steps.

```mermaid
flowchart LR
    subgraph "PipelineOrchestrator"
        DL["Download"]
        EX["Extract"]
        EM["Embed"]
        QR["Query"]
    end
    
    DL --> EX
    EX --> |"Dedup Check"| DEDUP{Duplicate?}
    DEDUP --> |No| EX2["Extract Tables"]
    DEDUP --> |Yes| SKIP["Skip"]
    
    EX2 --> |"Cache Check"| CACHE1{Cached?}
    CACHE1 --> |Yes| USE1["Use Cached"]
    CACHE1 --> |No| PROC1["Process"]
    
    USE1 --> EM
    PROC1 --> EM
    
    EM --> |"Model-Aware Cache"| CACHE2{Cached?}
    CACHE2 --> |Yes| USE2["Use Cached"]
    CACHE2 --> |No| PROC2["Generate Embeddings"]
    
    USE2 --> VDB["Store in VectorDB"]
    PROC2 --> VDB
```

---

## Provider Plug-and-Play

The system uses **Protocol interfaces** for true plug-and-play:

```python
# src/core/interfaces/provider.py
class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str: ...
    def get_model_name(self) -> str: ...

class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> List[float]: ...
    def get_dimension(self) -> int: ...

class VectorStoreProvider(Protocol):
    def add(self, chunks: List[TableChunk]) -> None: ...
    def search(self, query: str, top_k: int) -> List[SearchResult]: ...
```

### Switching Providers

```bash
# .env - Just change the provider name
LLM_PROVIDER=ollama        # or openai, groq
EMBEDDING_PROVIDER=local   # or openai
VECTORDB_PROVIDER=faiss    # or chroma, redis
```

**No code changes required!**

---

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Orchestrator
    participant Dedup
    participant ExtractionCache
    participant Extractor
    participant EmbeddingCache
    participant Embedder
    participant VectorDB
    participant QueryCache
    participant LLM

    User->>CLI: python main.py embed
    CLI->>Orchestrator: run_full_pipeline()
    
    loop For each PDF
        Orchestrator->>Dedup: is_duplicate(pdf)?
        alt Duplicate
            Dedup-->>Orchestrator: Skip
        else New
            Orchestrator->>ExtractionCache: get(content_hash)
            alt Cached
                ExtractionCache-->>Orchestrator: cached_tables
            else Miss
                Orchestrator->>Extractor: extract(pdf)
                Extractor-->>Orchestrator: tables
                Orchestrator->>ExtractionCache: set(hash, tables)
            end
            
            Orchestrator->>EmbeddingCache: get(hash, model)
            alt Cached
                EmbeddingCache-->>Orchestrator: cached_embeddings
            else Miss
                Orchestrator->>Embedder: embed(tables)
                Embedder-->>Orchestrator: embeddings
                Orchestrator->>EmbeddingCache: set(hash, model, embeddings)
            end
            
            Orchestrator->>VectorDB: store(embeddings)
        end
    end
    
    User->>CLI: python main.py query "Revenue?"
    CLI->>QueryCache: get(query, filters)
    alt Cached
        QueryCache-->>User: cached_response
    else Miss
        CLI->>VectorDB: search(query)
        VectorDB-->>CLI: relevant_chunks
        CLI->>LLM: generate(prompt, chunks)
        LLM-->>CLI: response
        CLI->>QueryCache: set(query, response)
        CLI-->>User: response
    end
```

---

## Directory Structure

```
GENAI/
├── src/
│   ├── core/                    # 🟢 Shared Kernel
│   │   ├── paths.py             # Cross-platform paths
│   │   ├── deduplication.py     # PDF content dedup
│   │   ├── exceptions.py        # Exception hierarchy
│   │   └── interfaces/          # Protocol definitions
│   │
│   ├── domain/                  # 🔵 Business Entities
│   │   ├── tables/              # Table entities
│   │   ├── documents/           # Document entities
│   │   └── queries/             # Query/Response entities
│   │
│   ├── infrastructure/          # 🟣 External Adapters & Providers
│   │   ├── cache/               # Three-tier caching
│   │   │   ├── extraction_cache.py  # Tier 1
│   │   │   ├── embedding_cache.py   # Tier 2
│   │   │   └── query_cache.py       # Tier 3
│   │   ├── llm/                 # LLM Providers (Ollama, OpenAI, Groq)
│   │   ├── embeddings/          # Embedding Providers (Local, OpenAI)
│   │   ├── vectordb/            # Vector Stores (FAISS, Chroma, Redis)
│   │   └── extraction/          # PDF Extractors (Docling, PyMuPDF)
│   │
│   ├── application/             # 🟠 Use Cases
│   │   └── use_cases/           # IngestUseCase, QueryUseCase
│   │
│   ├── pipeline/                # ⚙️ Orchestration
│   │   ├── orchestrator.py      # Pipeline coordinator
│   │   └── steps/               # Modular steps
│   │
│   ├── rag/                     # RAG Query Engine
│   ├── retrieval/               # Search & Retrieval
│   ├── cache/                   # Redis Cache (legacy compat)
│   └── models/                  # Schemas (legacy compat)
│
├── config/
│   ├── settings.py              # Pydantic settings (.env)
│   ├── loader.py                # YAML config loader
│   ├── paths.yaml               # Directory paths
│   ├── logging.yaml             # Enterprise logging
│   ├── providers.yaml           # LLM/Embedding/VectorDB
│   ├── prompts.yaml             # Prompt templates
│   └── environments/            # Per-environment configs
│       ├── dev.yaml
│       ├── prod.yaml
│       └── test.yaml
│
├── main.py                      # CLI entry point
└── .env                         # Provider configuration
```

---

## Key Design Decisions

### 1. **Why Protocol Interfaces?**
- Runtime duck-typing (no abstract base classes)
- Easy mocking for tests
- True dependency inversion

### 2. **Why Three-Tier Caching?**
- **Tier 1** saves expensive PDF extraction (~30s/doc)
- **Tier 2** saves embedding API costs and time
- **Tier 3** instant response for repeated queries

### 3. **Why Content-Hash Deduplication?**
- Files renamed? Still detected as duplicate
- No redundant processing
- History persists across runs

### 4. **Why Modular Pipeline Steps?**
- Each step testable in isolation
- Easy to add new steps
- Metrics per step

---

## Future Extensions

The architecture supports:

| Extension | How to Add |
|-----------|------------|
| **REST API** | Add FastAPI routes calling `QueryUseCase` |
| **Chat Interface** | Add `ChatUseCase` in application layer |
| **New LLM** | Implement `LLMProvider` protocol |
| **New VectorDB** | Implement `VectorStoreProvider` protocol |
| **Async Processing** | Add async versions of interfaces |
| **Kubernetes** | Each layer can be a separate service |

---

## Quick Start

```python
# Using the enterprise pipeline
from src.pipeline import get_pipeline

pipeline = get_pipeline()

# Run full ingestion with caching + dedup
result = pipeline.run_full_pipeline(source_dir="raw_data")
print(f"Metrics: {pipeline.get_metrics()}")
print(f"Cache stats: {pipeline.get_cache_stats()}")

# Or use high-level use cases
from src.application import get_query_use_case

uc = get_query_use_case()
response = uc.query("What was Q1 2025 revenue?", force_refresh=False)
print(f"Answer: {response.answer}")
print(f"From cache: {response.from_cache}")
```

---

## Summary

| Aspect | Design Choice |
|--------|--------------|
| **Architecture** | Clean Architecture (Onion) |
| **Coupling** | Loosely coupled via interfaces |
| **Scalability** | Horizontal (each layer independent) |
| **Extensibility** | Plug-and-play via Protocols |
| **Caching** | Three-tier with LRU eviction |
| **Testing** | Interface mocking, isolated steps |
