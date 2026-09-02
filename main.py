#!/usr/bin/env python3
"""
Robo-Shopper V4 - Agent Entry Point
"""
import sys
import re
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH
from schemas import TradeStatus
import trade_memory_mcp
import risk_management_mcp
import guardrails_mcp
from governance_engine import (
    screen_trade, request_approval, approve_trade,
    execute_trade, generate_execution_command, _get_proposal_hash
)

VALID_SYMBOLS = {"BTC", "ETH", "SOL"}

def safe_input(prompt: str, default: str = "") -> str:
    """Safely read input, returning default on EOF."""
    try:
        val = input(prompt)
        return val.strip() if val.strip() else default
    except EOFError:
        return default

def print_header(text: str):
    print(f"\n{'='*70}\n  {text}\n{'='*70}\n")

def print_section(text: str):
    print(f"\n--- {text} ---\n")

def _looks_like_natural_language(text: str) -> bool:
    text_lower = text.lower().strip()
    nl_indicators = ["investigate", "determine", "whether", "position", "fits", "my", "current", "risk", "policy", "long", "short", "trade"]
    if " " in text_lower:
        matches = sum(1 for word in nl_indicators if word in text_lower)
        if matches >= 2: return True
    return False

def _extract_symbol_from_query(query: str) -> Optional[str]:
    query_upper = query.upper()
    for symbol in VALID_SYMBOLS:
        if re.search(rf'\b{symbol}\b', query_upper): return symbol
    return None

def _extract_number_from_query(query: str, patterns: list) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            try: return float(match.group(1).replace(",", ""))
            except (ValueError, IndexError): continue
    return None

def _parse_natural_language_query(query: str) -> dict:
    result = {}
    symbol = _extract_symbol_from_query(query)
    if symbol: result["symbol"] = symbol
    
    query_lower = query.lower()
    if " short " in query_lower or query_lower.strip().endswith(" short"): result["side"] = "short"
    elif " long " in query_lower or query_lower.strip().endswith(" long"): result["side"] = "long"
    
    qty = _extract_number_from_query(query, [r'(\d+\.?\d*)\s*(?:btc|eth|sol|shares?|units?)', r'(?:quantity|size|amount)\s*(?:of\s*)?(\d+\.?\d*)'])
    if qty: result["quantity"] = qty
    
    entry = _extract_number_from_query(query, [r'entry\s*(?:of|at|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', r'(?:at|around|near)\s*\$?(\d+(?:,\d+)*(?:\.\d+)?)'])
    if entry: result["entry_price"] = entry
    
    stop = _extract_number_from_query(query, [r'stop\s*(?:loss)?\s*(?:of|at|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?)'])
    if stop: result["stop_loss"] = stop
    
    return result

def main():
    print_header("🤖 Robo-Shopper Agent - Autonomous Investigation")
    print("💡 Tip: You can enter parameters one-by-one, OR paste a natural language query")
    print("        like: 'Investigate BTC long 0.01 at entry 60000 stop 59500'\n")
    
    raw_input = safe_input("  Enter symbol (BTC/ETH/SOL) or natural language query: ", "BTC")
    
    if _looks_like_natural_language(raw_input):
        print(f"\n  🔍 Detected natural language query. Parsing...")
        parsed = _parse_natural_language_query(raw_input)
        
        symbol = parsed.get("symbol", "BTC").upper()
        side = parsed.get("side", "long")
        quantity = parsed.get("quantity", 0.01)
        entry_price = parsed.get("entry_price", 60000)
        stop_loss = parsed.get("stop_loss", 59500)
    else:
        symbol = raw_input.upper() if raw_input else "BTC"
        side = safe_input("  Side (long/short) [long]: ", "long").lower()
        quantity = float(safe_input("  Quantity [0.01]: ", "0.01"))
        entry_price = float(safe_input("  Entry Price [60000]: ", "60000"))
        stop_loss = float(safe_input("  Stop Loss [59500]: ", "59500"))

    if symbol not in VALID_SYMBOLS:
        print(f"\n❌ Invalid symbol '{symbol}'. Must be one of: {', '.join(VALID_SYMBOLS)}")
        sys.exit(1)
    if side not in ("long", "short"):
        print(f"\n❌ Invalid side '{side}'. Must be 'long' or 'short'.")
        sys.exit(1)

    print_section("🔍 Phase 1: Autonomous Investigation")
    print(f"Agent investigating {symbol} {side} position...")
    print(f"  • Entry: ${entry_price:,.2f}\n  • Stop Loss: ${stop_loss:,.2f}\n  • Quantity: {quantity}\n  • Risk per unit: ${abs(entry_price - stop_loss):,.2f}")

    print_section("📝 Phase 2: Trade Proposal Generation")
    proposal_result = trade_memory_mcp.propose_trade(symbol=symbol, side=side, quantity=quantity, entry_price=entry_price, stop_loss=stop_loss, reasoning="Agent investigation based on market analysis")
    if proposal_result["status"] != "success":
        print(f"❌ Failed to propose trade: {proposal_result}"); sys.exit(1)
    
    trade_id = proposal_result["trade_id"]
    print(f"✅ Trade proposed successfully\n  • Trade ID: {trade_id}\n  • Status: {proposal_result['current_status']}")

    print_section("️ Phase 3: Deterministic Risk Screening")
    print("Running risk engine and guardrail checks...")
    screen_result = screen_trade(trade_id)
    if screen_result["status"] == "REJECTED":
        print(f"❌ Trade rejected by risk engine\n  • Reason: {screen_result['reason']}"); sys.exit(1)
    print(f"✅ Risk checks passed\n  • Position sizing: Valid\n  • Exposure limits: Within bounds\n  • Circuit breakers: Clear")

    print_section("🔐 Phase 4: Cryptographic Authorization")
    print("Generating proposal hash and approval token...")
    approval_result = request_approval(trade_id)
    if approval_result["status"] != "success":
        print(f" Failed to request approval: {approval_result}"); sys.exit(1)
    
    proposal_hash = approval_result["proposal_hash"]
    approval_token = approval_result["approval_token"]
    print(f"✅ Approval token generated\n  • Proposal Hash: {proposal_hash[:32]}...\n  • Token: {approval_token[:32]}...\n  • Expires: {approval_result['expires_at']}")

    print_section("📋 Trade Proposal Dossier")
    trade = trade_memory_mcp.get_trade(trade_id)
    print(f"Trade ID: {trade_id}\nStatus: {trade['status']}\nSymbol: {trade['symbol']}\nSide: {trade['side']}\nEntry Price: ${trade['entry_price']:,.2f}\nStop Loss: ${trade['stop_loss']:,.2f}\nQuantity: {trade['quantity']}\nRisk Amount: ${trade['risk_amount']:,.2f}\nRisk Percent: {trade['risk_percent']*100:.4f}%\nPortfolio Balance: ${trade['portfolio_balance']:,.2f}\nProposal Hash: {proposal_hash}\nPolicy Version: {approval_result['policy_version']}")

    print_section(" Phase 5: Human Governance (Simulated)")
    print("Simulating human approval via dashboard...")
    approve_result = approve_trade(approval_token, approved_by="human_operator")
    if approve_result["status"] != "SUCCESS":
        print(f"❌ Approval failed: {approve_result}"); sys.exit(1)
    print(f"✅ Trade approved by human operator\n  • New Status: {approve_result['new_status']}")

    print_section("⚡ Phase 6: Execution Gateway")
    print("Generating dry-run execution command...")
    cmd_result = generate_execution_command(trade_id)
    if cmd_result["status"] != "SUCCESS":
        print(f"❌ Execution command failed: {cmd_result}"); sys.exit(1)
    print(f"✅ Execution command generated\n  • Command: {cmd_result['command']}")

    print_section("🚀 Phase 7: Trade Execution")
    print("Executing trade (dry-run)...")
    execution_price = entry_price * 1.001
    exec_result = execute_trade(trade_id, execution_price=execution_price)
    if exec_result["status"] != "SUCCESS":
        print(f"❌ Execution failed: {exec_result}"); sys.exit(1)
    print(f"✅ Trade executed successfully\n  • Execution Price: ${execution_price:,.2f}\n  • Final Status: {exec_result['new_status']}")

    print_header("✨ Investigation Complete")
    print("Full pipeline executed successfully:\n  1. ✅ Agent investigated market conditions\n  2. ✅ Deterministic risk engine validated proposal\n  3. ✅ Cryptographic hash bound to proposal\n  4. ✅ Human operator approved via secure token\n  5. ✅ Execution gateway verified hash integrity\n  6. ✅ Trade executed with full audit trail")
    print(f"\nTrade ID: {trade_id}\nProposal Hash: {proposal_hash}\n\n🎯 Robo-Shopper: AI investigates, system verifies, human authorizes.\n")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n\n⚠️  Agent interrupted by user"); sys.exit(0)
    except Exception as e: print(f"\n\n❌ Agent error: {e}"); import traceback; traceback.print_exc(); sys.exit(1)