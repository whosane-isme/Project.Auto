"""
Unit tests for handlers.
"""

import pytest
import asyncio
from handlers import HANDLERS


@pytest.mark.asyncio
async def test_trigger_returns_event():
    """Test that trigger handler returns the event payload correctly."""
    out = await HANDLERS["trigger"](
        {"event_name": "test.ping"},
        {"event": {"x": 1}, "contact": {}, "steps": {}},
        None,
    )
    assert out == {"event_name": "test.ping", "payload": {"x": 1}}


@pytest.mark.asyncio
async def test_condition_true():
    """Test condition handler with a true expression."""
    ctx = {"event": {"x": 1}, "contact": {}, "steps": {}}
    out = await HANDLERS["condition"]({"expr": "1 == 1"}, ctx, None)
    assert out == {"result": True}


@pytest.mark.asyncio
async def test_condition_false():
    """Test condition handler with a false expression."""
    ctx = {"event": {"x": 2}, "contact": {}, "steps": {}}
    out = await HANDLERS["condition"]({"expr": "1 == 2"}, ctx, None)
    assert out == {"result": False}


@pytest.mark.asyncio
async def test_condition_with_template():
    """Test condition handler with template variables."""
    ctx = {"event": {"x": 5}, "contact": {}, "steps": {}}
    out = await HANDLERS["condition"]({"expr": "{{ event.x }} > 3"}, ctx, None)
    assert out == {"result": True}


@pytest.mark.asyncio
async def test_condition_with_step_reference():
    """Test condition handler referencing previous step results."""
    ctx = {"event": {}, "contact": {}, "steps": {"calc": {"result": 10}}}
    out = await HANDLERS["condition"]({"expr": "{{ steps.calc.result }} == 10"}, ctx, None)
    assert out == {"result": True}


@pytest.mark.asyncio
async def test_set_variable():
    """Test set_variable handler sets a variable correctly."""
    out = await HANDLERS["set_variable"]({"name": "g", "value": "hello"}, {}, None)
    assert out == {"name": "g", "value": "hello"}
