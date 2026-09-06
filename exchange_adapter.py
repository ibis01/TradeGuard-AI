"""
TradeGuard AI - Exchange Adapter Implementation.

Implements the exchange adapter interface for paper trading and Binance integration.
All exchange-specific code is isolated behind this interface.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class ExchangeAdapter(ABC):
    """Abstract base class defining the exchange adapter interface."""
    
    @abstractmethod
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade order."""
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """Get current portfolio balance."""
        pass


# ============================================================================
# PAPER ADAPTER - Simulation Mode
# ============================================================================

class PaperAdapter(ExchangeAdapter):
    """Paper trading adapter - simulates execution without real money."""
    
    def __init__(self):
        self.mode = "paper"
        self.exchange = "PaperSimulator"
        self._balance = 10000.0
        self._order_counter = 0
        
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a paper trade simulation."""
        try:
            required_fields = ["trade_id", "symbol", "side", "quantity", "entry_price"]
            for field in required_fields:
                if field not in trade_intent:
                    return {
                        "status": "ERROR",
                        "order_id": None,
                        "executed_price": None,
                        "message": f"Missing required field: {field}",
                        "mode": self.mode,
                        "exchange": self.exchange
                    }
            
            trade_id = trade_intent["trade_id"]
            symbol = trade_intent["symbol"]
            side = trade_intent["side"]
            quantity = trade_intent["quantity"]
            entry_price = trade_intent["entry_price"]
            
            # Check if enough balance
            cost = quantity * entry_price
            if cost > self._balance:
                return {
                    "status": "REJECTED",
                    "order_id": None,
                    "executed_price": None,
                    "message": f"Insufficient paper balance: ${cost:,.2f} > ${self._balance:,.2f}",
                    "mode": self.mode,
                    "exchange": self.exchange
                }
            
            # Deduct balance
            self._balance -= cost
            self._order_counter += 1
            order_id = f"paper_{trade_id}_{self._order_counter}"
            
            logger.info(f"[PAPER] {side.upper()} {quantity} {symbol} @ ${entry_price:,.2f} | Balance: ${self._balance:,.2f}")
            
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "executed_price": entry_price,
                "message": f"Paper trade executed: {side.upper()} {quantity} {symbol} @ ${entry_price:,.2f}",
                "mode": self.mode,
                "exchange": self.exchange,
                "balance_remaining": self._balance
            }
            
        except Exception as e:
            logger.error(f"[PAPER] Execution failed: {e}")
            return {
                "status": "ERROR",
                "order_id": None,
                "executed_price": None,
                "message": f"Paper execution failed: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }
    
    def get_balance(self) -> Dict[str, Any]:
        """Get paper trading balance."""
        return {
            "status": "SUCCESS",
            "balance": self._balance,
            "currency": "USDT",
            "mode": self.mode,
            "exchange": self.exchange
        }


# ============================================================================
# BINANCE ADAPTER - Real Exchange Integration (Simplified)
# ============================================================================

class BinanceAdapter(ExchangeAdapter):
    """Binance exchange adapter - executes real trades on Binance."""
    
    def __init__(self, use_testnet: bool = True):
        self.mode = "live" if not use_testnet else "testnet"
        self.exchange = "Binance"
        self.use_testnet = use_testnet
        self.api_key = os.environ.get("BINANCE_API_KEY", "")
        self.secret_key = os.environ.get("BINANCE_SECRET_KEY", "")
        self._client = None
        self._init_client()
        
    def _init_client(self):
        """Initialize the Binance client."""
        try:
            import ccxt
            
            exchange_params = {
                "apiKey": self.api_key,
                "secret": self.secret_key,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"}
            }
            
            if self.use_testnet:
                exchange_params["options"]["testnet"] = True
                exchange_params["urls"] = {
                    "api": {
                        "public": "https://testnet.binance.vision/api/v3",
                        "private": "https://testnet.binance.vision/api/v3",
                    }
                }
            
            self._client = ccxt.binance(exchange_params)
            logger.info(f"[Binance] Client initialized in {'testnet' if self.use_testnet else 'mainnet'} mode")
            
        except ImportError:
            logger.error("ccxt not installed. Install with: pip install ccxt")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            self._client = None
    
    def _ensure_client(self):
        """Ensure the client is initialized."""
        if self._client is None:
            self._init_client()
        return self._client is not None
    
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade on Binance."""
        if not self._ensure_client():
            return {
                "status": "ERROR",
                "order_id": None,
                "executed_price": None,
                "message": "Binance client not initialized",
                "mode": self.mode,
                "exchange": self.exchange
            }
        
        try:
            required_fields = ["trade_id", "symbol", "side", "quantity", "entry_price"]
            for field in required_fields:
                if field not in trade_intent:
                    return {
                        "status": "ERROR",
                        "order_id": None,
                        "executed_price": None,
                        "message": f"Missing required field: {field}",
                        "mode": self.mode,
                        "exchange": self.exchange
                    }
            
            symbol = trade_intent["symbol"]
            side = trade_intent["side"]
            quantity = trade_intent["quantity"]
            entry_price = trade_intent["entry_price"]
            
            binance_symbol = f"{symbol}USDT"
            order_side = "buy" if side == "long" else "sell"
            
            order = self._client.create_order(
                symbol=binance_symbol,
                side=order_side,
                type="LIMIT",
                price=entry_price,
                quantity=quantity,
                timeInForce="GTC"
            )
            
            return {
                "status": "SUCCESS",
                "order_id": order.get("id", str(trade_intent["trade_id"])),
                "executed_price": float(order.get("price", entry_price)),
                "message": f"Binance order placed: {order_side.upper()} {quantity} {symbol} @ ${entry_price:,.2f}",
                "mode": self.mode,
                "exchange": self.exchange,
                "testnet": self.use_testnet
            }
            
        except Exception as e:
            logger.error(f"[Binance] Execution failed: {e}")
            return {
                "status": "ERROR",
                "order_id": None,
                "executed_price": None,
                "message": f"Binance execution failed: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }
    
    def get_balance(self) -> Dict[str, Any]:
        """Get Binance account balance."""
        if not self._ensure_client():
            return {
                "status": "ERROR",
                "balance": 0.0,
                "currency": "USDT",
                "message": "Binance client not initialized",
                "mode": self.mode,
                "exchange": self.exchange
            }
        
        try:
            balance = self._client.fetch_balance()
            usdt_balance = balance.get("USDT", {})
            
            return {
                "status": "SUCCESS",
                "balance": float(usdt_balance.get("free", 0)),
                "currency": "USDT",
                "mode": self.mode,
                "exchange": self.exchange
            }
            
        except Exception as e:
            logger.error(f"[Binance] Failed to get balance: {e}")
            return {
                "status": "ERROR",
                "balance": 0.0,
                "currency": "USDT",
                "message": f"Failed to fetch balance: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }


# ============================================================================
# ADAPTER FACTORY
# ============================================================================

def get_adapter(mode: str = "paper") -> ExchangeAdapter:
    """Factory function to get the appropriate exchange adapter."""
    if mode == "paper":
        return PaperAdapter()
    elif mode == "live":
        try:
            import ccxt
            use_testnet = os.environ.get("BINANCE_USE_MAINNET", "false").lower() != "true"
            return BinanceAdapter(use_testnet=use_testnet)
        except ImportError:
            raise NotImplementedError("ccxt not installed. Install with: pip install ccxt")
    else:
        raise ValueError(f"Unsupported trading mode: {mode}. Use 'paper' or 'live'.")


# ============================================================================
# DASHBOARD COMPATIBILITY
# ============================================================================

def get_adapter_status(mode: str = "paper") -> Dict[str, Any]:
    """Get the status of the exchange adapter for the dashboard."""
    try:
        adapter = get_adapter(mode)
        balance_result = adapter.get_balance()
        
        return {
            "status": "healthy",
            "mode": mode,
            "exchange": getattr(adapter, "exchange", "Unknown"),
            "connected": balance_result.get("status") == "SUCCESS",
            "balance": balance_result.get("balance", 0) if balance_result.get("status") == "SUCCESS" else None,
            "message": "Adapter ready" if balance_result.get("status") == "SUCCESS" else "Adapter error"
        }
    except Exception as e:
        return {
            "status": "error",
            "mode": mode,
            "exchange": "Unknown",
            "connected": False,
            "balance": None,
            "message": str(e)
        }


# ============================================================================
# SELF-TEST
# ============================================================================

if __name__ == "__main__":
    print("🧪 Testing Exchange Adapter...")
    print("=" * 50)
    
    # Test Paper Adapter
    print("\n📊 Testing Paper Adapter:")
    paper = get_adapter("paper")
    
    result = paper.execute_order({
        "trade_id": 1,
        "symbol": "BTC",
        "side": "long",
        "quantity": 0.01,
        "entry_price": 60000.0
    })
    print(f"  ✅ Paper Order: {result.get('message')}")
    
    balance = paper.get_balance()
    print(f"  ✅ Paper Balance: ${balance.get('balance'):,.2f}")
    
    print("\n✅ Exchange Adapter tests complete!")