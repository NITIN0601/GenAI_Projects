"""
Configuration loader for enterprise YAML-based configuration.

Provides:
- YAML configuration loading
- Environment-specific overrides (dev, prod, test)
- Deep merge of config dictionaries
- Environment variable interpolation

Usage:
    from config.loader import load_config, get_config
    
    # Load all config
    config = load_config()
    
    # Access values
    llm_provider = config['providers']['llm']['default_provider']
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


def _get_config_dir() -> Path:
    """Get the config directory path."""
    return Path(__file__).parent


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary with overrides
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def _interpolate_env(config: Dict) -> Dict:
    """
    Interpolate environment variables in config values.
    
    Supports ${VAR_NAME} and ${VAR_NAME:default} syntax.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Config with interpolated values
    """
    import re
    
    def interpolate_value(value: Any) -> Any:
        if isinstance(value, str):
            # Match ${VAR_NAME} or ${VAR_NAME:default}
            pattern = r'\$\{([A-Z_][A-Z0-9_]*)(:[^}]*)?\}'
            
            def replace(match):
                var_name = match.group(1)
                default = match.group(2)[1:] if match.group(2) else None
                return os.environ.get(var_name, default or '')
            
            return re.sub(pattern, replace, value)
        elif isinstance(value, dict):
            return {k: interpolate_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [interpolate_value(item) for item in value]
        return value
    
    return interpolate_value(config)


def load_yaml_file(filepath: Path) -> Dict[str, Any]:
    """
    Load a YAML file.
    
    Args:
        filepath: Path to YAML file
        
    Returns:
        Parsed YAML as dictionary
    """
    if not filepath.exists():
        logger.warning(f"Config file not found: {filepath}")
        return {}
    
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return {}


def load_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Load all configuration with environment overrides.
    
    Args:
        environment: Environment name (dev, prod, test)
                    If None, uses APP_ENV environment variable
                    Defaults to 'dev' if not set
    
    Returns:
        Merged configuration dictionary
    """
    config_dir = _get_config_dir()
    
    # Determine environment
    if environment is None:
        environment = os.environ.get('APP_ENV', 'dev')
    
    logger.info(f"Loading configuration for environment: {environment}")
    
    # Load base configs
    config = {
        'paths': load_yaml_file(config_dir / 'paths.yaml'),
        'logging': load_yaml_file(config_dir / 'logging.yaml'),
        'providers': load_yaml_file(config_dir / 'providers.yaml'),
    }
    
    # Load environment-specific overrides
    env_file = config_dir / 'environments' / f'{environment}.yaml'
    env_config = load_yaml_file(env_file)
    
    if env_config:
        # Merge environment config into base
        config = _deep_merge(config, env_config)
        logger.info(f"Applied environment overrides from {env_file.name}")
    
    # Interpolate environment variables
    config = _interpolate_env(config)
    
    # Add metadata
    config['_meta'] = {
        'environment': environment,
        'config_dir': str(config_dir),
    }
    
    return config


@lru_cache(maxsize=1)
def get_config() -> Dict[str, Any]:
    """
    Get cached configuration (singleton).
    
    Returns:
        Configuration dictionary
    """
    return load_config()


def reload_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Reload configuration (clears cache).
    
    Args:
        environment: Optional environment override
        
    Returns:
        Fresh configuration dictionary
    """
    get_config.cache_clear()
    return load_config(environment)


# Convenience accessors
def get_paths_config() -> Dict[str, Any]:
    """Get paths configuration."""
    return get_config().get('paths', {})


def get_providers_config() -> Dict[str, Any]:
    """Get providers configuration."""
    return get_config().get('providers', {})


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration."""
    return get_config().get('logging', {})


def get_llm_config() -> Dict[str, Any]:
    """Get LLM provider configuration."""
    providers = get_providers_config()
    return providers.get('llm', {})


def get_embedding_config() -> Dict[str, Any]:
    """Get embedding provider configuration."""
    providers = get_providers_config()
    return providers.get('embeddings', {})


def get_vectordb_config() -> Dict[str, Any]:
    """Get VectorDB configuration."""
    providers = get_providers_config()
    return providers.get('vectordb', {})
