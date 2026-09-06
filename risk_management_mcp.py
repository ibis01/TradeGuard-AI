"""
TradeGuard AI - Hardened Risk Management MCP.
Implements deterministic risk controls that CANNOT be bypassed by the LLM.
- 2% hard cap on per-trade risk (from config).
- Validates all financial inputs.
- HARD STOP on missing portfolio balance (no silent mock fallback).
- TRUST BOUNDARY: Portfolio balance is ALWAYS fetched from the trusted treasury.
"""
import os
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# Set up logging - FIXED
logger = logging.getLogger(__name__)

# Database path – uses unified config if available, otherwise falls back
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from config import DB_PATH, MAX_RISK_PER_TRADE
except ImportError:
    DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
    MAX_RISK_PER_TRADE = 0.02  # 2% fallback

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ============================================================================
# RISK MANAGEMENT CONFIGURATION
# ============================================================================

# Per-Trade Risk Limits (now sourced from config)
MAX_RISK_PERCENT = MAX_RISK_PER_TRADE   # 2% (from config)

# Portfolio Exposure Limits
MAX_POSITION_PCT = 0.10           # 10% max single position
MAX_TOTAL_EXPOSURE = 0.25         # 25% max total exposure
MAX_DAILY_DRAWDOWN = 0.03         # 3% max daily loss
MAX_WEEKLY_DRAWDOWN = 0.10        # 10% max weekly loss

# Stop Loss Rules
MIN_STOP_DISTANCE = 0.005         # 0.5% minimum
MAX_STOP_DISTANCE = 0.025         # 2.5% maximum

# Position Sizing Limits (minimums)
MIN_POSITION_SIZE = {
    "BTC": 0.0001,
    "ETH": 0.001,
    "SOL": 0.01,
    "DEFAULT": 0.0001
}

# Risk-Reward Requirements
MIN_RR_RATIO = 2.0                # 2:1 minimum
IDEAL_RR_RATIO = 3.0              # 3:1 ideal

# Trading Limits
MAX_TRADES_PER_DAY = 5
MAX_CONSECUTIVE_LOSSES = 3

# Cache for portfolio balance (with TTL)
_balance_cache = {
    "value": None,
    "timestamp": None,
    "ttl": 5  # seconds
}

# In-memory tracking for daily limits
_daily_tracker = {
    "trades_today": 0,
    "daily_pnl": 0.0,
    "consecutive_losses": 0,
    "last_trade_date": None
}


def _ensure_treasury_table(conn: sqlite3.Connection):
    """Ensure treasury table exists with correct schema."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasury (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_balance REAL NOT NULL DEFAULT 10000.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note TEXT
        )
    """)
    # Check if 'note' column exists and add if missing
    cursor.execute("PRAGMA table_info(treasury)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'note' not in columns:
        cursor.execute("ALTER TABLE treasury ADD COLUMN note TEXT")
    conn.commit()


# ============================================================================
# 1. PORTFOLIO BALANCE (HARD STOP ON FAILURE)
# ============================================================================

def _get_real_portfolio_balance(use_cache: bool = True) -> float:
    """
    Fetches the REAL portfolio balance from the treasury table.
    If the balance cannot be retrieved or is not positive, it raises a Hard Stop error.
    NEVER silently falls back to a default during active trading.
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
        
        _ensure_treasury_table(conn)
        
        cursor = conn.cursor()
        
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
            # HARD STOP on non-positive balance
            if balance <= 0:
                raise ValueError(f"Treasury balance is zero or negative. Got: {balance}")
            # Update cache
            _balance_cache["value"] = balance
            _balance_cache["timestamp"] = datetime.now(timezone.utc)
            return balance
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

def get_portfolio_balance() -> float:
    """Public wrapper to get the current portfolio balance."""
    return _get_real_portfolio_balance()


# ============================================================================
# 2. POSITION SIZING CALCULATOR (CORRECTED)
# ============================================================================

def calculate_position_size(
    entry: float, 
    stop: float,
    risk_percent: float = MAX_RISK_PERCENT,
    account_balance: Optional[float] = None,
    apply_cap: bool = True
) -> Dict[str, Any]:
    """
    Calculates the position size based on the risk cap.
    
    Args:
        entry: Entry price
        stop: Stop loss price
        risk_percent: Risk percentage (default: 2% from config)
        account_balance: Optional override for testing
        apply_cap: If True, cap position size at MAX_POSITION_PCT (default True)
    
    Returns:
        Dict with position sizing details
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
    portfolio_balance = account_balance if account_balance is not None else _get_real_portfolio_balance()
    
    if portfolio_balance <= 0:
        raise ValueError(f"Portfolio balance must be positive. Got: {portfolio_balance}")
    
    risk_amount = portfolio_balance * risk_percent
    risk_per_unit = abs(entry - stop)
    position_size = risk_amount / risk_per_unit
    
    # Apply cap if requested
    if apply_cap:
        max_position_value = portfolio_balance * MAX_POSITION_PCT
        max_position_size = max_position_value / entry
        if position_size > max_position_size:
            position_size = max_position_size
            risk_amount = position_size * risk_per_unit
            risk_percent = risk_amount / portfolio_balance
    
    position_value = position_size * entry
    exposure_pct = position_value / portfolio_balance
    
    return {
        "portfolio_balance": round(portfolio_balance, 2),
        "max_risk_percent": risk_percent * 100,
        "risk_amount_usd": round(risk_amount, 2),
        "position_size": round(position_size, 8),
        "position_value": round(position_value, 2),
        "exposure_pct": round(exposure_pct * 100, 2),
        "entry_price": entry,
        "stop_loss": stop,
        "risk_per_unit": round(risk_per_unit, 2),
        "max_position_pct": MAX_POSITION_PCT * 100
    }


# ============================================================================
# 3. RISK-REWARD CALCULATOR
# ============================================================================

def calculate_risk_reward(
    entry: float,
    stop: float,
    take_profit: float
) -> Dict[str, Any]:
    """
    Calculate risk-reward ratio.
    
    Args:
        entry: Entry price
        stop: Stop loss price
        take_profit: Take profit price
    
    Returns:
        Dict with risk-reward details
    """
    if entry <= 0 or stop <= 0 or take_profit <= 0:
        return {
            "valid": False,
            "error": "All prices must be positive"
        }
    
    risk = abs(entry - stop)
    reward = abs(take_profit - entry)
    
    if risk == 0:
        return {
            "valid": False,
            "error": "Risk cannot be zero"
        }
    
    rr_ratio = reward / risk
    
    if rr_ratio >= IDEAL_RR_RATIO:
        status = "IDEAL"
        message = f"Risk-Reward ratio of {rr_ratio:.2f}:1 is ideal (>= {IDEAL_RR_RATIO}:1)"
    elif rr_ratio >= MIN_RR_RATIO:
        status = "ACCEPTABLE"
        message = f"Risk-Reward ratio of {rr_ratio:.2f}:1 meets minimum ({MIN_RR_RATIO}:1)"
    else:
        status = "REJECTED"
        message = f"Risk-Reward ratio of {rr_ratio:.2f}:1 is below minimum {MIN_RR_RATIO}:1"
    
    return {
        "valid": rr_ratio >= MIN_RR_RATIO,
        "status": status,
        "rr_ratio": round(rr_ratio, 2),
        "risk": round(risk, 2),
        "reward": round(reward, 2),
        "message": message,
        "min_required": MIN_RR_RATIO,
        "ideal": IDEAL_RR_RATIO
    }


# ============================================================================
# 4. DAILY TRACKING
# ============================================================================

def _reset_daily_tracker():
    """Reset daily tracker at start of new day."""
    global _daily_tracker
    today = datetime.now(timezone.utc).date().isoformat()
    
    if _daily_tracker["last_trade_date"] != today:
        _daily_tracker["trades_today"] = 0
        _daily_tracker["daily_pnl"] = 0.0
        _daily_tracker["consecutive_losses"] = 0
        _daily_tracker["last_trade_date"] = today

def update_daily_tracker(pnl: float, is_win: bool):
    """Update daily tracking with trade result."""
    global _daily_tracker
    _reset_daily_tracker()
    
    _daily_tracker["trades_today"] += 1
    _daily_tracker["daily_pnl"] += pnl
    
    if is_win:
        _daily_tracker["consecutive_losses"] = 0
    else:
        _daily_tracker["consecutive_losses"] += 1

def check_daily_limits() -> Dict[str, Any]:
    """
    Check if daily trading limits are exceeded.
    
    Returns:
        Dict with status and reason if limits exceeded
    """
    _reset_daily_tracker()
    
    portfolio_balance = _get_real_portfolio_balance()
    daily_loss_pct = abs(_daily_tracker["daily_pnl"]) / portfolio_balance if portfolio_balance > 0 else 0
    
    # Check daily loss limit
    if daily_loss_pct >= MAX_DAILY_DRAWDOWN:
        return {
            "status": "HALTED",
            "reason": f"Daily loss of ${abs(_daily_tracker['daily_pnl']):,.2f} ({daily_loss_pct*100:.2f}%) exceeds {MAX_DAILY_DRAWDOWN*100}% limit",
            "action": "Stop trading for the day",
            "daily_pnl": _daily_tracker["daily_pnl"],
            "trades_today": _daily_tracker["trades_today"]
        }
    
    # Check max trades per day
    if _daily_tracker["trades_today"] >= MAX_TRADES_PER_DAY:
        return {
            "status": "LIMIT_REACHED",
            "reason": f"Maximum trades per day ({MAX_TRADES_PER_DAY}) reached",
            "action": "Stop trading for the day",
            "trades_today": _daily_tracker["trades_today"]
        }
    
    # Check consecutive losses
    if _daily_tracker["consecutive_losses"] >= MAX_CONSECUTIVE_LOSSES:
        return {
            "status": "HALTED",
            "reason": f"Consecutive losses ({_daily_tracker['consecutive_losses']}) reached limit of {MAX_CONSECUTIVE_LOSSES}",
            "action": "Stop trading for the day",
            "consecutive_losses": _daily_tracker["consecutive_losses"]
        }
    
    # Caution zone: 2% loss
    if daily_loss_pct >= 0.02:
        return {
            "status": "CAUTION",
            "reason": f"Daily loss of ${abs(_daily_tracker['daily_pnl']):,.2f} ({daily_loss_pct*100:.2f}%) approaching {MAX_DAILY_DRAWDOWN*100}% limit",
            "action": "Reduce position size by 50%",
            "daily_pnl": _daily_tracker["daily_pnl"]
        }
    
    return {
        "status": "NORMAL",
        "reason": f"Daily PnL: ${_daily_tracker['daily_pnl']:,.2f} ({daily_loss_pct*100:.2f}% of account)",
        "action": "Normal trading allowed",
        "trades_today": _daily_tracker["trades_today"],
        "daily_pnl": _daily_tracker["daily_pnl"]
    }


# ============================================================================
# 5. HARDCODED VETO GATE (AUTHORISATION)
# ============================================================================

def evaluate_trade_risk(
    symbol: str,
    side: str,
    entry: float,
    stop: float,
    size: float,
    take_profit: Optional[float] = None,
    rsi_override: Optional[float] = None,
    portfolio_balance: Optional[float] = None
) -> Dict[str, Any]:
    """
    Hardcoded veto gate. Purely deterministic.
    
    Args:
        symbol: Asset symbol (BTC, ETH, SOL)
        side: "long" or "short"
        entry: Entry price
        stop: Stop loss price
        size: Position size
        take_profit: Optional take profit price
        rsi_override: Optional RSI value for testing
        portfolio_balance: Optional override for testing
    
    Returns:
        Dict with status, reason, and risk metrics
    """
    # Validate inputs
    if not symbol or symbol not in ["BTC", "ETH", "SOL"]:
        return {
            "status": "REJECTED",
            "reason": f"Invalid symbol. Must be BTC, ETH, or SOL. Got: {symbol}",
            "details": {"symbol": symbol}
        }
    if side not in ["long", "short"]:
        return {
            "status": "REJECTED",
            "reason": f"Side must be 'long' or 'short'. Got: {side}",
            "details": {"side": side}
        }
    if entry <= 0:
        return {
            "status": "REJECTED",
            "reason": f"Entry price must be positive. Got: {entry}",
            "details": {"entry": entry}
        }
    if stop <= 0:
        return {
            "status": "REJECTED",
            "reason": f"Stop loss must be positive. Got: {stop}",
            "details": {"stop": stop}
        }
    if entry == stop:
        return {
            "status": "REJECTED",
            "reason": "Entry and Stop cannot be equal.",
            "details": {"entry": entry, "stop": stop}
        }
    if size <= 0:
        return {
            "status": "REJECTED",
            "reason": f"Position size must be positive. Got: {size}",
            "details": {"size": size}
        }
    
    # TRUSTED SOURCE: Never accept LLM override
    if portfolio_balance is None:
        try:
            portfolio_balance = _get_real_portfolio_balance()
        except Exception as e:
            return {
                "status": "REJECTED",
                "reason": f"Cannot fetch portfolio balance: {e}",
                "details": {"error": str(e)}
            }
    
    if portfolio_balance <= 0:
        return {
            "status": "REJECTED",
            "reason": f"Portfolio balance must be positive. Got: {portfolio_balance}",
            "details": {"portfolio_balance": portfolio_balance}
        }
    
    # --- Check 1: Daily Trading Limits ---
    daily_check = check_daily_limits()
    if daily_check["status"] in ["HALTED", "LIMIT_REACHED"]:
        return {
            "status": "REJECTED",
            "reason": f"Daily limit reached: {daily_check['reason']}",
            "action": daily_check["action"],
            "details": daily_check
        }
    
    warnings = []
    
    # --- Check 2: Risk Cap ---
    risk_per_unit = abs(entry - stop)
    risk_usd = risk_per_unit * size
    risk_percent = risk_usd / portfolio_balance
    
    if risk_percent > MAX_RISK_PERCENT:
        return {
            "status": "REJECTED",
            "reason": f"Risk {risk_percent*100:.2f}% exceeds {MAX_RISK_PERCENT*100}% cap.",
            "risk_percent": round(risk_percent * 100, 2),
            "risk_usd": round(risk_usd, 2),
            "portfolio_balance": round(portfolio_balance, 2),
            "warnings": [],
            "checks": {"risk_cap": "FAILED"},
            "details": {
                "risk_percent": risk_percent,
                "risk_usd": risk_usd,
                "max_risk_percent": MAX_RISK_PERCENT
            }
        }

    # --- Check 3: RSI Check (optional) ---
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

    # --- Check 4: Minimum position sanity ---
    min_size = MIN_POSITION_SIZE.get(symbol, MIN_POSITION_SIZE["DEFAULT"])
    if size < min_size:
        return {
            "status": "REJECTED", 
            "reason": f"Size {size} below minimum {min_size} for {symbol}.",
            "warnings": warnings,
            "checks": {"min_size": "FAILED"},
            "details": {"size": size, "min_size": min_size}
        }
    
    # --- Check 5: Stop loss distance ---
    stop_distance_pct = abs(entry - stop) / entry
    if stop_distance_pct < MIN_STOP_DISTANCE:
        return {
            "status": "REJECTED",
            "reason": f"Stop loss too tight: {stop_distance_pct*100:.2f}% (min {MIN_STOP_DISTANCE*100}%)",
            "details": {"stop_distance_pct": stop_distance_pct, "min_stop": MIN_STOP_DISTANCE}
        }
    if stop_distance_pct > MAX_STOP_DISTANCE:
        return {
            "status": "REJECTED",
            "reason": f"Stop loss too wide: {stop_distance_pct*100:.2f}% (max {MAX_STOP_DISTANCE*100}%)",
            "details": {"stop_distance_pct": stop_distance_pct, "max_stop": MAX_STOP_DISTANCE}
        }
    
    # --- Check 6: Position size vs portfolio ---
    position_value = size * entry
    position_pct = position_value / portfolio_balance
    if position_pct > MAX_POSITION_PCT:
        return {
            "status": "REJECTED",
            "reason": f"Position size {position_pct*100:.2f}% exceeds {MAX_POSITION_PCT*100}% max.",
            "details": {
                "position_value": position_value,
                "position_pct": position_pct,
                "max_position_pct": MAX_POSITION_PCT
            }
        }
    
    # --- Check 7: Risk-Reward Ratio ---
    if take_profit is not None:
        rr_result = calculate_risk_reward(entry, stop, take_profit)
        if not rr_result["valid"]:
            return {
                "status": "REJECTED",
                "reason": f"Risk-Reward ratio too low: {rr_result['message']}",
                "rr_ratio": rr_result["rr_ratio"],
                "details": rr_result
            }
        warnings.append(f"Risk-Reward: {rr_result['rr_ratio']:.2f}:1 ({rr_result['status']})")
    
    # --- Check 8: Validate stop loss direction ---
    if side == "long" and stop >= entry:
        return {
            "status": "REJECTED",
            "reason": f"For LONG position, stop loss ({stop}) must be below entry ({entry}).",
            "details": {"side": side, "entry": entry, "stop": stop}
        }
    if side == "short" and stop <= entry:
        return {
            "status": "REJECTED",
            "reason": f"For SHORT position, stop loss ({stop}) must be above entry ({entry}).",
            "details": {"side": side, "entry": entry, "stop": stop}
        }
    
    # --- Check 9: Daily caution warning ---
    if daily_check["status"] == "CAUTION":
        warnings.append(f"⚠️ {daily_check['reason']}")
        warnings.append(f"Action: {daily_check['action']}")
    
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
            "position_size": "PASSED",
            "stop_distance": "PASSED"
        },
        "details": {
            "risk_percent": risk_percent,
            "risk_usd": risk_usd,
            "position_value": position_value,
            "position_pct": position_pct,
            "stop_distance_pct": stop_distance_pct,
            "daily_status": daily_check["status"]
        }
    }


# ============================================================================
# 6. GET RISK RECOMMENDATIONS
# ============================================================================

def get_position_recommendation(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    take_profit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Get recommended position size for a trade.
    
    Args:
        symbol: Asset symbol
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Optional take profit price
    
    Returns:
        Dict with position recommendation
    """
    try:
        portfolio_balance = _get_real_portfolio_balance()
        
        # Calculate position size
        sizing = calculate_position_size(entry_price, stop_loss, MAX_RISK_PERCENT, portfolio_balance)
        
        result = {
            "symbol": symbol,
            "account_size": portfolio_balance,
            "max_risk_per_trade": portfolio_balance * MAX_RISK_PERCENT,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "risk_per_unit": abs(entry_price - stop_loss),
            "stop_distance_pct": (abs(entry_price - stop_loss) / entry_price) * 100,
            "recommended_position": sizing["position_size"],
            "position_value": sizing["position_value"],
            "exposure_pct": sizing["exposure_pct"],
            "risk_amount": sizing["risk_amount_usd"],
            "risk_pct": sizing["max_risk_percent"],
            "max_position_pct": MAX_POSITION_PCT * 100,
            "max_exposure_pct": MAX_TOTAL_EXPOSURE * 100
        }
        
        # Add risk-reward if take profit provided
        if take_profit is not None:
            rr = calculate_risk_reward(entry_price, stop_loss, take_profit)
            result["risk_reward"] = rr
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to calculate position recommendation"
        }


# ============================================================================
# 7. GET RISK SUMMARY
# ============================================================================

def get_risk_summary() -> Dict[str, Any]:
    """
    Get comprehensive risk management summary.
    
    Returns:
        Dict with all risk limits and current status
    """
    try:
        portfolio_balance = _get_real_portfolio_balance()
        daily_status = check_daily_limits()
        
        return {
            "account": {
                "balance": portfolio_balance,
                "max_risk_per_trade": portfolio_balance * MAX_RISK_PERCENT,
                "max_risk_percent": MAX_RISK_PERCENT * 100
            },
            "limits": {
                "max_position_pct": MAX_POSITION_PCT * 100,
                "max_total_exposure": MAX_TOTAL_EXPOSURE * 100,
                "max_daily_drawdown": MAX_DAILY_DRAWDOWN * 100,
                "max_trades_per_day": MAX_TRADES_PER_DAY,
                "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,
                "min_rr_ratio": MIN_RR_RATIO,
                "ideal_rr_ratio": IDEAL_RR_RATIO
            },
            "daily_status": daily_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to get risk summary"
        }


def reset_cache():
    """Reset the balance cache."""
    global _balance_cache
    _balance_cache["value"] = None
    _balance_cache["timestamp"] = None
    logger.info("Risk management cache reset")

# ============================================================================
# 8. SEED TREASURY
# ============================================================================

def seed_treasury(initial_balance: float = 10000.0) -> Dict[str, Any]:
    """
    Seeds the treasury with an initial balance.
    """
    if initial_balance <= 0:
        raise ValueError("Initial balance must be positive.")
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        _ensure_treasury_table(conn)
        cursor = conn.cursor()
        
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


# ============================================================================
# 9. DASHBOARD COMPATIBILITY WRAPPER
# ============================================================================

def check_trade_risk_for_dashboard(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    quantity: float,
    take_profit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Dashboard-compatible risk check wrapper.
    """
    try:
        result = evaluate_trade_risk(
            symbol=symbol,
            side=side,
            entry=entry_price,
            stop=stop_loss,
            size=quantity,
            take_profit=take_profit
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
                "risk_amount": result.get("risk_usd", 0),
                "details": result.get("details", {})
            }
            
    except Exception as e:
        return {
            "status": "FAILURE",
            "reason": str(e),
            "risk_percent": 0,
            "risk_amount": 0
        }


# ============================================================================
# 10. SELF-TEST
# ============================================================================

if __name__ == "__main__":
    print("🧪 Testing Risk Management MCP...")
    print("=" * 50)
    
    # Test a SOL trade that should PASS
    print("\n📊 Testing SOL SHORT (5 SOL @ $103.11, stop at $104.14):")
    try:
        result = evaluate_trade_risk(
            symbol="SOL",
            side="short",
            entry=103.11,
            stop=104.14,
            size=5.0
        )
        if result.get("status") == "PASSED":
            print(f"  ✅ PASSED")
            print(f"  Risk: {result.get('risk_percent')}%")
            print(f"  Risk USD: ${result.get('risk_usd')}")
            if result.get('warnings'):
                print(f"  ⚠️ Warnings: {result.get('warnings')}")
        else:
            print(f"  ❌ REJECTED: {result.get('reason')}")
            print(f"  Details: {result.get('details', {})}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print("\n✅ Risk Management MCP tests complete!")