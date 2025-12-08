# GENAI System Architecture Diagrams

## 1. Data Processing Pipeline

```mermaid
flowchart TB
    subgraph "1. Data Ingestion"
        SOURCE[(Morgan Stanley<br/>Quarterly Reports)]
        DS[DownloadStep]
        SOURCE --> |10-Q/10-K PDFs| DS
        DS --> |Raw PDFs| RAW[(raw_data/)]
    end
    
    subgraph "2. Extraction"
        ES[ExtractStep]
        EC[(ExtractionCache<br/>Tier 1)]
        UE[UnifiedExtractor]
        DB[DoclingBackend]
        QA[QualityAssessor]
        
        RAW --> ES
        ES --> |Check Cache| EC
        EC --> |Cache Hit| ES
        EC --> |Cache Miss| UE
        UE --> DB
        DB --> QA
        QA --> |Score ≥ 60| EC
    end
    
    subgraph "3. Chunking & Embedding"
        EMS[EmbedStep]
        TC[TableChunker]
        EM[EmbeddingManager]
        EMC[(EmbeddingCache<br/>Tier 2)]
        
        ES --> |Tables + Metadata| EMS
        EMS --> TC
        TC --> |Overlapping Chunks| EM
        EM --> |Check Cache| EMC
        EMC --> |Cache Hit| VDB
        EMC --> |Cache Miss| API
        API[Embedding API] --> EMC
    end
    
    subgraph "4. Storage"
        VDB[(VectorDB)]
        EM --> |Vectors + Metadata| VDB
    end
```

### Data Flow Details

| Step | Input | Output | Cache |
|------|-------|--------|-------|
| **Download** | URL patterns | PDF files | — |
| **Extract** | PDF files | Tables + Metadata | ExtractionCache (content hash) |
| **Chunk** | Tables | Overlapping chunks (10 rows, 3 overlap) | — |
| **Embed** | Text chunks | 768/1536-dim vectors | EmbeddingCache (text hash + model) |
| **Store** | Vectors + Metadata | VectorDB entries | — |

---

## 2. VectorDB Architecture

```mermaid
flowchart TB
    subgraph "VectorDB Manager (Singleton)"
        VDM[VectorDBManager]
        VDI[VectorDBInterface]
        VDM --> VDI
    end
    
    subgraph "Provider Implementations"
        VDI --> FAISS[(FAISS<br/>In-Memory/GPU)]
        VDI --> CHROMA[(ChromaDB<br/>Persistent)]
        VDI --> REDIS[(Redis Vector<br/>Distributed)]
    end
    
    subgraph "FAISS Options"
        FAISS --> FLAT[Flat Index<br/>Exact Search]
        FAISS --> IVF[IVF Index<br/>Approximate]
        FAISS --> HNSW[HNSW Index<br/>Fast Approximate]
    end
    
    subgraph "Horizontal Scaling (Redis)"
        REDIS --> R1[Redis Node 1]
        REDIS --> R2[Redis Node 2]
        REDIS --> R3[Redis Node N]
        LB[Load Balancer] --> R1
        LB --> R2
        LB --> R3
    end
    
    subgraph "Cache Integration"
        QC[(QueryCache<br/>Tier 3)]
        QC --> |Cache Hit| RESPONSE
        QC --> |Cache Miss| VDI
        VDI --> |Results| QC
    end
```

### VectorDB Provider Comparison

| Provider | Use Case | Scaling | Performance |
|----------|----------|---------|-------------|
| **FAISS** | Single instance, GPU | Vertical (GPU) | Fastest search |
| **ChromaDB** | Persistent, small-medium | Single node | Good, persistent |
| **Redis Vector** | Distributed, large scale | Horizontal (cluster) | Network latency |

### Metadata Stored

```
TableMetadata:
├── source_doc, table_id, chunk_reference_id
├── company_name, ticker, year, quarter
├── table_title, table_type, statement_type
├── page_no, row_count, column_count
├── embedding_model, embedding_provider
└── extraction_timestamp
```

---

## 3. User Query Flow

```mermaid
flowchart TB
    subgraph "User Input"
        USER[User Query]
        QS[QueryStep]
    end
    
    subgraph "Query Processing"
        QC[(QueryCache<br/>Tier 3)]
        USER --> QS
        QS --> |Check Cache| QC
        QC --> |Cache Hit| RESP
    end
    
    subgraph "Embedding"
        EM[EmbeddingManager]
        QC --> |Cache Miss| EM
        EM --> |Query Vector| SEARCH
    end
    
    subgraph "Search Orchestration"
        SO[SearchOrchestrator]
        SEARCH --> SO
        
        SO --> SEM[Semantic Search]
        SO --> HYB[Hybrid Search]
        SO --> HYDE[HyDE Search]
        SO --> MQ[Multi-Query]
        
        SEM --> RRF[Reciprocal Rank Fusion]
        HYB --> RRF
        HYDE --> RRF
        MQ --> RRF
    end
    
    subgraph "VectorDB Lookup"
        VDB[(VectorDB)]
        RRF --> VDB
        VDB --> |Top-K Results| RERANK
        RERANK[Reranker<br/>Optional] --> CONTEXT
    end
    
    subgraph "LLM Generation"
        CONTEXT[Retrieved Context]
        PM[PromptManager]
        LM[LLMManager]
        
        CONTEXT --> PM
        PM --> |standard| STD[Financial Analysis Prompt]
        PM --> |few_shot| FS[Few-Shot Examples]
        PM --> |cot| COT[Chain-of-Thought]
        PM --> |react| RE[ReAct Pattern]
        
        STD --> LM
        FS --> LM
        COT --> LM
        RE --> LM
    end
    
    subgraph "Response"
        LM --> |Generate| ANS[Answer]
        ANS --> |Cache| QC
        ANS --> RESP[Response to User]
        
        RESP --> TXT[Text Response]
        RESP --> CSV[CSV Export]
        RESP --> XLS[Excel Export]
    end
```

### Query Flow Details

| Stage | Component | Cache | Fallback |
|-------|-----------|-------|----------|
| **Query Input** | QueryStep | QueryCache (Tier 3) | — |
| **Embedding** | EmbeddingManager | EmbeddingCache (Tier 2) | Sequential API |
| **Search** | SearchOrchestrator | — | Multiple strategies |
| **VectorDB** | VectorDBManager | — | Configurable provider |
| **LLM** | LLMManager | — | Ollama/OpenAI/Custom |
| **Response** | QueryEngine | QueryCache | — |

### Prompt Strategies

| Strategy | Use Case | Template |
|----------|----------|----------|
| **standard** | General financial queries | `FINANCIAL_CHAT_PROMPT` |
| **few_shot** | Complex analysis | 21 examples in `prompts.yaml` |
| **cot** | Multi-step reasoning | `COT_PROMPT` |
| **react** | Tool-using queries | `REACT_PROMPT` |

---

## 4. Caching Architecture (Three Tiers)

```mermaid
flowchart LR
    subgraph "Tier 1: Extraction Cache"
        PDF[PDF File] --> |MD5 Hash| T1[(ExtractionCache)]
        T1 --> |Tables + Metadata| PROC
    end
    
    subgraph "Tier 2: Embedding Cache"
        PROC[Processed Text] --> |Hash + Model| T2[(EmbeddingCache)]
        T2 --> |Vectors| STORE
    end
    
    subgraph "Tier 3: Query Cache"
        QUERY[User Query] --> |Query Hash| T3[(QueryCache)]
        T3 --> |Full Response| USER
    end
    
    subgraph "Redis Backend (Optional)"
        T1 -.-> REDIS[(Redis)]
        T2 -.-> REDIS
        T3 -.-> REDIS
    end
```

### Cache Benefits

| Tier | Skip If Cached | Speed Improvement |
|------|----------------|-------------------|
| **Tier 1** | PDF extraction | 10-30 seconds/file |
| **Tier 2** | Embedding API calls | 100-500ms/chunk |
| **Tier 3** | Full RAG pipeline | 2-5 seconds/query |

---

## 5. Complete System Overview

```mermaid
graph TB
    subgraph "Entry Points"
        CLI[main.py CLI]
        API[Future: FastAPI]
    end
    
    subgraph "Pipeline Layer"
        PM[PipelineManager]
        DS[DownloadStep]
        ES[ExtractStep]
        EMS[EmbedStep]
        SS[SearchStep]
        QS[QueryStep]
        CS[ConsolidateStep]
    end
    
    subgraph "Application Layer"
        IU[IngestUseCase]
        QU[QueryUseCase]
    end
    
    subgraph "RAG Layer"
        QE[QueryEngine]
        SO[SearchOrchestrator]
    end
    
    subgraph "Infrastructure Layer"
        EM[EmbeddingManager]
        VM[VectorDBManager]
        LM[LLMManager]
        CM[CacheManager]
    end
    
    subgraph "External Services"
        EMBED[Embedding API]
        LLM[LLM API]
        VDB[(VectorDB)]
        CACHE[(Redis)]
    end
    
    CLI --> PM
    PM --> DS & ES & EMS & SS & QS & CS
    
    ES --> IU
    QS --> QU
    QU --> QE
    QE --> SO
    
    EMS --> EM & VM
    SO --> VM
    QE --> LM
    
    EM --> EMBED
    LM --> LLM
    VM --> VDB
    CM --> CACHE
```

---

## What's Covered

| Area | Diagrams Include |
|------|------------------|
| ✅ Data Processing | Download → Extract → Chunk → Embed → Store |
| ✅ Caching | Three-tier (Extraction, Embedding, Query) |
| ✅ VectorDB | FAISS, ChromaDB, Redis + horizontal scaling |
| ✅ Query Flow | Embedding → Search strategies → Reranking |
| ✅ LLM Integration | Multiple prompt strategies |
| ✅ Response Formats | Text, CSV, Excel exports |
| ✅ Consolidation | Table aggregation across quarters |
