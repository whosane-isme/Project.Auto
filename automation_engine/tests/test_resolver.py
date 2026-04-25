"""
Unit tests for the variable resolver.
"""

import pytest
from resolver import resolve_vars, StepError


def test_simple_event_var():
    """Test resolving a simple event variable."""
    ctx = {"event": {"x": 1}, "contact": {}, "steps": {}}
    result = resolve_vars({"v": " event.x "}, ctx)
    assert result == {"v": "1"}


def test_nested():
    """Test resolving a nested step variable."""
    ctx = {"event": {}, "contact": {}, "steps": {"s1": {"out": "done"}}}
    result = resolve_vars({"a": {"b": " steps.s1.out "}}, ctx)
    assert result == {"a": {"b": "done"}}


def test_unknown_var_raises():
    """Test that unknown variables raise StepError."""
    ctx = {"event": {}, "contact": {}, "steps": {}}
    with pytest.raises(StepError):
        resolve_vars({"v": " event.missing "}, ctx)
