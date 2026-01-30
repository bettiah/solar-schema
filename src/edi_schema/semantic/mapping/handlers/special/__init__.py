"""
Special segment handlers for the Builder Mapping Engine.

Each handler encapsulates logic for a specific segment type that requires
custom processing beyond simple field mapping.
"""

from .amt import AMTHandler
from .cad import CADHandler
from .dtm_despatch import DTMDespatchHandler
from .fob import FOBHandler
from .msg import MSGHandler
from .nte import NTEHandler
from .per import HeaderPERHandler
from .sac import SACHandler
from .td5 import TD5Handler
from .tds import TDSHandler
from .txi import TXIHandler

__all__ = [
    "AMTHandler",
    "CADHandler",
    "DTMDespatchHandler",
    "FOBHandler",
    "HeaderPERHandler",
    "MSGHandler",
    "NTEHandler",
    "SACHandler",
    "TD5Handler",
    "TDSHandler",
    "TXIHandler",
]
