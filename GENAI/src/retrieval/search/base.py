"""
Base interface for all search strategies.

Industry standard: Strategy Pattern + LangChain Retriever
- Inherits from LangChain's BaseRetriever
- Compatible with LangChain chains and agents
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pydantic import Field

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

# Re-export config and result classes
@dataclass
class SearchConfig:
    """Configuration for search strategy."""
    top_k: int = 10
    similarity_threshold: float = 0.7
    filters: Optional[Dict[str, Any]] = None
    hybrid_weights: Optional[Dict[str, float]] = field(
        default_factory=lambda: {"vector": 0.6, "keyword": 0.4}
    )
    hybrid_fusion_method: str = "rrf"
    num_queries: int = 3
    multi_query_temperature: float = 0.8
    hyde_prompt_template: Optional[str] = None
    hyde_max_tokens: int = 200
    hyde_temperature: float = 0.7
    use_reranking: bool = False
    reranking_top_k: int = 20
    enable_caching: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class SearchResult:
    """Result from search strategy."""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    strategy: str
    embedding: Optional[List[float]] = None
    rerank_score: Optional[float] = None
    retrieved_at: datetime = field(default_factory=datetime.now)

    def to_doc(self) -> Document:
        """Convert to LangChain Document."""
        metadata = self.metadata.copy()
        metadata.update({
            "score": self.score,
            "strategy": self.strategy,
            "id": self.id
        })
        if self.rerank_score:
            metadata["rerank_score"] = self.rerank_score
            
        return Document(
            page_content=self.content,
            metadata=metadata
        )


class SearchStrategy(str, Enum):
    """Available search strategies."""
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


class BaseSearchStrategy(BaseRetriever):
    """
    Base class for all search strategies.
    
    Inherits from LangChain's BaseRetriever to ensure compatibility
    with LangChain ecosystem (chains, agents, etc.).
    """
    
    # Pydantic fields for LangChain
    vector_store: Any = None
    embedding_manager: Any = None
    llm_manager: Any = None
    config: SearchConfig = Field(default_factory=SearchConfig)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        vector_store,
        embedding_manager=None,
        llm_manager=None,
        config: Optional[SearchConfig] = None,
        **kwargs
    ):
        """Initialize search strategy."""
        # Initialize Pydantic model
        super().__init__(**kwargs)
        
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.llm_manager = llm_manager
        self.config = config or SearchConfig()
        
        if not self.validate_config():
            raise ValueError(f"Invalid configuration for {self.get_strategy_name()}")

    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """
        LangChain standard interface implementation.
        """
        results = self.search(query)
        return [r.to_doc() for r in results]

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """Execute search strategy."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return strategy name."""
        pass
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        if self.config.top_k <= 0:
            return False
        return True
        
    def _convert_to_search_results(
        self,
        raw_results: List[Dict[str, Any]],
        strategy_name: str
    ) -> List[SearchResult]:
        """Convert raw results to SearchResult objects."""
        search_results = []
        for result in raw_results:
            search_results.append(SearchResult(
                id=result.get('id', ''),
                content=result.get('content', result.get('document', '')),
                metadata=result.get('metadata', {}),
                score=result.get('score', result.get('distance', 0.0)),
                strategy=strategy_name
            ))
        return search_results
