import pytest
import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trade_memory_mcp import propose_trade, get_trade
from governance_engine import screen_trade
from config import DB_PATH

# ------------------------------------------------------------------
# HELPER: Set treasury balance
# ------------------------------------------------------------------
def set_treasury_balance(balance):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("BEGIN TRANSACTION")
    cursor.execute("DELETE FROM treasury")
    cursor.execute("INSERT INTO treasury (id, current_balance) VALUES (1, ?)", (balance,))
    cursor.execute("COMMIT")
    conn.close()

# ------------------------------------------------------------------
# FIXTURE
# ------------------------------------------------------------------
@pytest.fixture
def clean_db():
    set_treasury_balance(10000.0)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM approval_tokens")
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM approval_tokens")
    cursor.execute("DELETE FROM treasury")
    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# TESTS
# ------------------------------------------------------------------
def test_propose_trade_accepts_any_valid_input(clean_db):
    result = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    assert result["status"] == "success"
    assert result["trade_id"] > 0

def test_screen_trade_rejects_high_risk_proposals(clean_db):
    # Verify treasury balance
    conn = sqlite3.connect(DB_PATH)
    balance = conn.execute("SELECT current_balance FROM treasury").fetchone()[0]
    conn.close()
    assert balance == 10000.0

    # 0.5 BTC with $500 stop distance = $250 risk (2.5% of $10k) → should reject
    result = propose_trade("BTC", "long", 0.5, 60000, 59500, reasoning="test")
    screen_res = screen_trade(result["trade_id"])
    assert screen_res["status"] == "REJECTED", f"Expected REJECTED, got {screen_res}"
    assert "2.0% cap" in screen_res["reason"] 

def test_risk_amount_calculation_is_deterministic(clean_db):
    result1 = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    trade1 = get_trade(result1["trade_id"])
    result2 = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    trade2 = get_trade(result2["trade_id"])
    assert trade1["risk_amount"] == trade2["risk_amount"]
    assert trade1["risk_percent"] == trade2["risk_percent"]

def test_propose_trade_always_sets_status_proposed(clean_db):
    result = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    trade = get_trade(result["trade_id"])
    assert trade["status"] == "proposed"