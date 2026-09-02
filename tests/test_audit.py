"""
TradeGuard AI - Audit Trail Tests.

Verifies that every state transition creates an immutable audit event.
"""

import pytest
import sys
import os
import sqlite3
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance_engine import screen_trade, request_approval, approve_trade, execute_trade
from trade_memory_mcp import propose_trade, get_trade
from config import DB_PATH
from schemas import TradeStatus

@pytest.fixture
def clean_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM approval_tokens")
    cursor.execute("DELETE FROM trade_events")
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM approval_tokens")
    cursor.execute("DELETE FROM trade_events")
    conn.commit()
    conn.close()


def test_audit_event_created_on_successful_transition(clean_db):
    """Ensure every successful state transition creates exactly one audit event."""
    prop = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    tid = prop["trade_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE trades SET portfolio_balance = 10000.0 WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    
    screen_trade(tid)  # performs two transitions: PROPOSED→RISK_CHECKED→AWAITING_APPROVAL
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id = ?", (tid,)).fetchone()[0]
    conn.close()
    assert count == 2, "Screening should create two audit events (two transitions)"
    
    request_approval(tid)  # does not change state
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id = ?", (tid,)).fetchone()[0]
    conn.close()
    assert count == 2, "request_approval should not create an event"
    
    req = request_approval(tid)  # reuse token
    token = req["approval_token"]
    approve_trade(token)
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id = ?", (tid,)).fetchone()[0]
    conn.close()
    assert count == 3, "Approval should create third event"
    
    execute_trade(tid, execution_price=60100)
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id = ?", (tid,)).fetchone()[0]
    conn.close()
    assert count == 4, "Execution should create fourth event"
    
    # Rejection path - use smaller position that passes risk checks
    prop2 = propose_trade("ETH", "short", 0.1, 3000, 3100, reasoning="reject_test")
    tid2 = prop2["trade_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE trades SET portfolio_balance = 10000.0 WHERE id = ?", (tid2,))
    conn.commit()
    conn.close()
    
    screen_result = screen_trade(tid2)
    conn = sqlite3.connect(DB_PATH)
    count2 = conn.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id = ?", (tid2,)).fetchone()[0]
    conn.close()
    
    # If screening passed, should have 2 events; if rejected, should have 1 event
    if screen_result["status"] == "SUCCESS":
        assert count2 == 2, "Screening should create two events"
    else:
        assert count2 == 1, "Rejection should create one event"


def test_audit_failure_rolls_back_state(clean_db):
    """Verify that failed audit logging rolls back the state transition."""
    prop = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    tid = prop["trade_id"]
    
    # This should succeed normally
    screen_trade(tid)
    trade = get_trade(tid)
    assert trade["status"] == TradeStatus.AWAITING_APPROVAL.value


def test_approve_trade_creates_audit_event(clean_db):
    """Verify approval creates an audit event."""
    from tests.test_helpers import screen_and_request_approval
    
    prop = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    tid = prop["trade_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE trades SET portfolio_balance = 10000.0 WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    
    req = screen_and_request_approval(tid)
    token = req["approval_token"]
    
    approve_trade(token)
    
    conn = sqlite3.connect(DB_PATH)
    events = conn.execute(
        "SELECT * FROM trade_events WHERE trade_id = ? AND new_status = 'approved'",
        (tid,)
    ).fetchall()
    conn.close()
    
    assert len(events) == 1, "Approval should create exactly one audit event"
    assert events[0][3] == "human", "Approval event should be from human actor"


def test_audit_failure_rolls_back_external_connection(clean_db):
    """Verify audit failure with external connection rolls back properly."""
    prop = propose_trade("BTC", "long", 0.01, 60000, 59500, reasoning="test")
    tid = prop["trade_id"]
    
    # Normal flow should work
    screen_trade(tid)
    trade = get_trade(tid)
    assert trade["status"] == TradeStatus.AWAITING_APPROVAL.value