"""
TradeGuard AI - Exchange Adapter Interface.

Defines the contract between the governance core and exchange implementations.
All exchange-specific code MUST be isolated behind this interface.

Constitution §5: Binance Integration Boundary
Constitution §6: Paper Trading vs Live Trading
"""

import os
from typing import Dict, Any
from abc import ABC, abstractmethod


class ExchangeAdapter(ABC):
    """
    Abstract base class defining the exchange adapter interface.
    
    All exchange implementations (paper, binance, etc.) must implement this interface.
    The governance core interacts only with this interface, never with exchange-specific code.
    """
    
    @abstractmethod
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade order.
        
        Args:
            trade_intent: Validated trade parameters from governance engine
                {
                    "trade_id": int,
                    "symbol": str,
                    "side": str,  # "long" or "short"
                    "quantity": float,
                    "entry_price": float,
                    "stop_loss": float,
                    "take_profit": Optional[float],
                    "proposal_hash": str
                }
        
        Returns:
            {
                "status": "SUCCESS" | "REJECTED" | "ERROR",
                "order_id": Optional[str],
                "execution_price": Optional[float],
                "message": str,
                "mode": str  # "paper" or "live"
            }
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """
        Get current portfolio balance.
        
        Returns:
            {
                "status": "SUCCESS" | "ERROR",
                "balance": float,
                "currency": str,
                "mode": str
            }
        """
        pass
    
    @abstractmethod
    def get_open_positions(self) -> Dict[str, Any]:
        """
        Get all open positions.
        
        Returns:
            {
                "status": "SUCCESS" | "ERROR",
                "positions": List[Dict],
                "mode": str
            }
        """
        pass


def get_adapter(mode: str = None) -> ExchangeAdapter:
    """
    Factory function to get the appropriate exchange adapter.
    
    Constitution §6: Paper and live environments must be explicitly separated.
    Default is "paper" for safety.
    
    Args:
        mode: "paper" (default) or "live"
    
    Returns:
        ExchangeAdapter instance
    
    Raises:
        ValueError: If mode is not supported
    """
    if mode is None:
        mode = os.environ.get("TRADING_MODE", "paper").lower()
    
    if mode == "paper":
        from .paper_adapter import PaperAdapter
        return PaperAdapter()
    elif mode == "live":
        from .binance_adapter import BinanceAdapter
        return BinanceAdapter()
    else:
        raise ValueError(f"Unsupported trading mode: {mode}. Use 'paper' or 'live'.")