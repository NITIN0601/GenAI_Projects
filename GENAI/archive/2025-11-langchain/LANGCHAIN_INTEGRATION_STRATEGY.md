# LangChain Integration Strategy for GENAI Repository

## Executive Summary

**Goal:** Convert codebase to use LangChain's orchestrator framework following industry standards (November 2024)

**Recommendation:** **Hybrid Approach** - Use LangChain where it adds value, keep custom code where it's superior

**LangChain Version:** 0.1.x with LangGraph for complex workflows

---

## Complete LangChain Integration Opportunities

### 🔴 **HIGH PRIORITY - Recommended to Implement**

#### 1. **Retrieval Module** (`src/retrieval/`)

**Current State:** Custom implementation  
**LangChain Components to Use:**
- ✅ `BaseRetriever` interface
- ✅ `EnsembleRetriever` for hybrid search
- ✅ `ContextualCompressionRetriever` for context optimization
- ✅ `MultiQueryRetriever` for query expansion
- ✅ `ParentDocumentRetriever` for hierarchical retrieval

**Files to Update:**
- `src/retrieval/search/base.py`
  - Inherit from `langchain.schema.BaseRetriever`
  - Implement `_get_relevant_documents()` method
  
- `src/retrieval/search/strategies/hybrid_search.py`
  - Replace with `langchain.retrievers.EnsembleRetriever`
  - Use built-in RRF fusion
  
- `src/retrieval/search/strategies/multi_query_search.py`
  - Replace with `langchain.retrievers.MultiQueryRetriever`
  - Auto-generates query variations

**Benefits:**
- ✅ Standardized interface
- ✅ Built-in query expansion
- ✅ Automatic context compression
- ✅ Better integration with LangChain ecosystem

**Code Example:**
```python
from langchain.schema import BaseRetriever
from langchain.retrievers import EnsembleRetriever

# Hybrid search with LangChain
vector_retriever = ChromaRetriever(...)
bm25_retriever = BM25Retriever(...)

ensemble = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.6, 0.4]
)

docs = ensemble.get_relevant_documents("query")
```

---

#### 2. **RAG Pipeline** (`src/rag/`)

**Current State:** Custom pipeline  
**LangChain Components to Use:**
- ✅ `RetrievalQA` chain
- ✅ `ConversationalRetrievalChain` for chat
- ✅ `LLMChain` for generation
- ✅ **LangGraph** for complex multi-step workflows

**Files to Update:**
- `src/rag/pipeline.py`
  - Replace with `langchain.chains.RetrievalQA`
  - Use `ConversationalRetrievalChain` for memory
  
- `src/rag/query_understanding.py`
  - Use `LLMChain` for query parsing
  - Use `StructuredOutputParser` for structured extraction

**Benefits:**
- ✅ Built-in memory management
- ✅ Automatic source tracking
- ✅ Stream support
- ✅ Agent capabilities

**Code Example:**
```python
from langchain.chains import RetrievalQA
from langchain_community.llms import Ollama

qa_chain = RetrievalQA.from_chain_type(
    llm=Ollama(model="llama2"),
    chain_type="stuff",
    retriever=ensemble_retriever,
    return_source_documents=True
)

result = qa_chain({"query": "What was revenue?"})
```

---

#### 3. **LLM Integration** (`src/llm/`)

**Current State:** Custom LLM manager  
**LangChain Components to Use:**
- ✅ `BaseLLM` interface
- ✅ `ChatModel` for conversational
- ✅ `langchain_community.llms.Ollama`
- ✅ `langchain_openai.ChatOpenAI`
- ✅ `Callbacks` for monitoring

**Files to Update:**
- `src/llm/manager.py`
  - Inherit from `langchain.llms.base.BaseLLM`
  - Use `langchain_community.llms.Ollama` directly
  
- Create `src/llm/callbacks.py`
  - Use `langchain.callbacks` for streaming
  - Use `LangChainTracer` for debugging

**Benefits:**
- ✅ Standardized interface
- ✅ Built-in streaming
- ✅ Automatic retries
- ✅ Usage tracking
- ✅ Multi-provider support

**Code Example:**
```python
from langchain_community.llms import Ollama
from langchain.callbacks import StreamingStdOutCallbackHandler

llm = Ollama(
    model="llama2",
    callbacks=[StreamingStdOutCallbackHandler()]
)

response = llm.invoke("What was revenue?")
```

---

#### 4. **Prompt Management** (`src/llm/prompts/`)

**Current State:** String templates  
**LangChain Components to Use:**
- ✅ `PromptTemplate`
- ✅ `ChatPromptTemplate`
- ✅ `FewShotPromptTemplate`
- ✅ `PipelinePromptTemplate`
- ✅ **LangChain Hub** for sharing prompts

**Files to Update:**
- `config/prompts.py`
  - Convert to `PromptTemplate` objects
  - Use `ChatPromptTemplate` for chat models
  
- Create `src/llm/prompts/templates.py`
  - Use `FewShotPromptTemplate` for examples
  - Use Hub for versioning

**Benefits:**
- ✅ Input validation
- ✅ Partial variables
- ✅ Template composition
- ✅ Shareable via Hub

**Code Example:**
```python
from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a financial analyst."),
    ("user", "Context: {context}\n\nQuestion: {question}")
])

chain = prompt | llm
result = chain.invoke({"context": "...", "question": "..."})
```

---

#### 5. **Document Processing** (`src/extraction/`)

**Current State:** Custom extraction  
**LangChain Components to Use:**
- ✅ `Document` schema
- ✅ `TextSplitter` (RecursiveCharacterTextSplitter)
- ✅ `DocumentLoader` interface
- ✅ `DocumentTransformer` for preprocessing

**Files to Update:**
- `src/extraction/backends/docling_backend.py`
  - Inherit from `langchain.document_loaders.base.BaseLoader`
  - Return `langchain.schema.Document` objects
  
- Create `src/extraction/splitters.py`
  - Use `RecursiveCharacterTextSplitter`
  - Use `MarkdownHeaderTextSplitter` for tables

**Benefits:**
- ✅ Standardized document format
- ✅ Better chunking strategies
- ✅ Metadata preservation
- ✅ Easy integration

**Code Example:**
```python
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Convert extraction result to LangChain Document
docs = [
    Document(
        page_content=table['content'],
        metadata={
            'source': 'file.pdf',
            'page': 1,
            'table_title': 'Revenue'
        }
    )
    for table in tables
]

# Split if needed
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
split_docs = splitter.split_documents(docs)
```

---

### 🟡 **MEDIUM PRIORITY - Consider Implementing**

#### 6. **Vector Store Integration** (`src/vector_store/`)

**Current State:** Custom wrappers  
**LangChain Components to Use:**
- ✅ `VectorStore` interface
- ✅ `langchain_community.vectorstores.Chroma`
- ✅ `langchain_community.vectorstores.FAISS`
- ✅ `langchain_community.vectorstores.Redis`

**Files to Update:**
- `src/vector_store/stores/chromadb_store.py`
  - Inherit from `langchain.vectorstores.Chroma`
  - Use built-in methods
  
- `src/vector_store/stores/faiss_store.py`
  - Inherit from `langchain.vectorstores.FAISS`

**Benefits:**
- ✅ Standardized interface
- ✅ Automatic batching
- ✅ Built-in similarity search types
- ✅ Easy switching between stores

**Code Example:**
```python
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

vectorstore = Chroma(
    collection_name="financial_tables",
    embedding_function=HuggingFaceEmbeddings(),
    persist_directory="./chroma_db"
)

# Use as retriever
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 10, "fetch_k": 50}
)
```

---

#### 7. **Caching Layer** (`src/cache/`)

**Current State:** Custom cache  
**LangChain Components to Use:**
- ✅ `InMemoryCache`
- ✅ `SQLiteCache`
- ✅ `RedisCache`
- ✅ `set_llm_cache()` for LLM responses

**Files to Update:**
- `src/cache/backends/redis_cache.py`
  - Use `langchain.cache.RedisCache`
  - Automatic cache key generation

**Benefits:**
- ✅ Automatic caching
- ✅ TTL support
- ✅ Semantic caching
- ✅ Less code to maintain

**Code Example:**
```python
from langchain.cache import RedisCache
from langchain.globals import set_llm_cache
import redis

set_llm_cache(RedisCache(
    redis_=redis.Redis(host='localhost', port=6379)
))

# Automatically caches LLM responses
```

---

#### 8. **Embeddings** (`src/embeddings/`)

**Current State:** Custom wrapper  
**LangChain Components to Use:**
- ✅ `Embeddings` interface
- ✅ `langchain_community.embeddings.HuggingFaceEmbeddings`
- ✅ `langchain_openai.OpenAIEmbeddings`
- ✅ `CacheBackedEmbeddings` for caching

**Files to Update:**
- `src/embeddings/manager.py`
  - Use `HuggingFaceEmbeddings` directly
  - Use `CacheBackedEmbeddings` for caching

**Benefits:**
- ✅ Automatic batching
- ✅ Built-in caching
- ✅ Multi-provider support
- ✅ Async support

**Code Example:**
```python
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

underlying = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

store = LocalFileStore("./embedding_cache/")
embeddings = CacheBackedEmbeddings.from_bytes_store(
    underlying, store, namespace="embeddings"
)
```

---

### 🟢 **LOW PRIORITY - Future Consideration**

#### 9. **Agents & Tools** (NEW)

**Current State:** Not implemented  
**LangChain Components to Use:**
- ✅ **LangGraph** for agent workflows
- ✅ `AgentExecutor` for tool calling
- ✅ `Tool` interface for custom tools
- ✅ `create_react_agent()` for reasoning

**New Files to Create:**
- `src/agents/tools.py`
  - Create tools for table analysis
  - Create tools for calculations
  
- `src/agents/graph.py`
  - Use LangGraph for multi-step reasoning
  - Financial analysis workflows

**Benefits:**
- ✅ Multi-step reasoning
- ✅ Tool calling
- ✅ Complex workflows
- ✅ State management

**Code Example:**
```python
from langgraph.graph import StateGraph, END
from langchain.agents import create_react_agent

# Define tools
tools = [
    Tool(
        name="search_tables",
        description="Search financial tables",
        func=retriever.get_relevant_documents
    ),
    Tool(
        name="calculate",
        description="Perform calculations",
        func=calculator
    )
]

# Create agent
agent = create_react_agent(llm, tools, prompt)

# Execute
agent_executor = AgentExecutor(agent=agent, tools=tools)
result = agent_executor.invoke({"input": "Calculate revenue growth"})
```

---

#### 10. **Memory & Chat History** (NEW)

**Current State:** Not implemented  
**LangChain Components to Use:**
- ✅ `ConversationBufferMemory`
- ✅ `ConversationSummaryMemory`
- ✅ `VectorStoreBackedMemory`
- ✅ `RedisChatMessageHistory`

**New Files to Create:**
- `src/memory/manager.py`
  - Conversation memory
  - User session management

**Benefits:**
- ✅ Conversation context
- ✅ Multi-turn queries
- ✅ User personalization

---

#### 11. **Output Parsers** (NEW)

**Current State:** Manual parsing  
**LangChain Components to Use:**
- ✅ `StructuredOutputParser`
- ✅ `PydanticOutputParser`
- ✅ `JSONOutputParser`
- ✅ `OutputFixingParser` for error correction

**New Files to Create:**
- `src/parsers/financial.py`
  - Parse financial metrics
  - Extract structured data

**Benefits:**
- ✅ Structured outputs
- ✅ Type validation
- ✅ Error handling

---

#### 12. **Evaluation & Monitoring** (NEW)

**Current State:** Not implemented  
**LangChain Components to Use:**
- ✅ **LangSmith** for tracing
- ✅ `load_evaluator()` for quality metrics
- ✅ `RunEvaluator` for chain evaluation

**New Files to Create:**
- `src/evaluation/metrics.py`
  - Evaluate retrieval quality
  - Evaluate answer quality

**Benefits:**
- ✅ Performance monitoring
- ✅ Quality metrics
- ✅ Debugging traces

---

## Implementation Priority

### Phase 1: Core LangChain Integration (Completed ✅)
1. ✅ **LLM Integration** - Replace with `langchain_community.llms.Ollama`
2. ✅ **Prompt Templates** - Convert to `PromptTemplate`
3. ✅ **Document Schema** - Use `langchain.schema.Document`
4. ✅ **Retrieval Interface** - Inherit from `BaseRetriever`

### Phase 2: Advanced Retrieval (Completed ✅)
5. ✅ **Hybrid Search** - Use `EnsembleRetriever`
6. ✅ **Multi-Query** - Use `MultiQueryRetriever`
7. ✅ **RAG Chain** - Use `RetrievalQA` (Implemented via LCEL)
8. ✅ **Vector Store** - Use LangChain vectorstore wrappers (Chroma)
9. ✅ **Embeddings** - Use `Embeddings` interface

### Phase 3: Orchestration & Agents (Future Work)
10. ⬜ **LangGraph Workflows** - Complex multi-step analysis
11. ⬜ **Agent Tools** - Financial analysis tools
12. ⬜ **Memory** - Conversation management
13. ⬜ **Monitoring** - LangSmith integration

---

## Recommended Architecture

### Before (Custom)
```
main.py → Custom RAG Pipeline → Custom Retriever → Custom Vector Store
```

### After (LangChain)
```
main.py → LangGraph Workflow → RetrievalQA Chain → EnsembleRetriever → LangChain VectorStore
                                      ↓
                                 LangSmith (Monitoring)
```

---

## Key LangChain Packages Needed

```python
# requirements.txt
langchain>=0.1.0
langchain-community>=0.0.20
langchain-openai>=0.0.5
langgraph>=0.0.20
langsmith>=0.0.70

# Specific integrations
langchain-chroma>=0.1.0
langchain-redis>=0.0.2
```

---

## Migration Strategy

### Option 1: Gradual Migration (RECOMMENDED)
- Keep existing code working
- Add LangChain alternatives alongside
- Migrate module by module
- A/B test performance

### Option 2: Full Rewrite
- Rewrite entire codebase with LangChain
- Faster to implement
- Higher risk

**Recommendation: Option 1** - Gradual migration with coexistence

---

## Benefits of LangChain Integration

### ✅ **Pros**
1. **Standardization** - Industry-standard interfaces
2. **Ecosystem** - Access to 1000+ integrations
3. **Community** - Large community, frequent updates
4. **Tools** - LangSmith monitoring, debugging
5. **Agents** - Built-in agent capabilities
6. **Memory** - Conversation management
7. **Less Code** - Use battle-tested components

### ⚠️ **Cons**
1. **Dependencies** - Large dependency tree (~500MB)
2. **Abstraction** - Less control over internals
3. **Learning Curve** - Team needs to learn LangChain
4. **Version Changes** - Fast-moving project, breaking changes
5. **Overhead** - Some performance overhead

---

## Final Recommendation

### **Hybrid Approach:**

**Use LangChain for:**
- ✅ LLM integration (`langchain_community.llms.Ollama`)
- ✅ Prompt management (`PromptTemplate`)
- ✅ RAG chains (`RetrievalQA`)
- ✅ Agents & workflows (`LangGraph`)
- ✅ Monitoring (`LangSmith`)

**Keep Custom for:**
- ✅ Extraction (Docling is superior)
- ✅ Vector store logic (custom metadata needs)
- ✅ BM25 retrieval (our implementation is good)
- ✅ Financial-specific parsing

This gives you **best of both worlds**: LangChain's ecosystem + custom optimizations!

---

**Next Steps:**
1. Review this analysis
2. Decide on migration approach
3. Start with Phase 1 (LLM + Prompts)
4. Gradually migrate other components
5. A/B test to ensure quality

Want me to implement Phase 1?
