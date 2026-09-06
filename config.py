"""
TradeGuard AI - Central Configuration.
Single source of truth for database paths, constants, and schema migration.
"""
import os
import sqlite3
import logging
from datetime import timedelta

# Set up logging
logger = logging.getLogger(__name__)

# ============================================================================
# TRADING MODE
# ============================================================================

TRADING_MODE = os.environ.get("TRADING_MODE", "paper").lower()

if TRADING_MODE not in ["paper", "live"]:
    raise ValueError(
        f"Invalid TRADING_MODE: {TRADING_MODE}. "
        f"Must be 'paper' (default) or 'live'."
    )

logger.warning(f"⚠️ TRADING MODE: {TRADING_MODE.upper()}")
if TRADING_MODE == "live":
    logger.error("🚨 LIVE TRADING ENABLED - REAL MONEY AT RISK 🚨")

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TRADEGUARD_DB", os.path.join(BASE_DIR, "data", "trades.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ============================================================================
# RISK CONSTANTS
# ============================================================================

# Per-Trade Risk
MAX_RISK_PER_TRADE = 0.02  # 2% max risk per trade
MAX_RISK_DOLLAR = 200.0  # $200 max risk for $10k account

# Daily Limits
MAX_DAILY_DRAWDOWN = 0.05  # 5% max daily loss
MAX_TRADES_PER_DAY = 5
MAX_CONSECUTIVE_LOSSES = 3

# Exposure Limits
MAX_OPEN_EXPOSURE = 0.25  # 25% max total exposure
MAX_POSITION_PCT = 0.10  # 10% max single position

# Stop Loss Rules
MIN_STOP_DISTANCE = 0.002  # 0.2% minimum stop distance
MAX_STOP_DISTANCE = 0.05  # 5% maximum stop distance

# Risk-Reward
MIN_RR_RATIO = 1.5  # Minimum 1.5:1
IDEAL_RR_RATIO = 3.0  # Ideal 3:1

# Account
ACCOUNT_SIZE = 10000.0  # $10,000 account
CORE_ASSETS = ["BTC", "ETH", "SOL"]

# Position Sizing
MIN_POSITION_SIZE = {
    "BTC": 0.00001,
    "ETH": 0.0001,
    "SOL": 0.001,
    "DEFAULT": 0.00001
}

# ============================================================================
# POLICY
# ============================================================================

POLICY_VERSION = "1.0.0"
PROPOSAL_EXPIRY_HOURS = 24

# ============================================================================
# SCHEMA MIGRATION
# ============================================================================

def ensure_schema():
    """Creates tables and adds missing columns idempotently."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            side TEXT,
            quantity REAL,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            reasoning TEXT,
            portfolio_balance REAL,
            risk_percent REAL,
            risk_amount REAL,
            proposal_expires_at TIMESTAMP,
            status TEXT,
            created_at TIMESTAMP,
            risk_checked_at TIMESTAMP,
            approval_requested_at TIMESTAMP,
            approved_at TIMESTAMP,
            approved_by TEXT,
            executed_at TIMESTAMP,
            execution_price REAL,
            closed_at TIMESTAMP,
            pnl REAL,
            feedback TEXT,
            proposal_hash TEXT,
            last_modified_by TEXT,
            transition_metadata TEXT,
            last_modified_at TIMESTAMP,
            policy_version TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(trades)")
    existing = [row[1] for row in cursor.fetchall()]
    
    # config.py (excerpt, only the new_cols part)
    new_cols = {
    "risk_percent": "REAL",
    "risk_amount": "REAL",
    "proposal_expires_at": "TIMESTAMP",
    "proposal_hash": "TEXT",
    "last_modified_by": "TEXT",
    "transition_metadata": "TEXT",
    "last_modified_at": "TIMESTAMP",
    "policy_version": "TEXT",
    "approval_requested_at": "TIMESTAMP",
    "execution_price": "REAL",
    "approved_by": "TEXT",
    "take_profit": "REAL",
    "rejection_reason": "TEXT",   # 
}
    
    for col, col_type in new_cols.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE trades ADD COLUMN {col} {col_type}")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            trade_id INTEGER,
            proposal_hash TEXT,
            policy_version TEXT,
            requested_by TEXT,
            expires_at TIMESTAMP,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasury (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_balance REAL NOT NULL DEFAULT 10000.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Database schema verified")

# Run migration on import
ensure_schema()