"""
Set variable handler module.
Stores a value into steps.<key>.value for downstream steps.
"""

from typing import Dict, Any
from handlers import handler


@handler("set_variable")
async def set_variable_handler(config: Dict[str, Any], context: Dict[str, Any], run: Any) -> Dict[str, Any]:
    """
    Set variable handler - stores a value for downstream steps.

    Args:
        config: Handler configuration containing name and value
        context: Execution context containing event, contact, and steps
        run: Run instance (can be None)

    Returns:
        Dictionary with name and value
    """
    return {
        "name": config["name"],
        "value": config["value"]
    }
