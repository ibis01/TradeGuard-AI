"""
TradeGuard AI - Portfolio Guardrails.
Enforces circuit breakers, exposure limits, and correlation checks.
USES THE SAME SOURCE OF TRUTH for portfolio balance as the risk engine.
"""
import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# --- IMPORT CANONICAL CONFIG AND SCHEMAS ---
from config import DB_PATH, MAX_OPEN_EXPOSURE
from schemas import TradeStatus
from risk_management_mcp import _get_real_portfolio_balance

logger = logging.getLogger(__name__)

# Constants (using DECIMAL convention: 0.02 = 2%)
MAX_DAILY_DRAWDOWN = 0.05      # 5%
CORE_ASSETS = ["BTC", "ETH", "SOL"]
# MAX_OPEN_EXPOSURE is imported from config (25%)

# In-memory cache for performance (optional)
_cache_ttl = 5  # seconds
_cache_timestamp = None
_cache_open_positions = None


def _get_open_positions(use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Fetches currently open positions from the trades ledger.
    
    Args:
        use_cache: Whether to use in-memory cache (default True)
    
    Returns:
        List of open positions
    
    Raises:
        RuntimeError: On database errors (fail-closed)
    """
    global _cache_timestamp, _cache_open_positions
    
    # Check cache if enabled
    if use_cache and _cache_timestamp is not None:
        elapsed = (datetime.now(timezone.utc) - _cache_timestamp).total_seconds()
        if elapsed < _cache_ttl:
            return _cache_open_positions
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        # FIX: Use canonical DB_PATH, correct column name (quantity), 
        # and only include truly open/approved statuses.
        cursor.execute("""
            SELECT symbol, side, entry_price, quantity, stop_loss, take_profit, id
            FROM trades 
            WHERE status IN (?, ?)
        """, (TradeStatus.APPROVED.value, TradeStatus.EXECUTED.value))
        rows = cursor.fetchall()
        conn.close()
        
        positions = [
            {
                "symbol": r[0], 
                "side": r[1], 
                "entry": r[2], 
                "size": r[3],
                "stop_loss": r[4],
                "take_profit": r[5],
                "trade_id": r[6],
                "value": r[2] * r[3]  # entry * size
            } 
            for r in rows
        ]
        
        # Update cache
        _cache_timestamp = datetime.now(timezone.utc)
        _cache_open_positions = positions
        
        return positions
        
    except sqlite3.Error as e:
        # FIX: FAIL-CLOSED. Raise exception to prevent silent exposure bypass.
        logger.error(f"Database error fetching open positions: {e}")
        raise RuntimeError(f"Cannot retrieve open positions: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching open positions: {e}")
        raise RuntimeError(f"Cannot retrieve open positions: {e}")


def _get_todays_pnl() -> float:
    """
    Get today's realized PnL from closed trades.
    
    Returns:
        Total realized PnL for today
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        # Get today's date in UTC
        today = datetime.now(timezone.utc).date().isoformat()
        
        cursor.execute("""
            SELECT COALESCE(SUM(pnl), 0) 
            FROM trades 
            WHERE status = ? AND date(closed_at) = ?
        """, (TradeStatus.CLOSED.value, today))
        result = cursor.fetchone()
        conn.close()
        
        return float(result[0]) if result else 0.0
        
    except sqlite3.Error as e:
        logger.error(f"Database error getting today's PnL: {e}")
        return 0.0


def check_circuit_breaker(portfolio_balance: Optional[float] = None) -> Dict[str, Any]:
    """
    Checks if the daily drawdown exceeds 5%.
    Uses the REAL portfolio balance.
    
    Args:
        portfolio_balance: Optional override for portfolio balance (for testing)
    
    Returns:
        Dict with status and details
    """
    try:
        balance = portfolio_balance if portfolio_balance is not None else _get_real_portfolio_balance()
        
        if balance <= 0:
            return {
                "status": "ERROR",
                "reason": "Invalid portfolio balance",
                "portfolio_balance": balance
            }
        
        daily_pnl = _get_todays_pnl()
        daily_loss_pct = abs(daily_pnl) / balance if balance > 0 else 0
        
        if daily_loss_pct >= MAX_DAILY_DRAWDOWN:
            return {
                "status": "TRIPPED",
                "reason": f"Daily drawdown of {daily_loss_pct*100:.2f}% exceeds {MAX_DAILY_DRAWDOWN*100}% limit.",
                "daily_pnl": daily_pnl,
                "daily_loss_pct": daily_loss_pct,
                "portfolio_balance": balance
            }
        return {
            "status": "ARMED",
            "reason": f"Daily drawdown {daily_loss_pct*100:.2f}% is within limit.",
            "daily_pnl": daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "portfolio_balance": balance
        }
    except Exception as e:
        logger.error(f"Circuit breaker check failed: {e}")
        return {"status": "ERROR", "reason": f"Cannot check circuit breaker: {e}"}


def check_exposure_limit(
    proposed_size: float, 
    proposed_entry: float,
    portfolio_balance: Optional[float] = None
) -> Dict[str, Any]:
    """
    Ensures total open exposure does not exceed 20% of portfolio.
    Uses REAL portfolio balance.
    
    Args:
        proposed_size: Size/quantity of proposed trade
        proposed_entry: Entry price of proposed trade
        portfolio_balance: Optional override for portfolio balance (for testing)
    
    Returns:
        Dict with status and details
    """
    try:
        balance = portfolio_balance if portfolio_balance is not None else _get_real_portfolio_balance()
        
        if balance <= 0:
            return {
                "status": "REJECTED",
                "reason": "Invalid portfolio balance",
                "portfolio_balance": balance
            }
        
        open_positions = _get_open_positions()  # May raise RuntimeError (fail-closed)
        
        current_exposure = sum([p["value"] for p in open_positions])
        proposed_exposure = proposed_size * proposed_entry
        total_exposure = current_exposure + proposed_exposure
        
        exposure_pct = total_exposure / balance if balance > 0 else 0
        
        if exposure_pct > MAX_OPEN_EXPOSURE:
            return {
                "status": "REJECTED",
                "reason": f"Total exposure {exposure_pct*100:.2f}% exceeds {MAX_OPEN_EXPOSURE*100}% cap.",
                "current_exposure_usd": round(current_exposure, 2),
                "proposed_exposure_usd": round(proposed_exposure, 2),
                "total_exposure_usd": round(total_exposure, 2),
                "exposure_pct": exposure_pct,
                "portfolio_balance": balance,
                "open_positions_count": len(open_positions)
            }
        return {
            "status": "PASSED",
            "reason": f"Total exposure {exposure_pct*100:.2f}% is within cap.",
            "current_exposure_usd": round(current_exposure, 2),
            "total_exposure_usd": round(total_exposure, 2),
            "exposure_pct": exposure_pct,
            "portfolio_balance": balance,
            "open_positions_count": len(open_positions)
        }
    except RuntimeError as e:
        # FIX: FAIL-CLOSED on database errors
        logger.error(f"Exposure check failed (fail-closed): {e}")
        return {
            "status": "REJECTED", 
            "reason": f"Exposure check failed: {e}",
            "is_fail_closed": True
        }
    except Exception as e:
        logger.error(f"Exposure check failed: {e}")
        return {
            "status": "REJECTED", 
            "reason": f"Cannot check exposure: {e}",
            "is_fail_closed": True
        }


def check_correlation_risk(
    proposed_symbol: str,
    proposed_side: Optional[str] = None
) -> Dict[str, Any]:
    """
    Warns if trying to open a correlated position (e.g., BTC and ETH).
    
    Args:
        proposed_symbol: Symbol of proposed trade
        proposed_side: Optional side of proposed trade (for directional correlation)
    
    Returns:
        Dict with status and details
    """
    if proposed_symbol not in CORE_ASSETS:
        return {
            "status": "PASSED", 
            "reason": "Asset not in core correlation set.",
            "asset": proposed_symbol
        }
    
    try:
        open_positions = _get_open_positions()  # May raise RuntimeError
        open_symbols = [p["symbol"] for p in open_positions]
        
        # Check for correlated assets
        correlated_open = []
        for asset in CORE_ASSETS:
            if asset != proposed_symbol and asset in open_symbols:
                correlated_open.append(asset)
        
        if correlated_open:
            # Check if opposite sides (for potential hedge)
            if proposed_side:
                opposite_side_count = 0
                same_side_count = 0
                for pos in open_positions:
                    if pos["symbol"] in correlated_open:
                        if pos["side"] != proposed_side:
                            opposite_side_count += 1
                        else:
                            same_side_count += 1
                
                # If all correlated positions are opposite side, it might be a hedge
                if opposite_side_count > 0 and same_side_count == 0:
                    return {
                        "status": "WARNING",
                        "reason": f"Correlated assets {correlated_open} are open on opposite sides. Possible hedge.",
                        "correlated_assets": correlated_open,
                        "is_hedge": True
                    }
            
            return {
                "status": "WARNING",
                "reason": f"Correlated asset(s) {correlated_open} already open. Adding {proposed_symbol} increases correlated risk.",
                "correlated_assets": correlated_open,
                "is_hedge": False
            }
        
        return {
            "status": "PASSED", 
            "reason": "No correlation conflicts detected.",
            "correlated_assets": []
        }
        
    except RuntimeError as e:
        # FIX: FAIL-CLOSED on database errors
        logger.error(f"Correlation check failed (fail-closed): {e}")
        return {
            "status": "REJECTED", 
            "reason": f"Correlation check failed: {e}",
            "is_fail_closed": True
        }
    except Exception as e:
        logger.error(f"Correlation check failed: {e}")
        return {
            "status": "REJECTED", 
            "reason": f"Cannot check correlation: {e}",
            "is_fail_closed": True
        }


def check_position_size_limit(
    proposed_size: float,
    proposed_entry: float,
    portfolio_balance: Optional[float] = None
) -> Dict[str, Any]:
    """
    Checks if the proposed position size is reasonable.
    
    Args:
        proposed_size: Size/quantity of proposed trade
        proposed_entry: Entry price of proposed trade
        portfolio_balance: Optional override for portfolio balance (for testing)
    
    Returns:
        Dict with status and details
    """
    try:
        balance = portfolio_balance if portfolio_balance is not None else _get_real_portfolio_balance()
        
        if balance <= 0:
            return {
                "status": "REJECTED",
                "reason": "Invalid portfolio balance",
                "portfolio_balance": balance
            }
        
        position_value = proposed_size * proposed_entry
        position_pct = position_value / balance if balance > 0 else 0
        
        # Max single position size: 10% of portfolio
        MAX_SINGLE_POSITION = 0.10
        
        if position_pct > MAX_SINGLE_POSITION:
            return {
                "status": "REJECTED",
                "reason": f"Position size {position_pct*100:.2f}% exceeds {MAX_SINGLE_POSITION*100}% limit.",
                "position_value": round(position_value, 2),
                "position_pct": position_pct,
                "portfolio_balance": balance
            }
        
        return {
            "status": "PASSED",
            "reason": f"Position size {position_pct*100:.2f}% is within limit.",
            "position_value": round(position_value, 2),
            "position_pct": position_pct,
            "portfolio_balance": balance
        }
        
    except Exception as e:
        logger.error(f"Position size check failed: {e}")
        return {
            "status": "REJECTED",
            "reason": f"Cannot check position size: {e}"
        }


def get_portfolio_summary() -> Dict[str, Any]:
    """
    Get a comprehensive portfolio summary.
    
    Returns:
        Dict with portfolio statistics
    """
    try:
        balance = _get_real_portfolio_balance()
        open_positions = _get_open_positions()
        
        total_exposure = sum([p["value"] for p in open_positions])
        exposure_pct = total_exposure / balance if balance > 0 else 0
        
        daily_pnl = _get_todays_pnl()
        daily_loss_pct = abs(daily_pnl) / balance if balance > 0 else 0
        
        # Count positions by symbol
        symbol_counts = {}
        for pos in open_positions:
            symbol = pos["symbol"]
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        return {
            "portfolio_balance": balance,
            "total_exposure": round(total_exposure, 2),
            "exposure_pct": exposure_pct,
            "open_positions_count": len(open_positions),
            "daily_pnl": daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "symbol_counts": symbol_counts,
            "circuit_breaker_status": check_circuit_breaker(balance).get("status"),
            "is_within_exposure_limit": exposure_pct <= MAX_OPEN_EXPOSURE,
            "is_within_drawdown_limit": daily_loss_pct <= MAX_DAILY_DRAWDOWN
        }
        
    except Exception as e:
        logger.error(f"Portfolio summary failed: {e}")
        return {
            "status": "ERROR",
            "reason": f"Cannot get portfolio summary: {e}"
        }


def reset_cache():
    """
    Reset the cache for open positions.
    Useful for testing or after database changes.
    """
    global _cache_timestamp, _cache_open_positions
    _cache_timestamp = None
    _cache_open_positions = None
    logger.info("Portfolio guardrails cache reset")


# ============================================================================
# DASHBOARD COMPATIBILITY WRAPPERS
# ============================================================================

def check_guardrails(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float
) -> Dict[str, Any]:
    """
    Comprehensive guardrail check for dashboard.
    Returns a unified result with all check results.
    
    Args:
        symbol: Asset symbol
        side: "long" or "short"
        quantity: Trade quantity
        entry_price: Entry price
    
    Returns:
        Dict with all guardrail results
    """
    results = {
        "status": "PASSED",
        "checks": {},
        "violations": []
    }
    
    # Check circuit breaker
    cb_result = check_circuit_breaker()
    results["checks"]["circuit_breaker"] = cb_result
    if cb_result.get("status") == "TRIPPED":
        results["violations"].append(f"Circuit breaker: {cb_result.get('reason')}")
    
    # Check exposure limit
    exposure_result = check_exposure_limit(quantity, entry_price)
    results["checks"]["exposure_limit"] = exposure_result
    if exposure_result.get("status") == "REJECTED":
        results["violations"].append(f"Exposure limit: {exposure_result.get('reason')}")
    
    # Check correlation risk
    correlation_result = check_correlation_risk(symbol, side)
    results["checks"]["correlation_risk"] = correlation_result
    if correlation_result.get("status") == "WARNING":
        results["violations"].append(f"Correlation warning: {correlation_result.get('reason')}")
    
    # Check position size
    size_result = check_position_size_limit(quantity, entry_price)
    results["checks"]["position_size"] = size_result
    if size_result.get("status") == "REJECTED":
        results["violations"].append(f"Position size: {size_result.get('reason')}")
    
    # Determine overall status
    if results["violations"]:
        results["status"] = "REJECTED" if any(
            c.get("status") in ["REJECTED", "TRIPPED"] 
            for c in results["checks"].values()
        ) else "WARNING"
    
    return results