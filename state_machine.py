# state_machine.py
"""
TradeGuard AI - Single State-Transition Authority (Sprint 5).
ONE function responsible for EVERY state mutation.
Supports external connections for atomic transactions.
"""
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from config import DB_PATH
from schemas import TradeStatus, ActorType

# --- Legal transitions ---
ALLOWED_TRANSITIONS = {
    TradeStatus.ANALYZING: [TradeStatus.PROPOSED, TradeStatus.REJECTED],
    TradeStatus.PROPOSED: [TradeStatus.RISK_CHECKED, TradeStatus.REJECTED],
    TradeStatus.RISK_CHECKED: [TradeStatus.AWAITING_APPROVAL, TradeStatus.REJECTED],
    TradeStatus.AWAITING_APPROVAL: [TradeStatus.APPROVED, TradeStatus.REJECTED],
    TradeStatus.APPROVED: [TradeStatus.EXECUTED, TradeStatus.CLOSED],  # cannot reject after approval
    TradeStatus.EXECUTED: [TradeStatus.CLOSED],
    TradeStatus.REJECTED: [],  # Terminal state
    TradeStatus.CLOSED: [],    # Terminal state
}

# --- Authorized actors ---
AUTHORIZED_ACTORS = {
    TradeStatus.PROPOSED: [ActorType.AI, ActorType.SYSTEM],
    TradeStatus.RISK_CHECKED: [ActorType.RISK_ENGINE],
    TradeStatus.AWAITING_APPROVAL: [ActorType.RISK_ENGINE],
    TradeStatus.APPROVED: [ActorType.HUMAN],                  # ONLY human
    TradeStatus.EXECUTED: [ActorType.EXECUTION_GATEWAY],      # NOT human directly
    TradeStatus.REJECTED: [ActorType.RISK_ENGINE, ActorType.GUARDRAIL, ActorType.HUMAN],
    TradeStatus.CLOSED: [ActorType.SYSTEM],
}

# ------------------------------------------------------------------
# IDEMPOTENCY CHECK
# ------------------------------------------------------------------
def _is_already_in_state(conn: sqlite3.Connection, trade_id: int, target_status: TradeStatus) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    return row and row[0] == target_status.value


def _get_current_status(conn: sqlite3.Connection, trade_id: int) -> Optional[str]:
    """Get current status of a trade."""
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    return row[0] if row else None


# ------------------------------------------------------------------
# 🔒 IMMUTABLE AUDIT LOG (uses the same connection)
# ------------------------------------------------------------------
def _ensure_audit_table(conn: sqlite3.Connection):
    """Ensure the audit log table exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            event_type TEXT,
            actor_type TEXT,
            old_status TEXT,
            new_status TEXT,
            metadata TEXT,
            created_at TIMESTAMP
        )
    """)


def _log_event(conn: sqlite3.Connection, trade_id: int, event_type: str, actor_type: str, 
               old_status: str, new_status: str, metadata: dict):
    """Append an immutable audit event using the provided connection."""
    _ensure_audit_table(conn)
    conn.execute("""
        INSERT INTO trade_events (trade_id, event_type, actor_type, old_status, new_status, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trade_id, event_type, actor_type, old_status, new_status, 
          json.dumps(metadata), datetime.now(timezone.utc).isoformat()))


# ------------------------------------------------------------------
# SINGLE STATE-TRANSITION AUTHORITY
# ------------------------------------------------------------------
def transition_trade(
    trade_id: int,
    target_status: TradeStatus,
    actor: ActorType,
    metadata: Optional[dict] = None,
    require_approval_hash: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """
    SINGLE SOURCE OF TRUTH for all trade state changes.
    Enforces: legality, actor auth, hash match, atomicity, idempotency.
    
    Args:
        trade_id: ID of the trade to transition
        target_status: Desired new status
        actor: Who is performing this transition
        metadata: Additional data to store with the transition
        require_approval_hash: Required hash for EXECUTED transitions
        conn: Optional existing database connection (for atomic transactions)
    
    Returns:
        Dict with status, trade_id, message, and transition details
    """
    metadata = metadata or {}
    own_connection = False
    
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        own_connection = True
        conn.execute("BEGIN TRANSACTION")
    
    try:
        cursor = conn.cursor()
        
        # Idempotency
        if _is_already_in_state(conn, trade_id, target_status):
            if own_connection:
                conn.commit()
                conn.close()
            return {
                "status": "SUCCESS",
                "trade_id": trade_id,
                "message": f"Trade already in {target_status.value}. Idempotent.",
                "idempotent": True,
                "new_status": target_status.value
            }
        
        # Fetch current state
        cursor.execute("""
            SELECT id, status, proposal_hash, entry_price, quantity, stop_loss, symbol, side
            FROM trades WHERE id = ?
        """, (trade_id,))
        row = cursor.fetchone()
        if not row:
            if own_connection:
                conn.rollback()
                conn.close()
            return {
                "status": "ERROR", 
                "trade_id": trade_id, 
                "message": f"Trade {trade_id} not found."
            }
        
        current_status_str = row[1]
        try:
            current_status = TradeStatus(current_status_str)
        except ValueError:
            if own_connection:
                conn.rollback()
                conn.close()
            return {
                "status": "ERROR",
                "trade_id": trade_id,
                "message": f"Invalid current status: {current_status_str}"
            }
        
        stored_hash = row[2]
        
        # Validate transition legality
        if target_status not in ALLOWED_TRANSITIONS.get(current_status, []):
            allowed = [s.value for s in ALLOWED_TRANSITIONS.get(current_status, [])]
            if own_connection:
                conn.rollback()
                conn.close()
            return {
                "status": "REJECTED",
                "trade_id": trade_id,
                "message": (
                    f"ILLEGAL: {current_status.value} → {target_status.value}. "
                    f"Allowed: {allowed}"
                ),
                "current_status": current_status.value,
                "target_status": target_status.value,
                "allowed_transitions": allowed
            }
        
        # Validate actor
        authorized = AUTHORIZED_ACTORS.get(target_status, [])
        if actor not in authorized:
            if own_connection:
                conn.rollback()
                conn.close()
            return {
                "status": "REJECTED",
                "trade_id": trade_id,
                "message": f"UNAUTHORIZED: {actor.value} cannot perform {target_status.value}.",
                "authorized_actors": [a.value for a in authorized],
                "actor": actor.value
            }
        
        # Special: EXECUTED requires approval hash
        if target_status == TradeStatus.EXECUTED:
            if not require_approval_hash:
                if own_connection:
                    conn.rollback()
                    conn.close()
                return {
                    "status": "REJECTED",
                    "trade_id": trade_id,
                    "message": "EXECUTION BLOCKED: Approval hash required."
                }
            if stored_hash and require_approval_hash != stored_hash:
                if own_connection:
                    conn.rollback()
                    conn.close()
                return {
                    "status": "REJECTED",
                    "trade_id": trade_id,
                    "message": "EXECUTION BLOCKED: Hash mismatch. Trade may be tampered.",
                    "stored_hash": stored_hash,
                    "provided_hash": require_approval_hash
                }
            if current_status != TradeStatus.APPROVED:
                if own_connection:
                    conn.rollback()
                    conn.close()
                return {
                    "status": "REJECTED",
                    "trade_id": trade_id,
                    "message": f"EXECUTION BLOCKED: Trade must be APPROVED, but is {current_status.value}."
                }
        
        # Build the atomic UPDATE
        set_clauses = [
            "status = ?",
            "last_modified_at = ?",
            "last_modified_by = ?"
        ]
        params = [target_status.value, datetime.now(timezone.utc).isoformat(), actor.value]

        # Add metadata fields if they exist in the table
        if metadata:
            # Get table columns
            cursor.execute("PRAGMA table_info(trades)")
            columns = {row[1] for row in cursor.fetchall()}
            
            # Safe metadata fields to update
            safe_metadata_fields = ["execution_price", "executed_by", "approved_by", "rejection_reason"]
            for key in safe_metadata_fields:
                if key in metadata and key in columns:
                    set_clauses.append(f"{key} = ?")
                    params.append(metadata[key])
        
        # Add status-specific timestamp
        status_col_map = {
            TradeStatus.PROPOSED: "proposed_at",
            TradeStatus.RISK_CHECKED: "risk_checked_at",
            TradeStatus.AWAITING_APPROVAL: "approval_requested_at",
            TradeStatus.APPROVED: "approved_at",
            TradeStatus.EXECUTED: "executed_at",
            TradeStatus.CLOSED: "closed_at",
        }
        if target_status in status_col_map:
            set_clauses.append(f"{status_col_map[target_status]} = ?")
            params.append(datetime.now(timezone.utc).isoformat())
        
        # Store metadata as JSON if provided
        if metadata:
            set_clauses.append("transition_metadata = ?")
            params.append(json.dumps(metadata))
        
        # Add old status for WHERE clause
        params.append(trade_id)
        params.append(current_status.value)
        
        query = f"""
            UPDATE trades 
            SET {', '.join(set_clauses)}
            WHERE id = ? AND status = ?
        """
        
        cursor.execute(query, params)
        affected = cursor.rowcount
        
        if affected == 0:
            if own_connection:
                conn.rollback()
                conn.close()
            return {
                "status": "REJECTED",
                "trade_id": trade_id,
                "message": "Concurrent modification detected. Please retry."
            }
        
        # 🔒 CRITICAL: Insert audit event BEFORE commit, using the same connection.
        # This ensures both UPDATE and INSERT are in the same transaction.
        _log_event(
            conn,
            trade_id,
            "STATE_TRANSITION",
            actor.value,
            current_status.value,
            target_status.value,
            metadata
        )
        
        if own_connection:
            conn.commit()
            conn.close()
        # If external connection, do NOT commit or close – caller handles it.
        
        return {
            "status": "SUCCESS",
            "trade_id": trade_id,
            "new_status": target_status.value,
            "old_status": current_status.value,
            "actor": actor.value,
            "message": f"Trade {trade_id} → {target_status.value} by {actor.value}.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except sqlite3.Error as e:
        if own_connection:
            conn.rollback()
            conn.close()
        return {
            "status": "ERROR",
            "trade_id": trade_id,
            "message": f"Database error during state transition: {str(e)}"
        }
    except Exception as e:
        if own_connection:
            conn.rollback()
            conn.close()
        return {
            "status": "ERROR",
            "trade_id": trade_id,
            "message": f"State transition failed: {str(e)}"
        }


# ------------------------------------------------------------------
# HELPER: Get transition history for a trade
# ------------------------------------------------------------------
def get_transition_history(trade_id: int, limit: int = 50) -> Dict[str, Any]:
    """
    Get the audit history for a specific trade.
    
    Args:
        trade_id: ID of the trade
        limit: Maximum number of events to return
    
    Returns:
        Dict with trade_id and list of events
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        _ensure_audit_table(conn)
        
        cursor.execute("""
            SELECT id, event_type, actor_type, old_status, new_status, metadata, created_at
            FROM trade_events
            WHERE trade_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (trade_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            try:
                metadata = json.loads(row[5]) if row[5] else {}
            except:
                metadata = {}
            events.append({
                "id": row[0],
                "event_type": row[1],
                "actor": row[2],
                "old_status": row[3],
                "new_status": row[4],
                "metadata": metadata,
                "created_at": row[6]
            })
        
        return {
            "trade_id": trade_id,
            "events": events,
            "count": len(events)
        }
        
    except Exception as e:
        return {
            "trade_id": trade_id,
            "events": [],
            "count": 0,
            "error": str(e)
        }


# ------------------------------------------------------------------
# HELPER: Validate transition is legal
# ------------------------------------------------------------------
def is_transition_legal(current_status: TradeStatus, target_status: TradeStatus) -> bool:
    """Check if a transition is legal."""
    return target_status in ALLOWED_TRANSITIONS.get(current_status, [])


def is_actor_authorized(target_status: TradeStatus, actor: ActorType) -> bool:
    """Check if an actor is authorized for a target status."""
    return actor in AUTHORIZED_ACTORS.get(target_status, [])


# ------------------------------------------------------------------
# HELPER: Get available transitions for a status
# ------------------------------------------------------------------
def get_available_transitions(status: TradeStatus) -> List[str]:
    """Get list of available transitions from a given status."""
    transitions = ALLOWED_TRANSITIONS.get(status, [])
    return [t.value for t in transitions]


def get_authorized_actors(status: TradeStatus) -> List[str]:
    """Get list of authorized actors for a target status."""
    actors = AUTHORIZED_ACTORS.get(status, [])
    return [a.value for a in actors]


# ------------------------------------------------------------------
# SELF-TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("🧪 Testing State Machine...")
    # Test with a sample trade ID (will fail if trade doesn't exist)
    # This is just to demonstrate the API
    print("✅ State Machine loaded successfully")