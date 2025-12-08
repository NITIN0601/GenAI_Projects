"""
Evaluation Provider Base Classes.

Defines the abstract base for evaluation providers,
enabling modular switching between RAGAS, heuristic, and custom evaluators.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from src.utils import get_logger

logger = get_logger(__name__)


class EvaluationProvider(str, Enum):
    """Available evaluation providers."""
    HEURISTIC = "heuristic"   # Fast, no LLM required
    RAGAS = "ragas"           # Industry-standard, requires LLM
    HYBRID = "hybrid"         # Heuristic + RAGAS for comprehensive eval


@dataclass
class MetricScore:
    """Individual metric score with metadata."""
    name: str
    score: float  # 0.0 - 1.0
    category: str  # 'retrieval', 'generation', 'faithfulness'
    source: str   # 'heuristic' or 'ragas'
    details: Optional[str] = None
    
    def to_row(self) -> List[str]:
        """Convert to table row."""
        return [
            self.name,
            f"{self.score:.3f}",
            self.category,
            self.source,
            self.details or "-"
        ]


@dataclass
class EvaluationScores:
    """
    Comprehensive evaluation scores with table display.
    
    Supports both heuristic and RAGAS metrics in a unified format.
    """
    metrics: List[MetricScore] = field(default_factory=list)
    overall_score: float = 0.0
    provider: str = "heuristic"
    evaluation_time_ms: float = 0.0
    
    # Derived scores
    retrieval_score: float = 0.0
    generation_score: float = 0.0
    faithfulness_score: float = 0.0
    
    # Flags
    hallucination_detected: bool = False
    is_reliable: bool = True
    warnings: List[str] = field(default_factory=list)
    
    def add_metric(self, metric: MetricScore):
        """Add a metric score."""
        self.metrics.append(metric)
    
    def compute_category_scores(self):
        """Compute category averages from individual metrics."""
        categories = {'retrieval': [], 'generation': [], 'faithfulness': []}
        
        for m in self.metrics:
            if m.category in categories:
                categories[m.category].append(m.score)
        
        if categories['retrieval']:
            self.retrieval_score = sum(categories['retrieval']) / len(categories['retrieval'])
        if categories['generation']:
            self.generation_score = sum(categories['generation']) / len(categories['generation'])
        if categories['faithfulness']:
            self.faithfulness_score = sum(categories['faithfulness']) / len(categories['faithfulness'])
        
        # Overall is weighted average
        all_scores = [m.score for m in self.metrics]
        if all_scores:
            self.overall_score = sum(all_scores) / len(all_scores)
    
    def to_table(self) -> str:
        """
        Convert scores to formatted table string.
        
        Returns:
            Formatted markdown table of all metrics
        """
        if not self.metrics:
            return "No metrics available"
        
        lines = [
            "| Metric | Score | Category | Source | Details |",
            "|--------|-------|----------|--------|---------|",
        ]
        
        for metric in self.metrics:
            row = metric.to_row()
            lines.append(f"| {' | '.join(row)} |")
        
        # Add summary row
        lines.append("|--------|-------|----------|--------|---------|")
        lines.append(f"| **Overall** | **{self.overall_score:.3f}** | - | {self.provider} | - |")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'overall_score': self.overall_score,
            'retrieval_score': self.retrieval_score,
            'generation_score': self.generation_score,
            'faithfulness_score': self.faithfulness_score,
            'hallucination_detected': self.hallucination_detected,
            'is_reliable': self.is_reliable,
            'provider': self.provider,
            'evaluation_time_ms': self.evaluation_time_ms,
            'warnings': self.warnings,
            'metrics': [
                {
                    'name': m.name,
                    'score': m.score,
                    'category': m.category,
                    'source': m.source,
                }
                for m in self.metrics
            ]
        }
    
    def print_table(self):
        """Print formatted table to console."""
        try:
            from rich.console import Console
            from rich.table import Table
            
            console = Console()
            table = Table(title="Evaluation Scores")
            
            table.add_column("Metric", style="cyan")
            table.add_column("Score", style="green")
            table.add_column("Category", style="magenta")
            table.add_column("Source", style="yellow")
            
            for metric in self.metrics:
                score_style = "green" if metric.score >= 0.7 else "yellow" if metric.score >= 0.5 else "red"
                table.add_row(
                    metric.name,
                    f"{metric.score:.3f}",
                    metric.category,
                    metric.source,
                    style=score_style if metric.score < 0.5 else None
                )
            
            # Summary row
            table.add_section()
            overall_style = "bold green" if self.overall_score >= 0.7 else "bold yellow" if self.overall_score >= 0.5 else "bold red"
            table.add_row(
                "Overall",
                f"{self.overall_score:.3f}",
                "-",
                self.provider,
                style=overall_style
            )
            
            console.print(table)
            
        except ImportError:
            print(self.to_table())


class BaseEvaluator(ABC):
    """
    Abstract base class for evaluation providers.
    
    Implement this to create new evaluation backends.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass
    
    @property
    @abstractmethod
    def requires_llm(self) -> bool:
        """Return True if this evaluator requires LLM calls."""
        pass
    
    @abstractmethod
    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        **kwargs
    ) -> EvaluationScores:
        """
        Perform evaluation.
        
        Args:
            query: User query
            answer: LLM-generated answer
            contexts: Retrieved context strings
            **kwargs: Additional provider-specific arguments
            
        Returns:
            EvaluationScores with all metrics
        """
        pass
    
    def quick_check(
        self,
        answer: str,
        contexts: List[str],
    ) -> Dict[str, Any]:
        """
        Quick evaluation for real-time use.
        
        Returns minimal metrics for fast feedback.
        """
        # Default implementation - override for efficiency
        result = self.evaluate("", answer, contexts)
        return {
            'is_reliable': result.is_reliable,
            'hallucination_detected': result.hallucination_detected,
            'overall_score': result.overall_score,
        }
