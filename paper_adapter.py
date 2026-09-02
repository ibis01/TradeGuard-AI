"""
TradeGuard AI - Paper Trading Adapter.

Default adapter implementation for paper trading (dry-run mode).
Simulates order execution without actual exchange interaction.

SAFETY: This is the DEFAULT mode. No real money is at risk.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from exchange_adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class PaperAdapter(ExchangeAdapter):
    """
    Paper trading adapter - simulates execution without real orders.
    
    This is the DEFAULT adapter. All trades are logged but not executed.
    Used for testing, development, and demonstration.
    """
    
    def __init__(self):
        self.mode = "paper"
        logger.info(f"PaperAdapter initialized (mode={self.mode})")
    
    def execute_order(self, trade_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate order execution (dry-run).
        
        Args:
            trade_intent: Validated trade parameters
        
        Returns:
            Simulated execution result
        """
        trade_id = trade_intent.get("trade_id")
        symbol = trade_intent.get("symbol")
        side = trade_intent.get("side")
        quantity = trade_intent.get("quantity")
        entry_price = trade_intent.get("entry_price")
        
        # Simulate execution at requested price
        execution_price = entry_price
        
        # Generate simulated order ID
        order_id = f"PAPER-{trade_id}-{int(datetime.now(timezone.utc).timestamp())}"
        
        result = {
            "status": "SUCCESS",
            "order_id": order_id,
            "execution_price": execution_price,
            "message": f"Paper trade executed: {side.upper()} {quantity} {symbol} @ ${execution_price:.2f}",
            "mode": self.mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"[PAPER] {result['message']} (order_id={order_id})")
        
        return result
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get simulated portfolio balance.
        
        Returns paper balance from database (treasury table).
        """
        try:
            from risk_management_mcp import _get_real_portfolio_balance
            
            balance = _get_real_portfolio_balance()
            
            return {
                "status": "SUCCESS",
                "balance": balance,
                "currency": "USD",
                "mode": self.mode
            }
        except Exception as e:
            logger.error(f"[PAPER] Failed to get balance: {e}")
            return {
                "status": "ERROR",
                "balance": 0.0,
                "currency": "USD",
                "mode": self.mode,
                "message": str(e)
            }
    
    def get_open_positions(self) -> Dict[str, Any]:
        """
        Get simulated open positions.
        
        Returns positions from database (trades table).
        """
        try:
            from guardrails_mcp import _get_open_positions
            
            positions = _get_open_positions()
            
            return {
                "status": "SUCCESS",
                "positions": positions,
                "mode": self.mode
            }
        except Exception as e:
            logger.error(f"[PAPER] Failed to get positions: {e}")
            return {
                "status": "ERROR",
                "positions": [],
                "mode": self.mode,
                "message": str(e)
            }