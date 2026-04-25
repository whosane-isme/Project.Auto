"""
Trigger handler module.
Handles trigger events by returning the event payload.
"""

from typing import Dict, Any
from handlers import handler


@handler("trigger")
async def trigger_handler(config: Dict[str, Any], context: Dict[str, Any], run: Any) -> Dict[str, Any]:
    """
    Trigger handler - returns the event payload.
    
    Args:
        config: Handler configuration containing event_name
        context: Execution context containing event, contact, and steps
        run: Run instance (can be None)
    
    Returns:
        Dictionary with event_name and payload
    """
    return {
        "event_name": config["event_name"],
        "payload": context["event"]
    }
