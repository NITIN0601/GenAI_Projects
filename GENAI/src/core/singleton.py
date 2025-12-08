"""
Thread-safe Singleton Pattern for GENAI.

Provides a reusable metaclass for creating thread-safe singleton instances.
Used by all infrastructure managers to ensure consistent instance management.

Example:
    >>> class MyManager(metaclass=ThreadSafeSingleton):
    ...     def __init__(self, config=None):
    ...         self.config = config
    >>> 
    >>> # First call initializes
    >>> manager1 = MyManager(config="test")
    >>> # Subsequent calls return same instance
    >>> manager2 = MyManager()
    >>> assert manager1 is manager2
    >>> 
    >>> # Reset for testing
    >>> MyManager._reset_instance()
"""

import threading
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar('T')


class ThreadSafeSingleton(type):
    """
    Thread-safe singleton metaclass.
    
    Usage:
        class MySingleton(metaclass=ThreadSafeSingleton):
            def __init__(self, value):
                self.value = value
    
    Features:
    - Thread-safe instance creation using double-checked locking
    - Optional reset for testing via _reset_instance()
    - Preserves constructor arguments from first call
    """
    
    _instances: Dict[Type, Any] = {}
    _locks: Dict[Type, threading.Lock] = {}
    _global_lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        """Create or return the singleton instance."""
        # Fast path - instance already exists
        if cls in cls._instances:
            return cls._instances[cls]
        
        # Slow path - need to create instance with lock
        # Ensure we have a lock for this class
        with cls._global_lock:
            if cls not in cls._locks:
                cls._locks[cls] = threading.Lock()
        
        # Double-checked locking pattern
        with cls._locks[cls]:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            return cls._instances[cls]
    
    def _reset_instance(cls) -> None:
        """
        Reset the singleton instance.
        
        Primarily for testing purposes. Allows creating a fresh instance
        with different configuration.
        
        Example:
            >>> MyManager._reset_instance()
            >>> new_manager = MyManager(new_config="test")
        """
        with cls._global_lock:
            if cls in cls._instances:
                del cls._instances[cls]
            if cls in cls._locks:
                del cls._locks[cls]
    
    def _get_instance(cls) -> Optional[Any]:
        """
        Get the current instance without creating one.
        
        Returns:
            The singleton instance if it exists, None otherwise.
        """
        return cls._instances.get(cls)
    
    def _has_instance(cls) -> bool:
        """
        Check if an instance exists.
        
        Returns:
            True if singleton instance exists, False otherwise.
        """
        return cls in cls._instances


def get_or_create_singleton(
    cls: Type[T],
    *args,
    **kwargs
) -> T:
    """
    Utility function to get or create a singleton instance.
    
    Works with classes that have ThreadSafeSingleton metaclass.
    
    Args:
        cls: The singleton class
        *args: Constructor arguments (used only on first call)
        **kwargs: Constructor keyword arguments (used only on first call)
        
    Returns:
        The singleton instance
    """
    return cls(*args, **kwargs)


def reset_all_singletons() -> None:
    """
    Reset all singleton instances.
    
    Useful for testing teardown.
    """
    with ThreadSafeSingleton._global_lock:
        ThreadSafeSingleton._instances.clear()
        ThreadSafeSingleton._locks.clear()
