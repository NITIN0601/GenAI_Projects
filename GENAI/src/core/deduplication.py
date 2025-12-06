"""
Content-based PDF deduplication with history tracking.

Uses SHA256 content hash to detect duplicate PDFs regardless of filename.
Maintains a JSON history file for tracking processed documents.

Example:
    >>> from src.core import get_deduplicator
    >>> dedup = get_deduplicator()
    >>> is_dup, original = dedup.is_duplicate(Path("10q0625.pdf"))
    >>> if not is_dup:
    ...     # Process the PDF
    ...     dedup.register(Path("10q0625.pdf"))
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class PDFDeduplicator:
    """
    Content-based PDF deduplication with history tracking.
    
    Uses SHA256 hash of file content to detect duplicates regardless
    of filename changes. Maintains a persistent JSON history file
    for tracking which PDFs have been processed.
    
    Attributes:
        history_file: Path to JSON file storing processing history
        history: In-memory dict of content_hash -> file info
    """
    
    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize PDFDeduplicator.
        
        Args:
            history_file: Path to history JSON file (default: .cache/pdf_history.json)
        """
        if history_file is None:
            from src.core.paths import get_paths
            history_file = get_paths().pdf_history_file
        
        self.history_file = Path(history_file)
        self.history: Dict[str, dict] = self._load_history()
        
        logger.debug(f"PDFDeduplicator initialized with {len(self.history)} entries")
    
    # =========================================================================
    # Core Methods
    # =========================================================================
    
    def compute_content_hash(self, pdf_path: Path) -> str:
        """
        Compute SHA256 hash of PDF file content.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            SHA256 hash as hex string
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        sha256 = hashlib.sha256()
        with open(pdf_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def is_duplicate(self, pdf_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if PDF is a duplicate based on content hash.
        
        Args:
            pdf_path: Path to PDF file to check
            
        Returns:
            Tuple of (is_duplicate, original_filename if duplicate else None)
            
        Example:
            >>> is_dup, original = dedup.is_duplicate(Path("report.pdf"))
            >>> if is_dup:
            ...     print(f"Duplicate of: {original}")
        """
        pdf_path = Path(pdf_path)
        
        try:
            content_hash = self.compute_content_hash(pdf_path)
        except FileNotFoundError:
            return False, None
        
        if content_hash in self.history:
            original_info = self.history[content_hash]
            logger.info(
                f"Duplicate detected: {pdf_path.name} matches {original_info['filename']}"
            )
            return True, original_info['filename']
        
        return False, None
    
    def register(self, pdf_path: Path, metadata: Optional[dict] = None) -> str:
        """
        Register PDF in history after successful processing.
        
        Args:
            pdf_path: Path to PDF file
            metadata: Optional additional metadata to store
            
        Returns:
            Content hash of the registered file
        """
        pdf_path = Path(pdf_path)
        content_hash = self.compute_content_hash(pdf_path)
        
        self.history[content_hash] = {
            'filename': pdf_path.name,
            'path': str(pdf_path.absolute()),
            'size_bytes': pdf_path.stat().st_size,
            'processed_at': datetime.now().isoformat(),
            'metadata': metadata or {},
        }
        
        self._save_history()
        
        logger.info(f"Registered PDF: {pdf_path.name} (hash: {content_hash[:12]}...)")
        
        return content_hash
    
    def unregister(self, pdf_path: Path) -> bool:
        """
        Remove PDF from history (for reprocessing).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if removed, False if not found
        """
        pdf_path = Path(pdf_path)
        
        try:
            content_hash = self.compute_content_hash(pdf_path)
        except FileNotFoundError:
            return False
        
        if content_hash in self.history:
            del self.history[content_hash]
            self._save_history()
            logger.info(f"Unregistered PDF: {pdf_path.name}")
            return True
        
        return False
    
    def get_hash(self, pdf_path: Path) -> Optional[str]:
        """
        Get stored hash for a PDF if it exists in history.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Content hash if found, None otherwise
        """
        try:
            content_hash = self.compute_content_hash(pdf_path)
            return content_hash if content_hash in self.history else None
        except FileNotFoundError:
            return None
    
    # =========================================================================
    # History Management
    # =========================================================================
    
    def _load_history(self) -> Dict[str, dict]:
        """Load history from JSON file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load history: {e}. Starting fresh.")
                return {}
        return {}
    
    def _save_history(self) -> None:
        """Save history to JSON file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, default=str)
    
    def clear_history(self) -> int:
        """
        Clear all history entries.
        
        Returns:
            Number of entries cleared
        """
        count = len(self.history)
        self.history.clear()
        self._save_history()
        logger.info(f"Cleared {count} entries from PDF history")
        return count
    
    def get_stats(self) -> dict:
        """
        Get statistics about processed PDFs.
        
        Returns:
            Dictionary with stats
        """
        total_size = sum(
            entry.get('size_bytes', 0) 
            for entry in self.history.values()
        )
        
        return {
            'total_files': len(self.history),
            'total_size_mb': total_size / (1024 * 1024),
            'history_file': str(self.history_file),
        }
    
    def __repr__(self) -> str:
        return f"PDFDeduplicator(entries={len(self.history)}, file={self.history_file.name})"


# =========================================================================
# Singleton Instance
# =========================================================================

_deduplicator: Optional[PDFDeduplicator] = None


@lru_cache(maxsize=1)
def get_deduplicator() -> PDFDeduplicator:
    """
    Get global PDFDeduplicator instance (singleton).
    
    Returns:
        PDFDeduplicator instance
    """
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = PDFDeduplicator()
    return _deduplicator


def reset_deduplicator():
    """Reset the global PDFDeduplicator (for testing)."""
    global _deduplicator
    _deduplicator = None
    get_deduplicator.cache_clear()
