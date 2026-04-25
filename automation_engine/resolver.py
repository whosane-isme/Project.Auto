"""
Variable resolver module.
Resolves Jinja2 templates in configuration dictionaries.
"""

from typing import Dict, Any
import jinja2


class StepError(Exception):
    """Raised when a step execution fails."""
    pass


def resolve_vars(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolve Jinja2 templates in a configuration dictionary.

    Args:
        config: Configuration dictionary that may contain template strings
        context: Context dictionary with variables (event, contact, steps)

    Returns:
        Configuration dictionary with all templates resolved

    Raises:
        StepError: If a template references an undefined variable
    """
    # Create Jinja2 environment with strict undefined behavior
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)

    def resolve_value(value: Any) -> Any:
        """Recursively resolve templates in a value."""
        if isinstance(value, str):
            # Strip whitespace and check if it looks like a variable reference
            stripped = value.strip()
            if stripped and not stripped.startswith('{'):
                # Convert space-delimited format to Jinja2 template
                # e.g., " event.x " -> "{{ event.x }}"
                template_str = f"{{{{ {stripped} }}}}"
            else:
                template_str = value
            
            try:
                template = env.from_string(template_str)
                return template.render(**context)
            except jinja2.UndefinedError as e:
                raise StepError(f"Undefined variable in template: {e}")
        elif isinstance(value, dict):
            return {k: resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [resolve_value(item) for item in value]
        else:
            return value

    return resolve_value(config)
