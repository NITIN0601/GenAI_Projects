"""
Tier 1: Extraction Cache

Content-hash based caching for PDF extraction results.
Key: SHA256 hash of PDF content (survives file renames)
TTL: 30 days (extraction results don't change)
"""

import hashlib
from pathlib import Path
from typing import Optional, Any
import logging

from src.infrastructure.cache.base import BaseCache

logger = logging.getLogger(__name__)


class ExtractionCache(BaseCache[Any]):
    """
    Content-hash based extraction cache.
    
    Uses SHA256 of PDF content as cache key, so renamed files
    still get cache hits if content is identical.
    
    Example:
        >>> cache = ExtractionCache()
        >>> result = cache.get_by_content(pdf_path)
        >>> if result is None:
        ...     result = extractor.extract(pdf_path)
        ...     cache.set_by_content(pdf_path, result)
    """
    
    DEFAULT_TTL_HOURS = 24 * 30  # 30 days
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        max_entries: Optional[int] = 500,
        enabled: bool = True,
    ):
        """
        Initialize extraction cache.
        
        Args:
            cache_dir: Cache directory (default: .cache/extraction)
            ttl_hours: TTL in hours (default: 30 days)
            max_entries: Max entries (default: 500)
            enabled: Enable caching
        """
        if cache_dir is None:
            from src.core.paths import get_paths
            cache_dir = get_paths().extraction_cache_dir
        
        super().__init__(
            cache_dir=cache_dir,
            name="ExtractionCache",
            ttl_hours=ttl_hours,
            max_entries=max_entries,
            enabled=enabled,
        )
    
    def compute_content_hash(self, pdf_path: Path) -> str:
        """
        Compute SHA256 hash of PDF content.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            SHA256 hash as hex string
        """
        pdf_path = Path(pdf_path)
        sha256 = hashlib.sha256()
        
        with open(pdf_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def get_by_content(self, pdf_path: Path) -> Optional[Any]:
        """
        Get cached result by PDF content hash.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Cached ExtractionResult or None
        """
        try:
            content_hash = self.compute_content_hash(pdf_path)
            return self.get(content_hash)
        except FileNotFoundError:
            return None
    
    def set_by_content(self, pdf_path: Path, result: Any) -> str:
        """
        Cache result by PDF content hash.
        
        Args:
            pdf_path: Path to PDF file
            result: ExtractionResult to cache
            
        Returns:
            Content hash used as key
        """
        content_hash = self.compute_content_hash(pdf_path)
        self.set(content_hash, result)
        return content_hash
    
    def exists_by_content(self, pdf_path: Path) -> bool:
        """Check if PDF content is cached."""
        try:
            content_hash = self.compute_content_hash(pdf_path)
            return self.exists(content_hash)
        except FileNotFoundError:
            return False
