"""
TradeGuard AI - Exchange Adapter Implementation.

Implements the exchange adapter interface for paper trading and Binance integration.
All exchange-specific code is isolated behind this interface.

INTEGRATION CONTRACT:
- Governance core calls execute_order() after validating APPROVED state
- Adapter handles exchange-specific execution logic
- Adapter returns standardized result format
- No exchange-specific imports in governance core
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

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
                "executed_price": Optional[float],
                "message": str,
                "mode": str,  # "paper" or "live"
                "exchange": str
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
                "mode": str,
                "exchange": str
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
                "mode": str,
                "exchange": str
            }
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            order_id: Exchange order ID to cancel
        
        Returns:
            {
                "status": "SUCCESS" | "ERROR",
                "order_id": str,
                "message": str,
                "mode": str
            }
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get the status of an order.
        
        Args:
            order_id: Exchange order ID to check
        
        Returns:
            {
                "status": "SUCCESS" | "ERROR",
                "order_id": str,
                "order_status": str,  # "open", "closed", "canceled"
                "executed_price": Optional[float],
                "executed_quantity": Optional[float],
                "message": str,
                "mode": str
            }
        """
        pass


# ============================================================================
# PAPER ADAPTER - Simulation Mode
# ============================================================================

class PaperAdapter(ExchangeAdapter):
    """
    Paper trading adapter - simulates execution without real money.
    Used for testing and demonstration purposes.
    """
    
    def __init__(self):
        self.mode = "paper"
        self.exchange = "PaperSimulator"
        self._balance = 10000.0  # Starting balance for paper trading
        self._open_positions: List[Dict[str, Any]] = []
        self._executed_orders: List[Dict[str, Any]] = []
        self._order_counter = 0
        
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a paper trade simulation.
        """
        try:
            # Validate required fields
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
            stop_loss = trade_intent.get("stop_loss")
            take_profit = trade_intent.get("take_profit")
            
            # Calculate cost
            cost = quantity * entry_price
            
            # Check if enough balance (paper simulation)
            if cost > self._balance:
                return {
                    "status": "REJECTED",
                    "order_id": None,
                    "executed_price": None,
                    "message": f"Insufficient paper balance: ${cost:,.2f} > ${self._balance:,.2f}",
                    "mode": self.mode,
                    "exchange": self.exchange
                }
            
            # Deduct from balance for long positions (paper simulation)
            if side == "long":
                self._balance -= cost
                logger.info(f"[PAPER] Long position opened: {quantity} {symbol} @ ${entry_price:,.2f} | Cost: ${cost:,.2f} | Balance: ${self._balance:,.2f}")
            else:
                # For short positions, we simulate by locking balance as collateral
                self._balance -= cost * 0.5  # 50% margin for shorts
                logger.info(f"[PAPER] Short position opened: {quantity} {symbol} @ ${entry_price:,.2f} | Collateral: ${cost * 0.5:,.2f} | Balance: ${self._balance:,.2f}")
            
            # Generate order ID
            self._order_counter += 1
            order_id = f"paper_{trade_id}_{self._order_counter}"
            
            # Store order
            order = {
                "order_id": order_id,
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "executed_price": entry_price,
                "executed_quantity": quantity,
                "status": "filled",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "proposal_hash": trade_intent.get("proposal_hash")
            }
            
            # Track position
            position = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "current_price": entry_price,
                "unrealized_pnl": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            self._open_positions.append(position)
            self._executed_orders.append(order)
            
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
        """
        Get paper trading balance.
        """
        # Calculate unrealized P&L from open positions
        total_unrealized_pnl = 0.0
        for position in self._open_positions:
            current_price = position.get("current_price", position["entry_price"])
            if position["side"] == "long":
                pnl = (current_price - position["entry_price"]) * position["quantity"]
            else:
                pnl = (position["entry_price"] - current_price) * position["quantity"]
            total_unrealized_pnl += pnl
        
        total_balance = self._balance + total_unrealized_pnl
        
        return {
            "status": "SUCCESS",
            "balance": total_balance,
            "available_balance": self._balance,
            "unrealized_pnl": total_unrealized_pnl,
            "currency": "USDT",
            "mode": self.mode,
            "exchange": self.exchange,
            "open_positions": len(self._open_positions)
        }
    
    def get_open_positions(self) -> Dict[str, Any]:
        """
        Get paper trading open positions.
        """
        # Update current prices (simulated)
        for position in self._open_positions:
            # In paper mode, price doesn't change unless we simulate
            position["current_price"] = position["entry_price"]
            position["unrealized_pnl"] = 0.0
        
        return {
            "status": "SUCCESS",
            "positions": self._open_positions,
            "count": len(self._open_positions),
            "mode": self.mode,
            "exchange": self.exchange
        }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a paper order (simulated).
        """
        # Find order
        for order in self._executed_orders:
            if order.get("order_id") == order_id:
                if order.get("status") == "filled":
                    return {
                        "status": "ERROR",
                        "order_id": order_id,
                        "message": "Order already filled, cannot cancel",
                        "mode": self.mode
                    }
        
        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "message": "Order cancelled (paper simulation)",
            "mode": self.mode,
            "exchange": self.exchange
        }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get paper order status.
        """
        for order in self._executed_orders:
            if order.get("order_id") == order_id:
                return {
                    "status": "SUCCESS",
                    "order_id": order_id,
                    "order_status": order.get("status", "unknown"),
                    "executed_price": order.get("executed_price"),
                    "executed_quantity": order.get("executed_quantity"),
                    "message": f"Order {order_id} status: {order.get('status')}",
                    "mode": self.mode,
                    "exchange": self.exchange,
                    "details": order
                }
        
        return {
            "status": "ERROR",
            "order_id": order_id,
            "order_status": "not_found",
            "executed_price": None,
            "executed_quantity": None,
            "message": f"Order {order_id} not found",
            "mode": self.mode,
            "exchange": self.exchange
        }


# ============================================================================
# BINANCE ADAPTER - Real Exchange Integration
# ============================================================================

class BinanceAdapter(ExchangeAdapter):
    """
    Binance exchange adapter - executes real trades on Binance.
    Supports both testnet and mainnet.
    """
    
    def __init__(self, use_testnet: bool = True):
        self.mode = "live" if not use_testnet else "testnet"
        self.exchange = "Binance"
        self.use_testnet = use_testnet
        self.api_key = os.environ.get("BINANCE_API_KEY", "")
        self.secret_key = os.environ.get("BINANCE_SECRET_KEY", "")
        self._client = None
        
        # Validate credentials
        if not self.api_key or not self.secret_key:
            if not use_testnet:  # Only warn for mainnet
                logger.warning("Binance API credentials not set. Falling back to testnet.")
                self.use_testnet = True
                self.mode = "testnet"
        
        # Initialize client lazily
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
        """
        Execute a trade on Binance.
        """
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
            # Validate required fields
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
            
            # Format symbol for Binance
            binance_symbol = f"{symbol}USDT"
            
            # Determine order side
            order_side = "buy" if side == "long" else "sell"
            
            # Use LIMIT order for precise execution
            order_params = {
                "symbol": binance_symbol,
                "side": order_side,
                "type": "LIMIT",
                "price": trade_intent["entry_price"],
                "quantity": quantity,
                "timeInForce": "GTC"  # Good 'til canceled
            }
            
            # Execute order
            logger.info(f"[Binance] Submitting order: {order_params}")
            response = self._client.create_order(**order_params)
            
            order_id = response.get("id", str(trade_intent["trade_id"]))
            
            # Check if order was filled immediately
            status = response.get("status", "unknown")
            executed_price = float(response.get("price", trade_intent["entry_price"]))
            executed_qty = float(response.get("filled", 0))
            
            if executed_qty > 0:
                executed_price = float(response.get("price", trade_intent["entry_price"]))
                message = f"Order {order_side.upper()} {executed_qty} {symbol} @ ${executed_price:,.2f}"
            else:
                message = f"Order placed, waiting for fill"
            
            return {
                "status": "SUCCESS" if status in ["filled", "closed"] else "PENDING",
                "order_id": order_id,
                "executed_price": executed_price if executed_qty > 0 else None,
                "message": message,
                "mode": self.mode,
                "exchange": self.exchange,
                "order_response": response,
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
        """
        Get Binance account balance.
        """
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
            # Fetch balance for USDT
            balance = self._client.fetch_balance()
            usdt_balance = balance.get("USDT", {})
            
            return {
                "status": "SUCCESS",
                "balance": float(usdt_balance.get("free", 0)),
                "total_balance": float(usdt_balance.get("total", 0)),
                "used_balance": float(usdt_balance.get("used", 0)),
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
    
    def get_open_positions(self) -> Dict[str, Any]:
        """
        Get Binance open positions (spot only).
        For spot trading, positions are just the asset balances.
        """
        if not self._ensure_client():
            return {
                "status": "ERROR",
                "positions": [],
                "count": 0,
                "message": "Binance client not initialized",
                "mode": self.mode,
                "exchange": self.exchange
            }
        
        try:
            # For spot, we track positions via open orders
            open_orders = self._client.fetch_open_orders()
            
            positions = []
            for order in open_orders:
                positions.append({
                    "symbol": order.get("symbol", "").replace("USDT", ""),
                    "side": "long" if order.get("side") == "buy" else "short",
                    "quantity": float(order.get("remaining", 0)),
                    "entry_price": float(order.get("price", 0)),
                    "status": order.get("status", "open"),
                    "order_id": order.get("id")
                })
            
            return {
                "status": "SUCCESS",
                "positions": positions,
                "count": len(positions),
                "mode": self.mode,
                "exchange": self.exchange
            }
            
        except Exception as e:
            logger.error(f"[Binance] Failed to get open positions: {e}")
            return {
                "status": "ERROR",
                "positions": [],
                "count": 0,
                "message": f"Failed to fetch open positions: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order on Binance.
        """
        if not self._ensure_client():
            return {
                "status": "ERROR",
                "order_id": order_id,
                "message": "Binance client not initialized",
                "mode": self.mode
            }
        
        try:
            response = self._client.cancel_order(order_id)
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "message": f"Order {order_id} cancelled",
                "mode": self.mode,
                "exchange": self.exchange,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"[Binance] Failed to cancel order: {e}")
            return {
                "status": "ERROR",
                "order_id": order_id,
                "message": f"Failed to cancel order: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get Binance order status.
        """
        if not self._ensure_client():
            return {
                "status": "ERROR",
                "order_id": order_id,
                "order_status": "unknown",
                "executed_price": None,
                "executed_quantity": None,
                "message": "Binance client not initialized",
                "mode": self.mode,
                "exchange": self.exchange
            }
        
        try:
            # Try to find order
            response = self._client.fetch_order(order_id)
            
            status_map = {
                "open": "open",
                "closed": "closed",
                "canceled": "canceled",
                "expired": "canceled",
                "filled": "closed"
            }
            
            order_status = status_map.get(response.get("status", ""), "unknown")
            executed_price = float(response.get("price", 0)) if order_status == "closed" else None
            executed_qty = float(response.get("filled", 0))
            
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "order_status": order_status,
                "executed_price": executed_price,
                "executed_quantity": executed_qty,
                "message": f"Order {order_id} status: {order_status}",
                "mode": self.mode,
                "exchange": self.exchange,
                "details": response
            }
            
        except Exception as e:
            logger.error(f"[Binance] Failed to get order status: {e}")
            return {
                "status": "ERROR",
                "order_id": order_id,
                "order_status": "unknown",
                "executed_price": None,
                "executed_quantity": None,
                "message": f"Failed to fetch order status: {str(e)}",
                "mode": self.mode,
                "exchange": self.exchange
            }


# ============================================================================
# ADAPTER FACTORY
# ============================================================================

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
        return PaperAdapter()
    elif mode == "live":
        # Check if Binance adapter is available
        try:
            # Check if ccxt is installed
            import ccxt
            # Use testnet by default for safety
            use_testnet = os.environ.get("BINANCE_USE_MAINNET", "false").lower() != "true"
            
            # Validate credentials if not testnet
            if not use_testnet:
                api_key = os.environ.get("BINANCE_API_KEY", "")
                secret_key = os.environ.get("BINANCE_SECRET_KEY", "")
                if not api_key or not secret_key:
                    logger.warning("Binance API credentials not set for mainnet. Falling back to testnet.")
                    use_testnet = True
            
            return BinanceAdapter(use_testnet=use_testnet)
            
        except ImportError:
            raise NotImplementedError(
                "ccxt not installed. Install with: pip install ccxt"
            )
    else:
        raise ValueError(f"Unsupported trading mode: {mode}. Use 'paper' or 'live'.")


# ============================================================================
# CONVENIENCE FUNCTIONS FOR DASHBOARD
# ============================================================================

def get_adapter_status(mode: str = "paper") -> Dict[str, Any]:
    """
    Get the status of the exchange adapter.
    
    Args:
        mode: "paper" or "live"
    
    Returns:
        Dict with adapter status information
    """
    try:
        adapter = get_adapter(mode)
        
        # Try to get balance as a health check
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