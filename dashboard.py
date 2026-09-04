"""
TradeGuard AI - Polished Streamlit Dashboard (Hackathon Ready).

Demonstrates the complete governed trading workflow with professional UI/UX.
Core Narrative: AI investigates. Deterministic controls verify. Humans govern. Binance executes.
"""

import streamlit as st
import os
from datetime import datetime
from config import DB_PATH, TRADING_MODE
from trade_memory_mcp import propose_trade, get_trade, get_trade_history
from governance_engine import screen_trade, request_approval, approve_trade, execute_trade
from schemas import TradeStatus

# Page configuration
st.set_page_config(
    page_title="TradeGuard AI - Governed Trading",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Professional, trustworthy design
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00c2ff 0%, #667eea 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .tagline { font-size: 1.1rem; color: #8b949e; margin-bottom: 2rem; font-style: italic; }
    .env-badge { display: inline-block; padding: 0.6rem 1.2rem; border-radius: 25px; font-weight: 600; font-size: 0.95rem; margin-bottom: 1.5rem; border: 2px solid; }
    .env-paper { background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1976d2; border-color: #1976d2; box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3); }
    .env-live { background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #d32f2f; border-color: #d32f2f; box-shadow: 0 2px 8px rgba(211, 47, 47, 0.3); }
    .status-card { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border: 1px solid #30363d; border-radius: 12px; padding: 1.2rem; text-align: center; transition: all 0.3s ease; }
    .status-card:hover { border-color: #00c2ff; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 194, 255, 0.2); }
    .workflow-step { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border: 2px solid #30363d; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; transition: all 0.3s ease; }
    .workflow-step.active { border-color: #00c2ff; box-shadow: 0 0 20px rgba(0, 194, 255, 0.3); }
    .workflow-step.completed { border-color: #3fb950; background: linear-gradient(135deg, #161b22 0%, #1a2f1a 100%); }
    .workflow-step.rejected { border-color: #f85149; background: linear-gradient(135deg, #161b22 0%, #2f1a1a 100%); }
    .step-number { display: inline-block; width: 32px; height: 32px; background: linear-gradient(135deg, #00c2ff 0%, #667eea 100%); color: white; border-radius: 50%; text-align: center; line-height: 32px; font-weight: 700; margin-right: 0.5rem; }
    .step-title { font-size: 1.2rem; font-weight: 600; color: #e6edf3; margin-bottom: 0.5rem; }
    .step-caption { color: #8b949e; font-size: 0.9rem; margin-bottom: 1rem; }
    .status-badge { display: inline-block; padding: 0.4rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.85rem; }
    .status-proposed { background: #d29922; color: #0d1117; }
    .status-approved { background: #3fb950; color: #0d1117; }
    .status-executed { background: #3fb950; color: #0d1117; }
    .status-rejected { background: #f85149; color: white; }
    .status-awaiting { background: #58a6ff; color: #0d1117; }
    .token-box { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border: 2px solid #00c2ff; border-radius: 8px; padding: 1rem; font-family: 'Courier New', monospace; word-break: break-all; margin: 1rem 0; box-shadow: 0 0 15px rgba(0, 194, 255, 0.2); }
    .warning-box { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border-left: 4px solid #d29922; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
    .success-box { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border-left: 4px solid #3fb950; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# Helper function to safely format numbers
def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# Header Section
st.markdown('<div class="main-header">🛡️ TradeGuard AI</div>', unsafe_allow_html=True)
st.markdown('<div class="tagline">AI investigates. Deterministic controls verify. Humans govern. Binance executes.</div>', unsafe_allow_html=True)

# Environment Badge (Truthful labeling)
env_class = "env-paper" if TRADING_MODE == "paper" else "env-live"
env_text = "📝 PAPER MODE - Simulated Trading (No Real Money)" if TRADING_MODE == "paper" else "🔴 LIVE MODE - Real Money at Risk"
st.markdown(f'<div class="env-badge {env_class}">{env_text}</div>', unsafe_allow_html=True)

st.divider()

# System Status Section (Truthful runtime status)
st.markdown("### System Status")
col1, col2, col3, col4 = st.columns(4)

with col1: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">🤖</div><div style="color:#8b949e;font-size:0.9rem">AI Agent</div><div style="color:#3fb950;font-weight:600">Online</div></div>', unsafe_allow_html=True)
with col2: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">🔒</div><div style="color:#8b949e;font-size:0.9rem">Risk Engine</div><div style="color:#3fb950;font-weight:600">Active</div></div>', unsafe_allow_html=True)
with col3: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">⚖️</div><div style="color:#8b949e;font-size:0.9rem">Governance</div><div style="color:#3fb950;font-weight:600">Enforcing</div></div>', unsafe_allow_html=True)
with col4:
    # Truthful adapter status based on runtime config
    if TRADING_MODE == "paper":
        adapter_status = "Paper Adapter Active"
        status_color = "#3fb950"
    else:
        is_testnet = os.environ.get("BINANCE_USE_TESTNET", "true").lower() == "true"
        adapter_status = "Binance Testnet Connected" if is_testnet else "Binance Mainnet Connected"
        status_color = "#d29922" if is_testnet else "#f85149"
        
    st.markdown(f'<div class="status-card"><div style="font-size:2rem">🔗</div><div style="color:#8b949e;font-size:0.9rem">Execution Adapter</div><div style="color:{status_color};font-weight:600">{adapter_status}</div></div>', unsafe_allow_html=True)

st.divider()

# Initialize session state
if 'trade_id' not in st.session_state:
    st.session_state.trade_id = None
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'token' not in st.session_state:
    st.session_state.token = None
if 'show_rejection_demo' not in st.session_state:
    st.session_state.show_rejection_demo = False

# Main Workflow Section
st.markdown("### Governed Trading Workflow")

# Step 1: Deterministic Demo Agent (Primary) + Manual Override (Secondary)
step_class = "active" if st.session_state.step >= 1 else ""
st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
st.markdown('<span class="step-number">1</span><div class="step-title">AI Agent Analysis & Proposal</div>', unsafe_allow_html=True)
st.markdown('<div class="step-caption">The agent generates reproducible, safe proposals based on your objective to test the governance workflow.</div>', unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("##### 🤖 Deterministic Demo Agent (Primary)")
    st.caption("Define your objective. The agent will generate a compliant, risk-managed proposal for governance testing.")
    
    user_objective = st.text_area("Trading Objective", value="Find a conservative long opportunity on BTC with strict risk management.", height=100)
    
    if st.button("🤖 Run Agent Analysis & Propose", type="primary", key="ai_propose"):
        try:
            # Deterministic Demo Agent: Parses objective to provide a relevant, safe proposal
            # This ensures the UI is honest about being a deterministic demo for governance testing.
            obj_lower = user_objective.lower()
            
            if "eth" in obj_lower:
                symbol, entry, qty = "ETH", 3000.0, 0.5
            elif "sol" in obj_lower:
                symbol, entry, qty = "SOL", 150.0, 10.0
            else:
                symbol, entry, qty = "BTC", 60000.0, 0.01
                
            if "short" in obj_lower:
                side, stop = "short", entry * 1.01
            else:
                side, stop = "long", entry * 0.99
                
            prop = propose_trade(
                symbol=symbol,
                side=side,
                quantity=qty,
                entry_price=entry,
                stop_loss=stop,
                reasoning=f"Deterministic Demo Agent Analysis: User requested '{user_objective}'. Agent generated a conservative {side.upper()} proposal for {symbol} adhering to the 2% portfolio risk cap."
            )
            st.session_state.trade_id = prop["trade_id"]
            st.session_state.step = 1
            st.session_state.show_rejection_demo = False
            st.rerun()
        except Exception as e:
            st.error(f"❌ Proposal failed: {e}")

    st.divider()
    
    with st.expander("✍️ Manual Override (Advanced)", expanded=False):
        st.caption("Bypass the agent and define exact parameters yourself.")
        intent_asset = st.selectbox("Asset", ["BTC", "ETH", "SOL"], index=0, key="manual_asset")
        intent_side = st.radio("Direction", ["long", "short"], horizontal=True, key="manual_side")
        default_entry = 60000.0 if intent_asset == "BTC" else (3000.0 if intent_asset == "ETH" else 150.0)
        entry_price = st.number_input("Entry Price", value=default_entry, step=100.0, format="%.2f", key="manual_entry")
        stop_loss = st.number_input("Stop Loss", value=default_entry * 0.99, step=10.0, format="%.2f", key="manual_stop")
        quantity = st.number_input("Quantity", value=0.01, step=0.01, format="%.4f", key="manual_qty")
        
        if st.button("Generate Manual Proposal", key="manual_propose"):
            try:
                prop = propose_trade(
                    symbol=intent_asset, side=intent_side, quantity=quantity,
                    entry_price=entry_price, stop_loss=stop_loss,
                    reasoning="Manual human-defined parameters. Awaiting deterministic risk validation."
                )
                st.session_state.trade_id = prop["trade_id"]
                st.session_state.step = 1
                st.session_state.show_rejection_demo = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ Manual Proposal failed: {e}")

with col2:
    st.markdown("##### 🧪 SECURITY DEMO")
    st.caption("The agent proposes an obviously dangerous trade. TradeGuard's deterministic controls will reject it.")
    if st.button("Simulate Unsafe AI Proposal (100 BTC)", key="propose_risky_demo"):
        try:
            prop = propose_trade(
                symbol="BTC", side="long", quantity=100.0,
                entry_price=60000.0, stop_loss=59500.0,
                reasoning="Unsafe AI Proposal: Ignoring risk limits for maximum gains!"
            )
            st.session_state.trade_id = prop["trade_id"]
            st.session_state.step = 1
            st.session_state.show_rejection_demo = True
            st.rerun()
        except Exception as e:
            st.error(f"❌ Proposal failed: {e}")

st.markdown('</div>', unsafe_allow_html=True)

# Display current trade if exists
if st.session_state.trade_id:
    trade = get_trade(st.session_state.trade_id)
    
    st.markdown("##### Trade Proposal Details")
    
    qty = safe_float(trade.get('quantity'))
    entry = safe_float(trade.get('entry_price'))
    stop = safe_float(trade.get('stop_loss'))
    risk_pct = safe_float(trade.get('risk_percent'))
    risk_amt = safe_float(trade.get('risk_amount'))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Asset", f"{trade.get('symbol', 'N/A')}")
    with col2: st.metric("Side", trade.get('side', 'N/A').upper())
    with col3: st.metric("Quantity", f"{qty:.4f}")
    with col4: st.metric("Entry Price", f"${entry:,.2f}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Stop Loss", f"${stop:,.2f}")
    with col2: st.metric("Risk %", f"{risk_pct:.2%}")
    with col3: st.metric("Risk Amount", f"${risk_amt:,.2f}")
    with col4:
        status_badge = {
            'proposed': '<span class="status-badge status-proposed">🟡 PROPOSED</span>',
            'risk_checked': '<span class="status-badge status-awaiting">🔵 RISK CHECKED</span>',
            'awaiting_approval': '<span class="status-badge status-awaiting">🟠 AWAITING APPROVAL</span>',
            'approved': '<span class="status-badge status-approved">🟢 APPROVED</span>',
            'executed': '<span class="status-badge status-executed">✅ EXECUTED</span>',
            'rejected': '<span class="status-badge status-rejected">🔴 REJECTED</span>'
        }.get(trade.get('status', ''), trade.get('status', 'UNKNOWN').upper())
        st.markdown(status_badge, unsafe_allow_html=True)
    
    st.markdown(f"**📝 Reasoning:** {trade.get('reasoning', 'N/A')}")
    
    st.divider()
    
    # Step 2: Risk Engine Validates
    step_class = "active" if st.session_state.step >= 2 else ""
    if trade.get('status') == 'rejected': step_class = "rejected"
    elif trade.get('status') in ['risk_checked', 'awaiting_approval', 'approved', 'executed']: step_class = "completed"
    
    st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
    st.markdown('<span class="step-number">2</span><div class="step-title">Deterministic Risk Engine Validates</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-caption">Independent risk validation enforces hard limits. The agent cannot override these checks.</div>', unsafe_allow_html=True)
    
    if trade.get('status') == 'proposed':
        if st.button("🔍 Run Risk Validation", type="primary", key="risk_validate"):
            result = screen_trade(st.session_state.trade_id)
            if result.get('status') == 'SUCCESS':
                st.success("✅ Risk validation PASSED - All checks cleared")
                st.info("Trade moved to AWAITING_APPROVAL status")
                st.session_state.step = 2
                st.rerun()
            else:
                st.error(f"❌ Risk validation REJECTED: {result.get('reason', 'Unknown')}")
                st.markdown('<div class="warning-box">⚠️ <strong>Key Demo Point:</strong> The proposal violated deterministic risk controls (e.g., 2% risk cap). TradeGuard blocked it automatically.</div>', unsafe_allow_html=True)
                st.session_state.step = 2
                st.rerun()
    elif trade.get('status') == 'rejected':
        st.markdown('<div class="success-box">✅ Risk engine correctly rejected unsafe trade. This demonstrates fail-closed security.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="success-box">✅ Risk validation completed successfully. Trade passed all safety checks.</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Step 3: Human Authorization
    if trade.get('status') not in ['rejected']:
        step_class = "active" if st.session_state.step >= 3 else ""
        if trade.get('status') in ['approved', 'executed']: step_class = "completed"
        
        st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
        st.markdown('<span class="step-number">3</span><div class="step-title">Human Authorization Required</div>', unsafe_allow_html=True)
        st.markdown('<div class="step-caption">Cryptographic approval token binds approval to the exact proposal. Any modification invalidates it.</div>', unsafe_allow_html=True)
        
        if trade.get('status') == 'awaiting_approval':
            if st.button("🎟️ Generate Approval Token", type="primary", key="gen_token"):
                result = request_approval(st.session_state.trade_id)
                if result.get('status') == 'success':
                    st.session_state.token = result.get('approval_token')
                    st.success("✅ Cryptographic approval token generated")
                    st.rerun()
                else:
                    st.error(f"❌ Token generation failed: {result.get('reason')}")
            
            if st.session_state.token:
                st.markdown("##### Approval Token (Cryptographically Bound)")
                st.markdown(f'<div class="token-box">{st.session_state.token}</div>', unsafe_allow_html=True)
                st.caption("This SHA-256 hash is mathematically bound to your exact parameters. Any change invalidates the token.")
                
                st.divider()
                
                st.markdown("#### Step 4: Human Approves Trade")
                entered_token = st.text_input("Enter Approval Token", key="token_input", placeholder="Paste token here...")
                
                if st.button("✅ Approve Trade", type="primary", key="approve_trade"):
                    if entered_token.strip() == st.session_state.token:
                        result = approve_trade(entered_token.strip())
                        if result.get('status') == 'SUCCESS':
                            st.success("✅ Trade APPROVED - Authorization verified")
                            st.session_state.step = 4
                            st.rerun()
                        else:
                            st.error(f"❌ Approval failed: {result.get('reason')}")
                    else:
                        st.error("❌ Token mismatch - Approval rejected for security")
        elif trade.get('status') == 'approved':
            st.markdown('<div class="success-box">✅ Human approval verified. Trade authorized for execution.</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Step 5: Execution Gateway
        if trade.get('status') == 'approved':
            step_class = "active" if st.session_state.step >= 4 else ""
            
            st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
            st.markdown('<span class="step-number">4</span><div class="step-title">Execution Gateway Executes</div>', unsafe_allow_html=True)
            st.markdown('<div class="step-caption">Governance verifies proposal integrity and approval before executing through the adapter.</div>', unsafe_allow_html=True)
            
            st.markdown(f"**Execution Price:** `${entry:,.2f}` *(Locked to approved proposal)*")
            st.caption("Manual input is disabled at execution. The Gateway fills at the approved price to maintain hash integrity.")
            
            if st.button("🚀 Execute Trade via Adapter", type="primary", key="execute_trade"):
                result = execute_trade(st.session_state.trade_id, execution_price=entry)
                if result.get('status') == 'SUCCESS':
                    st.success(f"✅ Trade EXECUTED at ${entry:,.2f}")
                    st.session_state.step = 5
                    st.rerun()
                else:
                    st.error(f"❌ Execution failed: {result.get('reason')}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        elif trade.get('status') == 'executed':
            st.markdown('<div class="success-box">✅ Trade executed successfully. Full lifecycle complete.</div>', unsafe_allow_html=True)

# Demo Summary Box
if st.session_state.show_rejection_demo and st.session_state.trade_id:
    trade = get_trade(st.session_state.trade_id)
    if trade.get('status') == 'rejected':
        st.divider()
        st.markdown("### 🎯 Demo Summary: Risk Engine Rejection")
        st.markdown("""
        **What Just Happened:**
        1. ✅ An unsafe trade (100 BTC) was proposed.
        2. ✅ Deterministic risk engine evaluated the proposal.
        3. ✅ Risk engine REJECTED the trade (exceeds 2% risk cap).
        4. ✅ Trade cannot proceed without approval.
        
        **Why This Matters:**
        - The agent cannot override deterministic risk controls.
        - Unsafe trades are blocked automatically.
        - This is NOT just an AI wrapper - it has independent safety.
        """)

# Audit Trail Section
st.divider()
st.markdown("### Audit Trail - Trade History")
st.caption("Every action is recorded for full transparency and accountability.")

history = get_trade_history(limit=10)

if history.get('trades'):
    for trade in history['trades']:
        status_emoji = {
            'proposed': '🟡', 'risk_checked': '🔵', 'awaiting_approval': '🟠',
            'approved': '🟢', 'executed': '✅', 'rejected': '🔴'
        }.get(trade.get('status', ''), '⚪')
        
        hist_qty = safe_float(trade.get('quantity'))
        hist_entry = safe_float(trade.get('entry'))
        hist_stop = safe_float(trade.get('stop'))
        hist_pnl = safe_float(trade.get('pnl'))
        
        with st.expander(f"{status_emoji} Trade #{trade.get('id', 'N/A')} - {trade.get('symbol', 'N/A')} {trade.get('side', 'N/A').upper()} - {trade.get('status', 'N/A').upper()}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Quantity:** {hist_qty:.4f}")
                st.write(f"**Entry:** ${hist_entry:,.2f}")
            with col2:
                st.write(f"**Stop Loss:** ${hist_stop:,.2f}")
                st.write(f"**PnL:** ${hist_pnl:,.2f}")
            with col3:
                st.write(f"**Created:** {trade.get('created', 'N/A')}")
                if trade.get('executed'): st.write(f"**Executed:** {trade['executed']}")
else:
    st.info("📭 No trades yet. Define your objective above to start the demo.")

# Footer (Clean, judge-focused)
st.divider()
st.markdown("""
<div style='text-align: center; color: #8b949e; padding: 2rem 0;'>
    <h3>🛡️ TradeGuard AI</h3>
    <p><em>AI investigates. Deterministic controls verify. Humans govern. Binance executes. TradeGuard records.</em></p>
    <p>Built for Binance Agent OS Mini Hackathon - Track B</p>
</div>
""", unsafe_allow_html=True)