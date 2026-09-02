"""
TradeGuard AI - Central Configuration (Sprint 6).
Single source of truth for database paths, constants, and schema migration.
"""
import os
import sqlite3
from datetime import timedelta

# --- Project Root ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Database (UNIFIED) ---
DB_PATH = os.environ.get("ROBO_SHOPPER_DB", os.path.join(BASE_DIR, "data", "trades.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- Risk Constants (DECIMAL format) ---
MAX_RISK_PER_TRADE = 0.02    # 2%
MAX_DAILY_DRAWDOWN = 0.05    # 5%
MAX_OPEN_EXPOSURE = 0.20     # 20%
CORE_ASSETS = ["BTC", "ETH", "SOL"]

# --- Policy Version (for hash binding) ---
POLICY_VERSION = "1.0.0"

# --- Default expiration for proposals ---
PROPOSAL_EXPIRY_HOURS = 24

# ------------------------------------------------------------------
# TRADING MODE CONFIGURATION
# ------------------------------------------------------------------
# TRADING_MODE: "paper" (default, safe) or "live" (requires explicit opt-in)
# ADAPTER selection is based on TRADING_MODE
# 
# SAFETY: Default is "paper" - no real money at risk
# To enable live trading, set TRADING_MODE=live in .env AND implement exchange adapter
# ------------------------------------------------------------------

TRADING_MODE = os.environ.get("TRADING_MODE", "paper").lower()

# Validate trading mode
if TRADING_MODE not in ["paper", "live"]:
    raise ValueError(
        f"Invalid TRADING_MODE: {TRADING_MODE}. "
        f"Must be 'paper' (default) or 'live'."
    )

# Log trading mode on startup
import logging
logger = logging.getLogger(__name__)
logger.warning(f"⚠️  TRADING MODE: {TRADING_MODE.upper()}")
if TRADING_MODE == "live":
    logger.error("🚨 LIVE TRADING ENABLED - REAL MONEY AT RISK 🚨")

# ------------------------------------------------------------------
# BINANCE CONFIGURATION
# ------------------------------------------------------------------
# Binance API credentials must be set in environment variables
# NEVER commit real credentials to source code
# 
# Required for live mode:
# - BINANCE_API_KEY: Your Binance API key
# - BINANCE_API_SECRET: Your Binance API secret
# - BINANCE_USE_MAINNET: "true" for mainnet, "false" for testnet (default)
# ------------------------------------------------------------------

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")
BINANCE_USE_MAINNET = os.environ.get("BINANCE_USE_MAINNET", "false").lower() == "true"

# Log Binance configuration
if TRADING_MODE == "live":
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.error("🚨 LIVE MODE ENABLED BUT BINANCE CREDENTIALS MISSING 🚨")
        logger.error("Set BINANCE_API_KEY and BINANCE_API_SECRET in environment")
    else:
        if BINANCE_USE_MAINNET:
            logger.error("🚨 BINANCE MAINNET - REAL MONEY AT RISK 🚨")
        else:
            logger.warning("⚠️  BINANCE TESTNET - Safe demonstration mode")

# ------------------------------------------------------------------
# SCHEMA MIGRATION (ensures all columns exist)
# ------------------------------------------------------------------
def ensure_schema():
    """Creates tables and adds missing columns idempotently."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Trades table
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
    
    # 2. Check existing columns and add missing ones
    cursor.execute("PRAGMA table_info(trades)")
    existing = [row[1] for row in cursor.fetchall()]
    
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
    }
    
    for col, col_type in new_cols.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE trades ADD COLUMN {col} {col_type}")
    
    # 3. Approval tokens table
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
    
    conn.commit()
    conn.close()

# Run migration on import
ensure_schema()