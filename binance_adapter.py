"""
TradeGuard AI - Binance Adapter.

Implements the ExchangeAdapter interface for Binance integration.
Uses ccxt library for Binance API access.

SAFETY:
- Defaults to Binance Testnet for safe demonstration
- Requires explicit TRADING_MODE=live for mainnet
- All API calls fail-closed
- No credentials in source code
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import os

from exchange_adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """
    Binance adapter - executes trades through Binance API.
    
    Supports both Testnet (default) and Mainnet (requires explicit opt-in).
    """
    
    def __init__(self, use_testnet: bool = True):
        """
        Initialize Binance adapter.
        
        Args:
            use_testnet: If True, use Binance Testnet (safe). If False, use Mainnet (real money).
        """
        self.mode = "live"
        self.use_testnet = use_testnet
        
        # Import ccxt here to avoid import errors if not installed
        try:
            import ccxt
        except ImportError:
            raise ImportError(
                "ccxt library not installed. "
                "Install with: pip install ccxt==4.4.17"
            )
        
        # Get API credentials from environment
        api_key = os.environ.get("BINANCE_API_KEY")
        api_secret = os.environ.get("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            raise ValueError(
                "Binance API credentials not found. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET in environment variables."
            )
        
        # Initialize Binance exchange
        if use_testnet:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': True,  # Enable testnet
                'enableRateLimit': True,
            })
            logger.warning("⚠️  BINANCE TESTNET MODE - No real money at risk")
        else:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': False,  # Mainnet
                'enableRateLimit': True,
            })
            logger.error("🚨 BINANCE MAINNET MODE - REAL MONEY AT RISK 🚨")
    
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade order through Binance.
        
        Args:
            trade_intent: Validated trade parameters from governance engine
        
        Returns:
            Execution result with order details
        """
        trade_id = trade_intent.get("trade_id")
        symbol = trade_intent.get("symbol")
        side = trade_intent.get("side")
        quantity = trade_intent.get("quantity")
        entry_price = trade_intent.get("entry_price")
        
        # Validate required fields
        if not all([trade_id, symbol, side, quantity, entry_price]):
            return {
                "status": "ERROR",
                "message": "Missing required fields in trade_intent",
                "mode": self.mode
            }
        
        # Convert symbol to Binance format (e.g., "BTC" -> "BTC/USDT")
        binance_symbol = f"{symbol}/USDT"
        
        # Convert side to Binance format
        binance_side = "buy" if side.lower() == "long" else "sell"
        
        try:
            # Execute market order (simplified for demo)
            order = self.exchange.create_market_order(
                symbol=binance_symbol,
                side=binance_side,
                amount=quantity
            )
            
            result = {
                "status": "SUCCESS",
                "order_id": order.get("id"),
                "execution_price": order.get("average") or order.get("price") or entry_price,
                "message": f"Binance {self.mode} order executed: {binance_side.upper()} {quantity} {binance_symbol}",
                "mode": self.mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "order_details": order
            }
            
            logger.info(f"[BINANCE {self.mode.upper()}] {result['message']} (order_id={result['order_id']})")
            
            return result
        
        except Exception as e:
            logger.error(f"[BINANCE {self.mode.upper()}] Order execution failed: {e}")
            return {
                "status": "ERROR",
                "message": f"Binance order execution failed: {str(e)}",
                "mode": self.mode,
                "error_type": type(e).__name__
            }
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get live portfolio balance from Binance.
        
        Returns:
            Balance information from authorized Binance account
        """
        try:
            balance = self.exchange.fetch_balance()
            
            # Extract USDT balance (primary trading currency)
            usdt_balance = balance.get("USDT", {}).get("free", 0.0)
            
            return {
                "status": "SUCCESS",
                "balance": float(usdt_balance),
                "currency": "USDT",
                "mode": self.mode,
                "full_balance": balance
            }
        
        except Exception as e:
            logger.error(f"[BINANCE {self.mode.upper()}] Failed to get balance: {e}")
            return {
                "status": "ERROR",
                "balance": 0.0,
                "currency": "USDT",
                "mode": self.mode,
                "message": str(e)
            }
    
    def get_open_positions(self) -> Dict[str, Any]:
        """
        Get open positions from Binance.
        
        Note: Binance spot doesn't have "positions" like futures.
        This returns current holdings (assets with non-zero balance).
        
        Returns:
            List of current holdings
        """
        try:
            balance = self.exchange.fetch_balance()
            
            # Extract non-zero balances
            positions = []
            for currency, data in balance.get("total", {}).items():
                if data > 0 and currency not in ["USDT", "USD"]:
                    positions.append({
                        "symbol": currency,
                        "quantity": data,
                        "side": "long"  # Spot holdings are always long
                    })
            
            return {
                "status": "SUCCESS",
                "positions": positions,
                "mode": self.mode
            }
        
        except Exception as e:
            logger.error(f"[BINANCE {self.mode.upper()}] Failed to get positions: {e}")
            return {
                "status": "ERROR",
                "positions": [],
                "mode": self.mode,
                "message": str(e)
            }