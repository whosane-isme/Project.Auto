"""
Handlers module for automation engine.
Contains handler registry and individual handler implementations.
"""

from typing import Dict, Callable, Any
from functools import wraps

# Global handlers registry
HANDLERS: Dict[str, Callable] = {}


def handler(type_name: str):
    """
    Decorator to register a handler function in the HANDLERS dict.
    
    Args:
        type_name: The handler type name (e.g., "trigger", "http", "delay")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        HANDLERS[type_name] = wrapper
        return wrapper
    return decorator

# Import all handlers to register them
from handlers import trigger
from handlers import condition
from handlers import set_variable
from handlers import http_request
from handlers import adam_action
