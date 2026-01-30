"""
Tests for BuilderMappingEngine handler utilities.

Transaction-specific tests live in:
- test_builder_850.py
- test_builder_810.py
"""

import pytest


class TestHandlerBase:
    """Test base handler utilities."""

    def test_set_box_path_simple(self):
        from box import Box
        from edi_schema.semantic.mapping.handlers.base import set_box_path

        builder = Box(default_box=True)
        set_box_path(builder, "id", "test-123")
        assert builder.id == "test-123"

    def test_set_box_path_nested(self):
        from box import Box
        from edi_schema.semantic.mapping.handlers.base import set_box_path

        builder = Box(default_box=True)
        set_box_path(builder, "order_reference.id", "REF-001")
        assert builder.order_reference.id == "REF-001"

    def test_set_box_path_list_index(self):
        from box import Box
        from edi_schema.semantic.mapping.handlers.base import ensure_list, set_box_path

        builder = Box(default_box=True)
        lst = ensure_list(builder, "delivery")
        lst.append(Box(default_box=True))
        set_box_path(builder, "delivery[0].id", "DEL-001")
        assert builder.delivery[0].id == "DEL-001"

    def test_strip_empty_boxes(self):
        from edi_schema.semantic.mapping.handlers.base import strip_empty_boxes

        d = {"a": "value", "b": {}, "c": {"d": {}}, "e": {"f": "ok"}}
        result = strip_empty_boxes(d)
        assert result == {"a": "value", "e": {"f": "ok"}}

    def test_strip_empty_boxes_preserves_values(self):
        from edi_schema.semantic.mapping.handlers.base import strip_empty_boxes

        d = {"a": 0, "b": False, "c": "", "d": None}
        result = strip_empty_boxes(d)
        # 0, False, "" are all preserved; None is stripped
        assert result == {"a": 0, "b": False, "c": ""}


class TestHandlerContext:
    """Test HandlerContext."""

    def test_next_index(self):
        from edi_schema.semantic.mapping.handlers.base import HandlerContext
        from edi_schema.semantic.mapping.errors import ErrorAccumulator, ErrorHandlingMode

        ctx = HandlerContext(
            metrics=None,
            trace=None,
            accumulator=ErrorAccumulator(mode=ErrorHandlingMode.LENIENT),
        )
        assert ctx.next_index("delivery") == 0
        assert ctx.next_index("delivery") == 1
        assert ctx.next_index("order_lines") == 0
        assert ctx.next_index("delivery") == 2
