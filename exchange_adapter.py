"""
TradeGuard AI - Exchange Adapter Interface (Sprint 6).

Defines the contract between governance core and exchange implementations.
All exchange-specific code MUST be isolated behind this interface.

INTEGRATION CONTRACT:
- Governance core calls execute_order() after validating APPROVED state
- Adapter handles exchange-specific execution logic
- Adapter returns standardized result format
- No exchange-specific imports in governance core
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class ExchangeAdapter(ABC):
    """
    Abstract base class defining the exchange adapter interface.
    
    All exchange implementations (paper, binance, etc.) must implement this interface.
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


def get_adapter(mode: str = "paper") -> ExchangeAdapter:
    """
    Factory function to get the appropriate exchange adapter.
    
    Args:
        mode: "paper" (default) or "live"
    
    Returns:
        ExchangeAdapter instance
    
    Raises:
        ValueError: If mode is not supported
        NotImplementedError: If live mode is requested but not configured
    """
    if mode == "paper":
        from paper_adapter import PaperAdapter
        return PaperAdapter()
    elif mode == "live":
        # Check if Binance adapter is available
        try:
            from binance_adapter import BinanceAdapter
            import os
            
            # Default to testnet for safety unless explicitly configured
            use_testnet = os.environ.get("BINANCE_USE_MAINNET", "false").lower() != "true"
            
            return BinanceAdapter(use_testnet=use_testnet)
        except ImportError:
            raise NotImplementedError(
                "Binance adapter not available. "
                "Ensure binance_adapter.py exists and ccxt is installed."
            )
    else:
        raise ValueError(f"Unsupported trading mode: {mode}. Use 'paper' or 'live'.")