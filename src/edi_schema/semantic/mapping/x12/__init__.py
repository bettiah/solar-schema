"""
X12 Transaction Mapping Definitions.

Contains declarative mapping definitions for X12 transaction types.
"""

from .order_850 import ORDER_850_MAPPING

__all__ = [
    "ORDER_850_MAPPING",
]
