"""
Handler registry: maps transaction IDs to their special segment handlers.

This replaces the scattered `if transaction_id in ("850", "810")` guards
in the old MappingEngine.
"""

from __future__ import annotations

from .special.amt import AMTHandler
from .special.cad import CADHandler
from .special.dtm_despatch import DTMDespatchHandler
from .special.fob import FOBHandler
from .special.msg import MSGHandler
from .special.nte import NTEHandler
from .special.per import HeaderPERHandler
from .special.sac import SACHandler
from .special.td5 import TD5Handler
from .special.tds import TDSHandler
from .special.txi import TXIHandler

# Singleton handler instances (stateless, safe to share)
_sac = SACHandler()
_txi = TXIHandler()
_fob = FOBHandler()
_td5 = TD5Handler()
_msg = MSGHandler()
_amt = AMTHandler()
_tds = TDSHandler()
_cad = CADHandler()
_nte = NTEHandler()
_per = HeaderPERHandler()
_dtm_despatch = DTMDespatchHandler()

# Registry: transaction_id -> segment_tag -> list of handlers
# These are the "special" handlers that go beyond declarative field/qualified mappings.
HANDLER_REGISTRY: dict[str, dict[str, list]] = {
    "850": {
        "SAC": [_sac],
        "TXI": [_txi],
        "FOB": [_fob],
        "TD5": [_td5],
        "MSG": [_msg],
        "AMT": [_amt],
        "DTM": [_dtm_despatch],
        "PER": [_per],
    },
    "810": {
        "SAC": [_sac],
        "TXI": [_txi],
        "FOB": [_fob],
        "TD5": [_td5],
        "MSG": [_msg],
        "AMT": [_amt],
        "TDS": [_tds],
        "CAD": [_cad],
        "NTE": [_nte],
        "DTM": [_dtm_despatch],
        "PER": [_per],
    },
    "856": {
        "SAC": [_sac],
        "FOB": [_fob],
        "TD5": [_td5],
        "MSG": [_msg],
        "AMT": [_amt],
        "DTM": [_dtm_despatch],
        "PER": [_per],
    },
}

# Line-level special handlers: invoked per loop item (PO1, IT1)
# These handlers receive an item_prefix parameter.
LINE_HANDLER_REGISTRY: dict[str, dict[str, list]] = {
    "850": {
        "PO1": {"SAC": [_sac]},
    },
    "810": {
        "IT1": {"SAC": [_sac], "TXI": [_txi]},
    },
}
