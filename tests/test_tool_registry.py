"""
tests/test_tool_registry.py

Tests for tools/registry.py's generic Tool shape - see
docs/learn/day-03/01-tool-registry/01a-tool-registry.md Step 1.
"""

import pytest

from tools.registry import Tool


def _dummy_handler(args):
    return args["a"] + args["b"]


def test_tool_can_be_constructed_with_all_required_fields():
    tool = Tool(
        name="add",
        description="Add two numbers together.",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        handler=_dummy_handler,
        blast_radius="read_only",
    )
    assert tool.name == "add"
    assert tool.blast_radius == "read_only"
    assert tool.check_fn is None


def test_handler_is_callable_and_produces_a_real_result():
    tool = Tool(
        name="add",
        description="Add two numbers together.",
        parameters={"type": "object", "properties": {}},
        handler=_dummy_handler,
        blast_radius="read_only",
    )
    result = tool.handler({"a": 7, "b": 5})
    assert result == 12


def test_check_fn_defaults_to_none_meaning_always_available():
    tool = Tool(
        name="add",
        description="...",
        parameters={"type": "object", "properties": {}},
        handler=_dummy_handler,
        blast_radius="read_only",
    )
    assert tool.check_fn is None


def test_check_fn_can_be_set_to_a_real_availability_callable():
    tool = Tool(
        name="browser_nav",
        description="...",
        parameters={"type": "object", "properties": {}},
        handler=_dummy_handler,
        blast_radius="reversible_write",
        check_fn=lambda: False,
    )
    assert tool.check_fn() is False


def test_blast_radius_is_required_not_defaulted():
    """blast_radius has no default value - constructing a Tool without
    it must fail, per docs/standards/SECURITY.md's 'every tool gets an
    explicit tier at registration time, never inferred later' rule."""
    with pytest.raises(TypeError):
        Tool(
            name="add",
            description="...",
            parameters={"type": "object", "properties": {}},
            handler=_dummy_handler,
        )
