"""
Metrics and monitoring for extraction system.
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ExtractionMetrics:
    """Metrics for a single extraction."""
    pdf_path: str
    backend: str
    success: bool
    tables_found: int
    quality_score: float
    extraction_time: float
    timestamp: str
    error: str = None


class MetricsCollector:
    """Collect and store extraction metrics."""
    
    def __init__(self, metrics_dir: str = ".metrics/extraction"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: List[ExtractionMetrics] = []
    
    def record_extraction(
        self,
        pdf_path: str,
        backend: str,
        success: bool,
        tables_found: int,
        quality_score: float,
        extraction_time: float,
        error: str = None
    ):
        """Record extraction metrics."""
        metric = ExtractionMetrics(
            pdf_path=pdf_path,
            backend=backend,
            success=success,
            tables_found=tables_found,
            quality_score=quality_score,
            extraction_time=extraction_time,
            timestamp=datetime.now().isoformat(),
            error=error
        )
        
        self.metrics.append(metric)
        
        # Save to file
        self._save_metric(metric)
    
    def _save_metric(self, metric: ExtractionMetrics):
        """Save metric to daily file."""
        date_str = datetime.now().strftime('%Y%m%d')
        metrics_file = self.metrics_dir / f"metrics_{date_str}.jsonl"
        
        with open(metrics_file, 'a') as f:
            f.write(json.dumps(asdict(metric)) + '\n')
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        if not self.metrics:
            return {"total_extractions": 0}
        
        total = len(self.metrics)
        successful = sum(1 for m in self.metrics if m.success)
        
        # Backend stats
        backend_stats = defaultdict(lambda: {"count": 0, "success": 0, "avg_time": 0.0})
        for m in self.metrics:
            backend_stats[m.backend]["count"] += 1
            if m.success:
                backend_stats[m.backend]["success"] += 1
            backend_stats[m.backend]["avg_time"] += m.extraction_time
        
        # Calculate averages
        for backend, stats in backend_stats.items():
            if stats["count"] > 0:
                stats["avg_time"] /= stats["count"]
                stats["success_rate"] = stats["success"] / stats["count"] * 100
        
        return {
            "total_extractions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total * 100 if total > 0 else 0,
            "avg_quality_score": sum(m.quality_score for m in self.metrics if m.success) / successful if successful > 0 else 0,
            "avg_extraction_time": sum(m.extraction_time for m in self.metrics) / total,
            "total_tables": sum(m.tables_found for m in self.metrics),
            "backend_stats": dict(backend_stats)
        }
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent metrics."""
        return [asdict(m) for m in self.metrics[-limit:]]


# Global metrics collector
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
