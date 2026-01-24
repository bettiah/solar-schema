"""
X12 Envelope Segment Definitions.

The envelope segments (ISA/IEA, GS/GE, ST/SE) are not defined in the
standard schema files because they're universal across all transaction types.
This module provides their definitions.
"""

from .gs import (
    GE_SEGMENT,
    GS_SEGMENT,
    SE_SEGMENT,
    ST_SEGMENT,
    parse_ge_segment,
    parse_gs_segment,
    parse_se_segment,
    parse_st_segment,
)
from .isa import (
    IEA_SEGMENT,
    ISA_ELEMENT_POSITIONS,
    ISA_SEGMENT,
    parse_iea_segment,
    parse_isa_segment,
)

__all__ = [
    "ISA_SEGMENT",
    "IEA_SEGMENT",
    "ISA_ELEMENT_POSITIONS",
    "parse_isa_segment",
    "parse_iea_segment",
    "GS_SEGMENT",
    "GE_SEGMENT",
    "ST_SEGMENT",
    "SE_SEGMENT",
    "parse_gs_segment",
    "parse_ge_segment",
    "parse_st_segment",
    "parse_se_segment",
]
