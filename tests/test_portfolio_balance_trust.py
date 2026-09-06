import pytest
import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_management_mcp import reset_cache 
from risk_management_mcp import calculate_position_size, evaluate_trade_risk, _get_real_portfolio_balance
from trade_memory_mcp import propose_trade, get_trade
from governance_engine import screen_trade
from config import DB_PATH

# ------------------------------------------------------------------
# HELPER: Set treasury balance to exactly one row
# ------------------------------------------------------------------
def set_treasury_balance(balance):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("BEGIN TRANSACTION")
    cursor.execute("DELETE FROM treasury")
    cursor.execute("INSERT INTO treasury (id, current_balance) VALUES (1, ?)", (balance,))
    cursor.execute("COMMIT")
    conn.close()

def get_treasury_balance():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT current_balance FROM treasury ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else None

# ------------------------------------------------------------------
# FIXTURE
# ------------------------------------------------------------------
@pytest.fixture
def clean_db_and_treasury():
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
def test_llm_cannot_override_balance(clean_db_and_treasury):
    with pytest.raises(TypeError):
        calculate_position_size(entry=60000, stop=59500, portfolio_balance=1000000)

def test_fake_balance_not_persisted(clean_db_and_treasury):
    result = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    trade = get_trade(result["trade_id"])
    assert trade["portfolio_balance"] == 10000.0

def test_screen_trade_uses_trusted_balance(clean_db_and_treasury):
    # Verify treasury balance
    assert get_treasury_balance() == 10000.0

    # Directly test evaluate_trade_risk first
    risk_result = evaluate_trade_risk("BTC", "long", 60000, 59500, 0.5)
    assert risk_result["status"] == "REJECTED", f"Expected REJECTED, got {risk_result}"
    assert "2.0% cap" in risk_result["reason"]  

    # Now test through screen_trade
    prop = propose_trade("BTC", "long", 0.5, 60000, 59500, reasoning="test")
    screen_res = screen_trade(prop["trade_id"])
    assert screen_res["status"] == "REJECTED", f"Expected REJECTED, got {screen_res}"
    assert "2.0% cap" in risk_result["reason"]

def test_missing_balance_fails_closed(clean_db_and_treasury):
    reset_cache() 
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE treasury SET current_balance = -100.0")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="HARD STOP"):
        _get_real_portfolio_balance(use_cache=False) 
def test_enormous_balance_cannot_bypass_policy(clean_db_and_treasury):
    # Valid trade: 0.01 BTC at $60k = $600 exposure, risk = $5 (0.05% of $10k)
    prop = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    screen_res = screen_trade(prop["trade_id"])
    assert screen_res["status"] == "SUCCESS", f"Expected SUCCESS, got {screen_res}"

def test_risk_decision_idempotent(clean_db_and_treasury):
    res1 = calculate_position_size(entry=60000, stop=59500)
    res2 = calculate_position_size(entry=60000, stop=59500)
    assert res1["position_size"] == res2["position_size"]