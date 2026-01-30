"""Handler modules for the Builder Mapping Engine."""

from .base import HandlerContext, LoopHandler, SegmentHandler, set_box_path, strip_empty_boxes
from .field import FieldMappingHandler
from .loop import LoopItemHandler
from .party import PartyLoopHandler
from .qualified import QualifiedMappingHandler
from .registry import HANDLER_REGISTRY

__all__ = [
    "HandlerContext",
    "SegmentHandler",
    "LoopHandler",
    "set_box_path",
    "strip_empty_boxes",
    "FieldMappingHandler",
    "QualifiedMappingHandler",
    "LoopItemHandler",
    "PartyLoopHandler",
    "HANDLER_REGISTRY",
]
