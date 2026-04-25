"""
Condition handler - evaluates boolean expressions.
"""

from typing import Dict, Any
from simpleeval import simple_eval
from resolver import resolve_vars, StepError
from handlers import handler


@handler("condition")
async def condition_handler(config: Dict[str, Any], context: Dict[str, Any], run) -> Dict[str, Any]:
    """
    Evaluate a boolean expression against the current context.

    Args:
        config: Configuration dict with "expr" key containing the expression
        context: Current execution context (event, contact, steps)
        run: Run object (not used in condition handler)

    Returns:
        Dict with "result" key containing boolean evaluation result

    Raises:
        StepError: If expression evaluation fails
    """
    try:
        # Get the expression from config
        expr_template = config.get("expr", "")

        # Resolve any template variables in the expression
        resolved_config = resolve_vars({"expr": expr_template}, context)
        expr = resolved_config["expr"]

        # Evaluate the expression safely using simpleeval
        result = simple_eval(expr)

        # Ensure result is boolean
        if not isinstance(result, bool):
            raise StepError(f"Expression '{expr}' did not evaluate to a boolean (got {type(result).__name__}: {result})")

        return {"result": result}

    except Exception as e:
        raise StepError(f"Failed to evaluate condition expression '{expr_template}': {str(e)}")
