"""
Cross-platform path management.

Provides centralized path configuration that works on Windows, Mac, and Linux.
Uses pathlib.Path for cross-platform compatibility.

Directory Structure:
    data/
    ├── raw/           # Downloaded PDFs
    ├── processed/     # Processed data
    └── cache/         # Application cache (extraction, embeddings, queries)
    
    outputs/
    ├── extraction_reports/
    ├── consolidated_tables/
    └── exports/
    
    logs/              # Application logs

Example:
    >>> from src.core import PathManager, get_paths
    >>> paths = get_paths()
    >>> paths.cache_dir
    PosixPath('/path/to/project/data/cache')
"""

import platform
from pathlib import Path
from typing import Optional
from functools import lru_cache


class PathManager:
    """
    Cross-platform path manager.
    
    All paths are resolved relative to the project root and use
    pathlib.Path for cross-platform compatibility.
    
    Attributes:
        project_root: Base directory of the project
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize PathManager.
        
        Args:
            project_root: Override project root (default: auto-detect)
        """
        self._project_root = project_root or self._detect_project_root()
        self._platform = platform.system()
    
    @staticmethod
    def _detect_project_root() -> Path:
        """Auto-detect project root by finding config/ directory."""
        current = Path(__file__).resolve()
        # Go up from src/core/paths.py to project root
        for _ in range(5):  # Max 5 levels up
            if (current / 'config').exists() and (current / 'src').exists():
                return current
            current = current.parent
        # Fallback: 3 levels up from this file
        return Path(__file__).parent.parent.parent.resolve()
    
    # =========================================================================
    # System Info
    # =========================================================================
    
    @property
    def platform(self) -> str:
        """Get current platform (Windows, Darwin, Linux)."""
        return self._platform
    
    @property
    def is_windows(self) -> bool:
        """Check if running on Windows."""
        return self._platform == 'Windows'
    
    # =========================================================================
    # Base Directories
    # =========================================================================
    
    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root
    
    @property
    def src_dir(self) -> Path:
        """Get src/ directory."""
        return self._project_root / 'src'
    
    @property
    def config_dir(self) -> Path:
        """Get config/ directory."""
        return self._project_root / 'config'
    
    @property
    def scripts_dir(self) -> Path:
        """Get scripts/ directory."""
        return self._project_root / 'scripts'
    
    @property
    def tests_dir(self) -> Path:
        """Get tests/ directory."""
        return self._project_root / 'tests'
    
    # =========================================================================
    # Data Directories (Primary Data Folder)
    # =========================================================================
    
    @property
    def data_dir(self) -> Path:
        """Get data/ directory."""
        path = self._project_root / 'data'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def raw_data_dir(self) -> Path:
        """Get data/raw/ directory (PDF storage)."""
        path = self.data_dir / 'raw'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def processed_data_dir(self) -> Path:
        """Get data/processed/ directory."""
        path = self.data_dir / 'processed'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # =========================================================================
    # Cache Directories (Three-Tier) - in data/cache/
    # =========================================================================
    
    @property
    def cache_dir(self) -> Path:
        """Get data/cache/ base directory."""
        path = self.data_dir / 'cache'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def extraction_cache_dir(self) -> Path:
        """Get data/cache/extraction/ directory (Tier 1)."""
        path = self.cache_dir / 'extraction'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def embedding_cache_dir(self) -> Path:
        """Get data/cache/embeddings/ directory (Tier 2)."""
        path = self.cache_dir / 'embeddings'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def query_cache_dir(self) -> Path:
        """Get data/cache/queries/ directory (Tier 3)."""
        path = self.cache_dir / 'queries'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def pdf_history_file(self) -> Path:
        """Get path to PDF deduplication history file."""
        return self.cache_dir / 'pdf_history.json'
    
    # =========================================================================
    # Output Directories
    # =========================================================================
    
    @property
    def outputs_dir(self) -> Path:
        """Get outputs/ base directory."""
        path = self._project_root / 'outputs'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def extraction_reports_dir(self) -> Path:
        """Get outputs/extraction_reports/ directory."""
        path = self.outputs_dir / 'extraction_reports'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def consolidated_dir(self) -> Path:
        """Get outputs/consolidated_tables/ directory."""
        path = self.outputs_dir / 'consolidated_tables'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def exports_dir(self) -> Path:
        """Get outputs/exports/ directory."""
        path = self.outputs_dir / 'exports'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def reports_dir(self) -> Path:
        """Get outputs/reports/ directory."""
        path = self.outputs_dir / 'reports'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # =========================================================================
    # Logs Directory (Simple - no user subdirectories)
    # =========================================================================
    
    @property
    def logs_dir(self) -> Path:
        """Get logs/ directory."""
        path = self._project_root / 'logs'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # =========================================================================
    # VectorDB Directories
    # =========================================================================
    
    @property
    def faiss_index_dir(self) -> Path:
        """Get faiss_index/ directory."""
        path = self._project_root / 'faiss_index'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def chroma_db_dir(self) -> Path:
        """Get chroma_db/ directory."""
        path = self._project_root / 'chroma_db'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists, create if not."""
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_relative(self, path: Path) -> Path:
        """Get path relative to project root."""
        try:
            return path.relative_to(self._project_root)
        except ValueError:
            return path
    
    def __repr__(self) -> str:
        return f"PathManager(root={self._project_root})"


# =========================================================================
# Singleton Instance
# =========================================================================

_path_manager: Optional[PathManager] = None


@lru_cache(maxsize=1)
def get_paths() -> PathManager:
    """
    Get global PathManager instance (singleton).
    
    Returns:
        PathManager instance configured for the project
    
    Example:
        >>> paths = get_paths()
        >>> paths.cache_dir
        PosixPath('/project/data/cache')
    """
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


def reset_paths():
    """Reset the global PathManager (for testing)."""
    global _path_manager
    _path_manager = None
    get_paths.cache_clear()

