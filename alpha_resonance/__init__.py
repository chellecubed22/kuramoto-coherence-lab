"""
Alpha Resonance OS — unified computational framework.
"""

from .constants import ALPHA, KAPPA_CAP, DT, TOTAL_TIME
from .cmt import CMTSimulator, NetworkType
from .operators import DualPathEngine
from .telascura import TelascuraLattice
from .evidence import EvidenceLayer
from .composite import AlphaResonanceOS

__version__ = "1.2.0"
__all__ = [
    "ALPHA",
    "KAPPA_CAP",
    "DT",
    "TOTAL_TIME",
    "CMTSimulator",
    "NetworkType",
    "DualPathEngine",
    "TelascuraLattice",
    "EvidenceLayer",
    "AlphaResonanceOS",
]