"""Test that request_approval() cannot bypass risk screening."""
import pytest
from governance_engine import request_approval, screen_trade
from trade_memory_mcp import propose_trade, get_trade
from schemas import TradeStatus

# Use the same fixture as other tests
@pytest.fixture
def clean_db():
    import sqlite3
    from config import DB_PATH
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
    conn.commit()
    conn.close()

# Helper to create a proposed trade (copied from test_security)
def create_proposed_trade(symbol="BTC", side="long", quantity=0.01, entry=60000, stop=59500, reasoning="test"):
    prop = propose_trade(symbol, side, quantity, entry, stop, reasoning=reasoning)
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE trades SET portfolio_balance = 10000.0 WHERE id = ?",
        (prop["trade_id"],)
    )
    conn.commit()
    conn.close()
    return prop["trade_id"]

def test_request_approval_rejects_unscreened_trade(clean_db):
    """request_approval() must reject trades that haven't been screened."""
    tid = create_proposed_trade()
    trade = get_trade(tid)
    assert trade["status"] == TradeStatus.PROPOSED.value
    result = request_approval(tid)
    assert result["status"] == "REJECTED"
    assert "screen_trade" in result["reason"].lower() or "awaiting_approval" in result["reason"].lower()

def test_request_approval_works_after_screening(clean_db):
    """request_approval() works after screen_trade() passes."""
    tid = create_proposed_trade()
    screen_result = screen_trade(tid)
    if screen_result.get("status") != "SUCCESS":
        print(f"Screen failed: {screen_result}")
    assert screen_result["status"] == "SUCCESS", f"Screening failed: {screen_result}"
    trade = get_trade(tid)
    assert trade["status"] == TradeStatus.AWAITING_APPROVAL.value
    result = request_approval(tid)
    assert result["status"] == "success"
    assert "approval_token" in result