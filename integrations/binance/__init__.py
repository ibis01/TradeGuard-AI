"""
TradeGuard AI - Binance Integration Module.

Isolates all Binance-specific logic behind an adapter boundary.
The core governance system never imports from this module directly.
"""

from .adapter import ExchangeAdapter, get_adapter
from .paper_adapter import PaperAdapter
from .binance_adapter import BinanceAdapter

__all__ = [
    "ExchangeAdapter",
    "get_adapter",
    "PaperAdapter",
    "BinanceAdapter",
]