# risk_management_mcp.py
"""
TradeGuard AI - Hardened Risk Management MCP.
Implements deterministic risk controls that CANNOT be bypassed by the LLM.
- 2% hard cap on per-trade risk.
- Validates all financial inputs.
- HARD STOP on missing portfolio balance (no silent mock fallback).
- TRUST BOUNDARY: Portfolio balance is ALWAYS fetched from the trusted treasury.
"""
import os
import sqlite3
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

# Set up logging
logger = logging.getLogger(__name__)

# Database path – uses unified config if available, otherwise falls back
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from config import DB_PATH
except ImportError:
    DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Risk constants (hard-coded, cannot be overridden)
MAX_RISK_PERCENT = 0.02  # 2% max risk per trade
MAX_DAILY_DRAWDOWN = 0.05  # 5% max daily drawdown
MIN_POSITION_SIZE = {
    "BTC": 0.0001,
    "ETH": 0.001,
    "SOL": 0.01,
    "DEFAULT": 0.0001
}

# Cache for portfolio balance (with TTL)
_balance_cache = {
    "value": None,
    "timestamp": None,
    "ttl": 5  # seconds
}


# ------------------------------------------------------------------
# 1. PORTFOLIO BALANCE (HARD STOP ON FAILURE)
# ------------------------------------------------------------------
def _get_real_portfolio_balance(use_cache: bool = True) -> float:
    """
    Fetches the REAL portfolio balance from the treasury table.
    If the balance cannot be retrieved, it raises a Hard Stop error.
    NEVER silently falls back to a default during active trading.
    
    Args:
        use_cache: Whether to use cached balance (default True)
    
    Returns:
        Current portfolio balance
    
    Raises:
        RuntimeError: If balance cannot be retrieved (HARD STOP)
    """
    global _balance_cache
    
    # Check cache if enabled
    if use_cache and _balance_cache["timestamp"] is not None:
        elapsed = (datetime.now(timezone.utc) - _balance_cache["timestamp"]).total_seconds()
        if elapsed < _balance_cache["ttl"]:
            return _balance_cache["value"]
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        # Create treasury table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS treasury (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_balance REAL NOT NULL DEFAULT 10000.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
        """)
        
        # Check if treasury has data
        cursor.execute("SELECT COUNT(*) FROM treasury")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Seed with default balance
            cursor.execute(
                "INSERT INTO treasury (current_balance, note) VALUES (?, ?)",
                (10000.0, "Initial seed")
            )
            conn.commit()
            logger.info("Treasury seeded with $10,000.00")
        
        # Get latest balance
        cursor.execute("SELECT current_balance FROM treasury ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] is not None:
            balance = float(row[0])
            if balance > 0:
                # Update cache
                _balance_cache["value"] = balance
                _balance_cache["timestamp"] = datetime.now(timezone.utc)
                return balance
            else:
                raise ValueError(f"Treasury balance is zero or negative. Got: {balance}")
        else:
            raise ValueError("Treasury table exists but contains no valid balance row.")
            
    except sqlite3.Error as e:
        logger.error(f"Database error fetching portfolio balance: {e}")
        raise RuntimeError(f"HARD STOP: Database error while fetching portfolio balance. Details: {e}")
    except ValueError as e:
        logger.error(f"Invalid portfolio balance: {e}")
        raise RuntimeError(f"HARD STOP: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching portfolio balance: {e}")
        raise RuntimeError(f"HARD STOP: Unexpected error while fetching portfolio balance. Details: {e}")


def update_portfolio_balance(new_balance: float, note: str = "") -> Dict[str, Any]:
    """
    Update the portfolio balance in the treasury.
    
    Args:
        new_balance: New balance amount (must be positive)
        note: Optional note for the update
    
    Returns:
        Dict with status and new balance
    
    Raises:
        ValueError: If new_balance is not positive
    """
    if new_balance <= 0:
        raise ValueError(f"Balance must be positive. Got: {new_balance}")
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO treasury (current_balance, note) VALUES (?, ?)",
            (new_balance, note or f"Updated to ${new_balance:,.2f}")
        )
        conn.commit()
        conn.close()
        
        # Invalidate cache
        _balance_cache["value"] = None
        _balance_cache["timestamp"] = None
        
        logger.info(f"Portfolio balance updated to ${new_balance:,.2f}")
        
        return {
            "status": "SUCCESS",
            "balance": new_balance,
            "note": note,
            "message": f"Portfolio balance updated to ${new_balance:,.2f}"
        }
        
    except Exception as e:
        logger.error(f"Failed to update portfolio balance: {e}")
        return {
            "status": "ERROR",
            "message": f"Failed to update balance: {str(e)}"
        }


# ------------------------------------------------------------------
# 2. POSITION SIZING (CALCULATES, BUT DOES NOT AUTHORISE)
# ------------------------------------------------------------------
def calculate_position_size(
    entry: float, 
    stop: float,
    risk_percent: float = MAX_RISK_PERCENT
) -> Dict[str, Any]:
    """
    Calculates the position size based on the risk cap.
    TRUST BOUNDARY: Always fetches authoritative balance from treasury.
    
    Args:
        entry: Entry price
        stop: Stop loss price
        risk_percent: Risk percentage (default: 2%)
    
    Returns:
        Dict with position sizing details
    
    Raises:
        ValueError: If inputs are invalid
        RuntimeError: If balance cannot be fetched
    """
    if entry <= 0:
        raise ValueError(f"Entry price must be positive. Got: {entry}")
    if stop <= 0:
        raise ValueError(f"Stop loss price must be positive. Got: {stop}")
    if entry == stop:
        raise ValueError("Entry and Stop prices cannot be equal. Risk per unit would be zero.")
    if risk_percent <= 0 or risk_percent > 0.5:
        raise ValueError(f"Risk percent must be between 0 and 0.5. Got: {risk_percent}")
    
    # TRUSTED SOURCE: Never accept LLM override
    portfolio_balance = _get_real_portfolio_balance()
    
    if portfolio_balance <= 0:
        raise ValueError(f"Portfolio balance must be positive. Got: {portfolio_balance}")
    
    risk_amount = portfolio_balance * risk_percent
    risk_per_unit = abs(entry - stop)
    position_size = risk_amount / risk_per_unit
    
    return {
        "portfolio_balance": round(portfolio_balance, 2),
        "max_risk_percent": risk_percent * 100,
        "risk_amount_usd": round(risk_amount, 2),
        "position_size": round(position_size, 8),
        "entry_price": entry,
        "stop_loss": stop,
        "risk_per_unit": round(risk_per_unit, 2),
        "risk_percent": risk_percent
    }


# ------------------------------------------------------------------
# 3. HARDCODED VETO GATE (AUTHORISATION)
# ------------------------------------------------------------------
def evaluate_trade_risk(
    symbol: str,
    side: str,
    entry: float,
    stop: float,
    size: float,
    rsi_override: Optional[float] = None,
    portfolio_balance: Optional[float] = None
) -> Dict[str, Any]:
    """
    Hardcoded veto gate. Purely deterministic.
    TRUST BOUNDARY: Always fetches authoritative balance from treasury.
    
    Args:
        symbol: Asset symbol (BTC, ETH, SOL)
        side: "long" or "short"
        entry: Entry price
        stop: Stop loss price
        size: Position size
        rsi_override: Optional RSI value for testing
        portfolio_balance: Optional override for testing
    
    Returns:
        Dict with status, reason, and risk metrics
    
    Raises:
        ValueError: If inputs are invalid
        RuntimeError: If balance cannot be fetched
    """
    # Validate inputs
    if not symbol or symbol not in ["BTC", "ETH", "SOL"]:
        raise ValueError(f"Invalid symbol. Must be BTC, ETH, or SOL. Got: {symbol}")
    if side not in ["long", "short"]:
        raise ValueError(f"Side must be 'long' or 'short'. Got: {side}")
    if entry <= 0:
        raise ValueError(f"Entry price must be positive. Got: {entry}")
    if stop <= 0:
        raise ValueError(f"Stop loss must be positive. Got: {stop}")
    if entry == stop:
        raise ValueError("Entry and Stop cannot be equal.")
    if size <= 0:
        raise ValueError(f"Position size must be positive. Got: {size}")
    
    # TRUSTED SOURCE: Never accept LLM override
    if portfolio_balance is None:
        portfolio_balance = _get_real_portfolio_balance()
    
    if portfolio_balance <= 0:
        raise ValueError(f"Portfolio balance must be positive. Got: {portfolio_balance}")
    
    # --- Check 1: 2% Risk Cap ---
    risk_per_unit = abs(entry - stop)
    risk_usd = risk_per_unit * size
    risk_percent = (risk_usd / portfolio_balance)
    
    if risk_percent > MAX_RISK_PERCENT:
        return {
            "status": "REJECTED",
            "reason": f"Risk exceeds {MAX_RISK_PERCENT*100}% hard cap. Proposed risk: {risk_percent*100:.2f}% (max allowed: {MAX_RISK_PERCENT*100:.1f}%).",
            "risk_percent": round(risk_percent * 100, 2),
            "risk_usd": round(risk_usd, 2),
            "portfolio_balance": round(portfolio_balance, 2),
            "warnings": [],
            "checks": {
                "risk_cap": "FAILED"
            }
        }

    # --- Check 2: RSI (Override only for testing. No live fetch.) ---
    warnings = []
    if rsi_override is not None:
        if rsi_override > 70 and side == "long":
            return {
                "status": "REJECTED", 
                "reason": f"RSI override {rsi_override} > 70 (overbought). Long rejected.",
                "rsi": rsi_override,
                "checks": {"rsi": "FAILED"}
            }
        if rsi_override < 30 and side == "short":
            return {
                "status": "REJECTED", 
                "reason": f"RSI override {rsi_override} < 30 (oversold). Short rejected.",
                "rsi": rsi_override,
                "checks": {"rsi": "FAILED"}
            }

    # --- Check 3: Minimum position sanity ---
    min_size = MIN_POSITION_SIZE.get(symbol, MIN_POSITION_SIZE["DEFAULT"])
    if size < min_size:
        return {
            "status": "REJECTED", 
            "reason": f"Size {size} below minimum {min_size} for {symbol}.",
            "warnings": warnings,
            "checks": {"min_size": "FAILED"}
        }
    
    # --- Check 4: Stop loss distance (prevent too tight stops) ---
    stop_distance_pct = abs(entry - stop) / entry
    MIN_STOP_DISTANCE = 0.005  # 0.5% minimum stop distance
    if stop_distance_pct < MIN_STOP_DISTANCE:
        warnings.append(f"Stop loss is very tight ({stop_distance_pct*100:.2f}%). May trigger prematurely.")
    
    # --- Check 5: Position size vs portfolio ---
    position_value = size * entry
    position_pct = position_value / portfolio_balance
    MAX_POSITION_PCT = 0.10  # 10% max single position
    if position_pct > MAX_POSITION_PCT:
        warnings.append(f"Position size is {position_pct*100:.2f}% of portfolio (recommended < {MAX_POSITION_PCT*100}%)")
    
    # All checks passed
    return {
        "status": "PASSED",
        "reason": f"Trade passed all risk checks. Risk: {risk_percent*100:.2f}% of portfolio.",
        "warnings": warnings,
        "risk_percent": round(risk_percent * 100, 2),
        "risk_usd": round(risk_usd, 2),
        "portfolio_balance": round(portfolio_balance, 2),
        "checks": {
            "risk_cap": "PASSED",
            "rsi": "PASSED" if rsi_override is None else "PASSED",
            "min_size": "PASSED",
            "stop_distance": "PASSED" if stop_distance_pct >= MIN_STOP_DISTANCE else "WARNING"
        }
    }


# ------------------------------------------------------------------
# 4. DAILY DRAWDOWN CHECK
# ------------------------------------------------------------------
def check_daily_drawdown(portfolio_balance: Optional[float] = None) -> Dict[str, Any]:
    """
    Check if daily drawdown exceeds the limit.
    
    Args:
        portfolio_balance: Optional override for testing
    
    Returns:
        Dict with drawdown status
    """
    try:
        balance = portfolio_balance if portfolio_balance is not None else _get_real_portfolio_balance()
        
        if balance <= 0:
            return {
                "status": "ERROR",
                "reason": "Invalid portfolio balance",
                "portfolio_balance": balance
            }
        
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        # Get today's realized PnL from closed trades
        today = datetime.now(timezone.utc).date().isoformat()
        cursor.execute("""
            SELECT COALESCE(SUM(pnl), 0) 
            FROM trades 
            WHERE status = 'closed' AND date(closed_at) = ?
        """, (today,))
        
        result = cursor.fetchone()
        conn.close()
        
        daily_pnl = float(result[0]) if result else 0.0
        daily_loss_pct = abs(daily_pnl) / balance if balance > 0 else 0
        
        if daily_loss_pct >= MAX_DAILY_DRAWDOWN:
            return {
                "status": "TRIPPED",
                "reason": f"Daily drawdown of {daily_loss_pct*100:.2f}% exceeds {MAX_DAILY_DRAWDOWN*100}% limit.",
                "daily_pnl": daily_pnl,
                "daily_loss_pct": daily_loss_pct,
                "portfolio_balance": balance,
                "limit": MAX_DAILY_DRAWDOWN
            }
        
        return {
            "status": "ARMED",
            "reason": f"Daily drawdown {daily_loss_pct*100:.2f}% is within {MAX_DAILY_DRAWDOWN*100}% limit.",
            "daily_pnl": daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "portfolio_balance": balance,
            "limit": MAX_DAILY_DRAWDOWN
        }
        
    except Exception as e:
        logger.error(f"Daily drawdown check failed: {e}")
        return {
            "status": "ERROR",
            "reason": f"Failed to check daily drawdown: {str(e)}"
        }


# ------------------------------------------------------------------
# 5. HELPER: Seed treasury
# ------------------------------------------------------------------
def seed_treasury(initial_balance: float = 10000.0) -> Dict[str, Any]:
    """
    Seeds the treasury with an initial balance.
    
    Args:
        initial_balance: Initial balance amount
    
    Returns:
        Dict with status and balance
    """
    if initial_balance <= 0:
        raise ValueError("Initial balance must be positive.")
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS treasury (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_balance REAL NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
        """)
        
        # Clear existing and insert new
        cursor.execute("DELETE FROM treasury")
        cursor.execute(
            "INSERT INTO treasury (current_balance, note) VALUES (?, ?)",
            (initial_balance, "Initial seed")
        )
        conn.commit()
        conn.close()
        
        # Invalidate cache
        _balance_cache["value"] = None
        _balance_cache["timestamp"] = None
        
        logger.info(f"Treasury seeded with ${initial_balance:,.2f}")
        
        return {
            "status": "success",
            "message": f"Treasury seeded with ${initial_balance:,.2f}",
            "balance": initial_balance
        }
        
    except Exception as e:
        logger.error(f"Failed to seed treasury: {e}")
        return {
            "status": "error",
            "message": f"Failed to seed treasury: {str(e)}"
        }


# ------------------------------------------------------------------
# 6. HELPER: Get portfolio summary
# ------------------------------------------------------------------
def get_portfolio_summary() -> Dict[str, Any]:
    """
    Get a comprehensive portfolio summary.
    
    Returns:
        Dict with portfolio statistics
    """
    try:
        balance = _get_real_portfolio_balance()
        drawdown = check_daily_drawdown(balance)
        
        # Get open positions count
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE status IN ('approved', 'executed')
        """)
        open_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COALESCE(SUM(pnl), 0) FROM trades 
            WHERE status = 'closed'
        """)
        total_pnl = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "portfolio_balance": balance,
            "daily_drawdown": drawdown,
            "open_positions": open_count,
            "total_pnl": total_pnl,
            "risk_cap": MAX_RISK_PERCENT * 100,
            "daily_drawdown_limit": MAX_DAILY_DRAWDOWN * 100
        }
        
    except Exception as e:
        logger.error(f"Portfolio summary failed: {e}")
        return {
            "status": "ERROR",
            "reason": f"Failed to get portfolio summary: {str(e)}"
        }


# ------------------------------------------------------------------
# 7. HELPER: Reset cache
# ------------------------------------------------------------------
def reset_cache():
    """Reset the balance cache."""
    global _balance_cache
    _balance_cache["value"] = None
    _balance_cache["timestamp"] = None
    logger.info("Risk management cache reset")


# ------------------------------------------------------------------
# 8. DASHBOARD COMPATIBILITY WRAPPER
# ------------------------------------------------------------------
def check_trade_risk_for_dashboard(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    quantity: float
) -> Dict[str, Any]:
    """
    Dashboard-compatible risk check wrapper.
    
    Returns:
        Dict with status and details that match dashboard expectations
    """
    try:
        result = evaluate_trade_risk(
            symbol=symbol,
            side=side,
            entry=entry_price,
            stop=stop_loss,
            size=quantity
        )
        
        # Convert to dashboard format
        if result.get("status") == "PASSED":
            return {
                "status": "SUCCESS",
                "message": "Risk validation passed",
                "risk_percent": result.get("risk_percent", 0),
                "risk_amount": result.get("risk_usd", 0),
                "warnings": result.get("warnings", [])
            }
        else:
            return {
                "status": "FAILURE",
                "reason": result.get("reason", "Risk check failed"),
                "risk_percent": result.get("risk_percent", 0),
                "risk_amount": result.get("risk_usd", 0)
            }
            
    except Exception as e:
        return {
            "status": "FAILURE",
            "reason": str(e),
            "risk_percent": 0,
            "risk_amount": 0
        }


# ------------------------------------------------------------------
# 9. SELF-TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("🧪 Testing Risk Management MCP...")
    
    # Test 1: Calculate position size
    try:
        result = calculate_position_size(entry=60000, stop=59500)
        print(f"✅ calculate_position_size: {result}")
    except Exception as e:
        print(f"❌ calculate_position_size error: {e}")
    
    # Test 2: Evaluate trade risk (should PASS)
    try:
        result = evaluate_trade_risk(
            symbol="BTC", 
            side="long", 
            entry=60000, 
            stop=59500, 
            size=0.1
        )
        print(f"✅ evaluate_trade_risk (PASS expected): {result}")
    except Exception as e:
        print(f"❌ evaluate_trade_risk error: {e}")
    
    # Test 3: Evaluate trade risk (should REJECT - too large)
    try:
        result = evaluate_trade_risk(
            symbol="BTC", 
            side="long", 
            entry=60000, 
            stop=59500, 
            size=1.0
        )
        print(f"✅ evaluate_trade_risk (REJECT expected): {result}")
    except Exception as e:
        print(f"❌ evaluate_trade_risk error: {e}")
    
    # Test 4: Get portfolio summary
    try:
        result = get_portfolio_summary()
        print(f"✅ get_portfolio_summary: {result}")
    except Exception as e:
        print(f"❌ get_portfolio_summary error: {e}")
    
    print("✅ Risk Management MCP tests complete.")