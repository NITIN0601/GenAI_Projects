"""
Configuration package.

Provides:
- Pydantic settings (for .env and defaults)
- YAML config loader (for paths, logging, providers)
- Environment-specific overrides

Usage:
    from config import settings  # Pydantic settings
    from config import get_config, get_paths_config  # YAML config
"""

from config.settings import settings
from config.loader import (
    load_config,
    get_config,
    reload_config,
    get_paths_config,
    get_providers_config,
    get_logging_config,
    get_llm_config,
    get_embedding_config,
    get_vectordb_config,
)

__all__ = [
    'settings',
    'load_config',
    'get_config',
    'reload_config',
    'get_paths_config',
    'get_providers_config',
    'get_logging_config',
    'get_llm_config',
    'get_embedding_config',
    'get_vectordb_config',
]

