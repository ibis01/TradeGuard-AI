# compatibility.py
"""
TradeGuard AI - Dashboard Compatibility Layer
Bridges the Streamlit dashboard with the core governance engine.
"""

import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

# Import core modules
from config import DB_PATH, TRADING_MODE
from trade_memory_mcp import propose_trade as core_propose_trade, get_trade as core_get_trade, get_trade_history as core_get_trade_history
from governance_engine import (
    screen_trade as core_screen_trade,
    request_approval as core_request_approval,
    approve_trade as core_approve_trade,
    dashboard_approve_trade,
    dashboard_reject_trade,
    execute_trade_with_adapter as core_execute_trade
)
from market_intelligence_mcp import analyze_technicals as core_analyze_technicals
from schemas import TradeStatus

# ============================================================================
# COMPATIBILITY WRAPPERS - Match Dashboard Expectations
# ============================================================================

def propose_trade(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss: float,
    reasoning: str = "",
    take_profit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Dashboard-compatible propose_trade wrapper.
    Returns: {"trade_id": int, "status": str}
    """
    result = core_propose_trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reasoning=reasoning
    )
    
    # Convert to dashboard expected format
    if result.get("status") == "success":
        return {
            "trade_id": result.get("trade_id"),
            "status": "success"
        }
    else:
        return {
            "trade_id": None,
            "status": "error",
            "message": result.get("message", "Unknown error")
        }


def get_trade(trade_id: int) -> Dict[str, Any]:
    """
    Dashboard-compatible get_trade wrapper.
    Returns a dict with all fields the dashboard expects.
    """
    trade = core_get_trade(trade_id)
    if not trade:
        return {"status": "not_found"}
    
    # Convert database column names to dashboard expected names
    return {
        "id": trade.get("id"),
        "symbol": trade.get("symbol", ""),
        "side": trade.get("side", ""),
        "quantity": trade.get("quantity", 0.0),
        "entry_price": trade.get("entry_price", 0.0),
        "stop_loss": trade.get("stop_loss", 0.0),
        "reasoning": trade.get("reasoning", ""),
        "status": trade.get("status", "proposed"),
        "risk_percent": trade.get("risk_percent", 0.0),
        "risk_amount": trade.get("risk_amount", 0.0),
        "created": trade.get("created_at", ""),
        "executed": trade.get("executed_at", ""),
        "pnl": trade.get("pnl", 0.0),
        # Aliases for dashboard
        "entry": trade.get("entry_price", 0.0),
        "stop": trade.get("stop_loss", 0.0),
    }


def get_trade_history(limit: int = 10) -> Dict[str, Any]:
    """
    Dashboard-compatible get_trade_history wrapper.
    """
    result = core_get_trade_history(limit)
    
    # Convert to dashboard expected format
    trades = []
    for trade in result.get("trades", []):
        trades.append({
            "id": trade.get("id"),
            "symbol": trade.get("symbol", ""),
            "side": trade.get("side", ""),
            "quantity": trade.get("quantity", 0.0),
            "entry": trade.get("entry", 0.0),
            "stop": trade.get("stop", 0.0),
            "status": trade.get("status", ""),
            "pnl": trade.get("pnl", 0.0),
            "created": trade.get("created", ""),
            "executed": trade.get("executed", ""),
        })
    
    return {"trades": trades}


def screen_trade(trade_id: int) -> Dict[str, Any]:
    """
    Dashboard-compatible screen_trade wrapper.
    """
    result = core_screen_trade(trade_id)
    
    # Dashboard expects "SUCCESS" or "FAILURE" in status
    if result.get("status") == "SUCCESS":
        return {"status": "SUCCESS", "message": "Risk validation passed"}
    elif result.get("status") == "REJECTED":
        return {"status": "FAILURE", "reason": result.get("reason", "Risk check failed")}
    else:
        return {"status": "FAILURE", "reason": result.get("reason", "Unknown error")}


def request_approval(trade_id: int, requested_by: str = "ai") -> Dict[str, Any]:
    """
    Dashboard-compatible request_approval wrapper.
    """
    result = core_request_approval(trade_id, requested_by)
    
    # Convert to dashboard format
    if result.get("status") == "success":
        return {
            "status": "success",
            "trade_id": trade_id,
            "approval_token": result.get("approval_token", ""),
            "expires_at": result.get("expires_at", ""),
            "proposal_hash": result.get("proposal_hash", ""),
            "policy_version": result.get("policy_version", ""),
        }
    else:
        return {
            "status": "error",
            "reason": result.get("reason", "Token generation failed")
        }


def approve_trade(approval_token: str) -> Dict[str, Any]:
    """
    Dashboard-compatible approve_trade wrapper.
    """
    result = core_approve_trade(approval_token)
    
    # Dashboard expects "SUCCESS" in status
    if result.get("status") == "SUCCESS":
        return {
            "status": "SUCCESS",
            "trade_id": result.get("trade_id"),
            "new_status": result.get("new_status", "approved")
        }
    else:
        return {
            "status": "FAILURE",
            "reason": result.get("reason", "Approval failed")
        }


def execute_trade(trade_id: int, execution_price: float) -> Dict[str, Any]:
    """
    Dashboard-compatible execute_trade wrapper.
    Uses the adapter for actual execution.
    """
    try:
        result = core_execute_trade(trade_id, execution_price)
        
        if result.get("status") == "SUCCESS":
            return {
                "status": "SUCCESS",
                "trade_id": trade_id,
                "new_status": result.get("new_status", "executed"),
                "execution_details": result.get("execution", {})
            }
        else:
            return {
                "status": "FAILURE",
                "reason": result.get("reason", "Execution failed")
            }
    except Exception as e:
        return {
            "status": "FAILURE",
            "reason": str(e)
        }


# Export all functions with dashboard-compatible signatures
__all__ = [
    'propose_trade',
    'get_trade',
    'get_trade_history',
    'screen_trade',
    'request_approval',
    'approve_trade',
    'execute_trade',
    'TRADING_MODE',
    'DB_PATH'
]