"""
X12 Transaction Mapping Definitions.

Contains declarative mapping definitions for X12 transaction types.
"""

from .invoice_810 import INVOICE_810_MAPPING
from .order_850 import ORDER_850_MAPPING

__all__ = [
    "INVOICE_810_MAPPING",
    "ORDER_850_MAPPING",
]
