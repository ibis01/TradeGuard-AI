"""
TradeGuard AI - Binance Adapter.

Implements the ExchangeAdapter interface for Binance integration.
Uses ccxt library for Binance API access.

Constitution §5: Binance Integration Boundary
Constitution §6: LIVE MODE → balance obtained from authorized Binance account
Constitution §10: Never add secrets to source code
"""

from typing import Dict, Any
from datetime import datetime, timezone
import logging
import os

from .adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """
    Binance adapter - executes trades through Binance API.
    
    Supports both Testnet (recommended for demo) and Mainnet.
    Defaults to Testnet for safety.
    """
    
    def __init__(self, use_testnet: bool = None):
        """
        Initialize Binance adapter.
        
        Args:
            use_testnet: If True, use Binance Testnet (safe). 
                        If False, use Mainnet (real money).
                        Defaults to True for safety.
        """
        self.mode = "live"
        
        # Default to testnet for safety (§6, §10)
        if use_testnet is None:
            use_testnet = os.environ.get("BINANCE_USE_TESTNET", "true").lower() == "true"
        
        self.use_testnet = use_testnet
        
        # Import ccxt here to avoid import errors if not installed
        try:
            import ccxt
            self.ccxt = ccxt
        except ImportError:
            raise ImportError(
                "ccxt library not installed. "
                "Install with: pip install ccxt==4.4.17"
            )
        
        # Get API credentials from environment (never from code)
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
            # Execute market order
            order = self.exchange.create_market_order(
                symbol=binance_symbol,
                side=binance_side,
                amount=quantity
            )
            
            result = {
                "status": "SUCCESS",
                "order_id": order.get("id"),
                "execution_price": order.get("average") or order.get("price") or entry_price,
                "message": f"[BINANCE {'TESTNET' if self.use_testnet else 'MAINNET'}] {binance_side.upper()} {quantity} {binance_symbol}",
                "mode": self.mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "order_details": order
            }
            
            logger.info(f"{result['message']} (order_id={result['order_id']})")
            
            return result
        
        except Exception as e:
            logger.error(f"[BINANCE] Order execution failed: {e}")
            return {
                "status": "ERROR",
                "message": f"Binance order execution failed: {str(e)}",
                "mode": self.mode,
                "error_type": type(e).__name__
            }
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get live portfolio balance from Binance.
        
        Constitution §6: LIVE MODE → balance obtained from authorized Binance account
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
                "note": "LIVE BINANCE BALANCE"
            }
        
        except Exception as e:
            logger.error(f"[BINANCE] Failed to get balance: {e}")
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
            logger.error(f"[BINANCE] Failed to get positions: {e}")
            return {
                "status": "ERROR",
                "positions": [],
                "mode": self.mode,
                "message": str(e)
            }