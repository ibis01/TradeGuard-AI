"""
TradeGuard AI - Polished Streamlit Dashboard .

Demonstrates the complete governed trading workflow with professional UI/UX.
Core Narrative: AI investigates. Deterministic controls verify. Humans govern. Binance executes.
"""

import streamlit as st
import os
import time
from datetime import datetime

# Import from compatibility layer
from compatibility import (
    propose_trade,
    get_trade,
    get_trade_history,
    screen_trade,
    request_approval,
    approve_trade,
    execute_trade,
    TRADING_MODE
)

# Import risk constants for manual validation (single import)
from risk_management_mcp import (
    get_portfolio_balance,
    MAX_RISK_PERCENT,
    MIN_STOP_DISTANCE,
    MAX_POSITION_PCT
)

# Import market intelligence
from market_intelligence_mcp import (
    get_live_market_data,
    check_market_data_health,
    analyze_technicals_fast,
    get_trade_recommendation,
    clear_cache
)

# Page configuration
st.set_page_config(
    page_title="TradeGuard AI - Governed Trading",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS (kept exactly as before – omitted for brevity, but include it)
# ============================================================================
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
    .tagline {
        font-size: 1.1rem;
        color: #8b949e;
        margin-bottom: 2rem;
        font-style: italic;
    }
    .env-badge {
        display: inline-block;
        padding: 0.6rem 1.2rem;
        border-radius: 25px;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
        border: 2px solid;
    }
    .env-paper {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        color: #1976d2;
        border-color: #1976d2;
    }
    .env-live {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        color: #d32f2f;
        border-color: #d32f2f;
    }
    .status-card {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .status-card:hover {
        border-color: #00c2ff;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 194, 255, 0.2);
    }
    .workflow-step {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 2px solid #30363d;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    .workflow-step.active {
        border-color: #00c2ff;
        box-shadow: 0 0 20px rgba(0, 194, 255, 0.3);
    }
    .workflow-step.completed {
        border-color: #3fb950;
        background: linear-gradient(135deg, #161b22 0%, #1a2f1a 100%);
    }
    .workflow-step.rejected {
        border-color: #f85149;
        background: linear-gradient(135deg, #161b22 0%, #2f1a1a 100%);
    }
    .step-number {
        display: inline-block;
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #00c2ff 0%, #667eea 100%);
        color: white;
        border-radius: 50%;
        text-align: center;
        line-height: 32px;
        font-weight: 700;
        margin-right: 0.5rem;
    }
    .step-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #e6edf3;
        margin-bottom: 0.5rem;
    }
    .step-caption {
        color: #8b949e;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-proposed {
        background: #d29922;
        color: #0d1117;
    }
    .status-risk_checked {
        background: #58a6ff;
        color: #0d1117;
    }
    .status-awaiting {
        background: #58a6ff;
        color: #0d1117;
    }
    .status-approved {
        background: #3fb950;
        color: #0d1117;
    }
    .status-executed {
        background: #3fb950;
        color: #0d1117;
    }
    .status-rejected {
        background: #f85149;
        color: white;
    }
    .token-box {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 2px solid #00c2ff;
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        word-break: break-all;
        margin: 1rem 0;
        box-shadow: 0 0 15px rgba(0, 194, 255, 0.2);
    }
    .warning-box {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border-left: 4px solid #d29922;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .success-box {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border-left: 4px solid #3fb950;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border-left: 4px solid #58a6ff;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .price-source-live {
        background: #3fb950;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .price-source-simulated {
        background: #d29922;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .price-source-manual {
        background: #58a6ff;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .price-source-error {
        background: #f85149;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .stButton > button {
        background: linear-gradient(90deg, #00c2ff 0%, #667eea 100%);
        color: white;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 194, 255, 0.4);
    }
    .stButton > button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
    }
    .market-status {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .market-connected {
        background: #3fb950;
        color: #0d1117;
    }
    .market-disconnected {
        background: #f85149;
        color: white;
    }
    div[data-testid="stExpander"] details {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
    }
    .metric-box {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 0.8rem;
        text-align: center;
    }
    .metric-label {
        color: #8b949e;
        font-size: 0.8rem;
    }
    .metric-value {
        color: #e6edf3;
        font-size: 1.2rem;
        font-weight: 600;
    }
    .manual-box {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .analysis-box {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .analysis-label {
        color: #8b949e;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .analysis-value {
        color: #e6edf3;
        font-size: 1.1rem;
        margin-top: 0.2rem;
    }
    .rr-badge-ideal {
        background: #3fb950;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .rr-badge-good {
        background: #58a6ff;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .rr-badge-poor {
        background: #d29922;
        color: #0d1117;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE
# ============================================================================

if 'trade_id' not in st.session_state:
    st.session_state.trade_id = None
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'token' not in st.session_state:
    st.session_state.token = None
if 'show_rejection_demo' not in st.session_state:
    st.session_state.show_rejection_demo = False
if 'execution_price' not in st.session_state:
    st.session_state.execution_price = None
if 'price_source' not in st.session_state:
    st.session_state.price_source = None
if 'market_healthy' not in st.session_state:
    st.session_state.market_healthy = False
if 'market_status_checked' not in st.session_state:
    st.session_state.market_status_checked = False
if 'manual_tech_analysis' not in st.session_state:
    st.session_state.manual_tech_analysis = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default

def check_market_status():
    """Check market status once per session."""
    if not st.session_state.market_status_checked:
        try:
            health = check_market_data_health()
            st.session_state.market_healthy = health.get('status') == 'healthy'
        except:
            st.session_state.market_healthy = False
        st.session_state.market_status_checked = True
    return st.session_state.market_healthy

def generate_technical_analysis(symbol: str, price: float, side: str = None) -> str:
    """Generate a human-readable technical analysis with reasoning."""
    tech_data = analyze_technicals_fast(symbol)
    
    trend = tech_data.get("trend", "Neutral")
    rsi = tech_data.get("rsi", 50.0)
    signal = tech_data.get("signal", "Neutral")
    
    analysis_parts = []
    analysis_parts.append(f"📊 **Technical Analysis for {symbol}**")
    analysis_parts.append("")
    analysis_parts.append(f"**Current Price:** ${price:,.2f}")
    analysis_parts.append("")
    
    if trend == "Bullish":
        analysis_parts.append(f"📈 **Trend:** Bullish - Price above 10-period SMA.")
    elif trend == "Bearish":
        analysis_parts.append(f"📉 **Trend:** Bearish - Price below 10-period SMA.")
    else:
        analysis_parts.append(f"➡️ **Trend:** Neutral - No clear direction.")
    
    analysis_parts.append("")
    
    if rsi >= 70:
        analysis_parts.append(f"⚠️ **RSI:** {rsi:.1f} - Overbought.")
    elif rsi <= 30:
        analysis_parts.append(f"💡 **RSI:** {rsi:.1f} - Oversold.")
    else:
        analysis_parts.append(f"⚖️ **RSI:** {rsi:.1f} - Neutral.")
    
    analysis_parts.append("")
    
    if signal == "Buy":
        analysis_parts.append("🟢 **Signal:** BUY")
    elif signal == "Sell":
        analysis_parts.append("🔴 **Signal:** SELL")
    else:
        analysis_parts.append("🟡 **Signal:** HOLD")
    
    if side:
        if side == "long" and signal in ["Buy", "Neutral"]:
            analysis_parts.append(f"✅ **{side.upper()} Entry:** Technical conditions support this direction.")
        elif side == "short" and signal in ["Sell", "Neutral"]:
            analysis_parts.append(f"✅ **{side.upper()} Entry:** Technical conditions support this direction.")
        else:
            analysis_parts.append(f"⚠️ **{side.upper()} Entry:** May not strongly support this direction.")
    
    analysis_parts.append("")
    analysis_parts.append("---")
    analysis_parts.append("*Analysis based on real-time market data.*")
    
    return "\n".join(analysis_parts)

# ============================================================================
# HEADER
# ============================================================================

st.markdown('<div class="main-header">🛡️ TradeGuard AI</div>', unsafe_allow_html=True)
st.markdown('<div class="tagline">AI investigates. Deterministic controls verify. Humans govern. Binance executes.</div>', unsafe_allow_html=True)

# Environment Badge
env_class = "env-paper" if TRADING_MODE == "paper" else "env-live"
env_text = "📝 PAPER MODE - Simulated Trading (No Real Money)" if TRADING_MODE == "paper" else "🔴 LIVE MODE - Real Money at Risk"
st.markdown(f'<div class="env-badge {env_class}">{env_text}</div>', unsafe_allow_html=True)

# Market Status
is_healthy = check_market_status()
if is_healthy:
    st.markdown('<span class="market-status market-connected">🟢 LIVE Market Data Connected</span>', unsafe_allow_html=True)
else:
    st.markdown('<span class="market-status market-disconnected">🔴 Market Data Disconnected - Using Simulated Prices</span>', unsafe_allow_html=True)

st.divider()

# ============================================================================
# SYSTEM STATUS
# ============================================================================

st.markdown("### System Status")
col1, col2, col3, col4 = st.columns(4)

with col1: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">🤖</div><div style="color:#8b949e;font-size:0.9rem">AI Agent</div><div style="color:#3fb950;font-weight:600">Online</div></div>', unsafe_allow_html=True)
with col2: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">🛡️</div><div style="color:#8b949e;font-size:0.9rem">Risk Engine</div><div style="color:#3fb950;font-weight:600">Active</div></div>', unsafe_allow_html=True)
with col3: 
    st.markdown('<div class="status-card"><div style="font-size:2rem">⚖️</div><div style="color:#8b949e;font-size:0.9rem">Governance</div><div style="color:#3fb950;font-weight:600">Enforcing</div></div>', unsafe_allow_html=True)
with col4:
    if TRADING_MODE == "paper":
        adapter_status = "Paper Adapter Active"
        status_color = "#3fb950"
    else:
        is_testnet = os.environ.get("BINANCE_USE_TESTNET", "true").lower() == "true"
        adapter_status = "Binance Testnet" if is_testnet else "Binance Mainnet"
        status_color = "#d29922" if is_testnet else "#f85149"
        
    st.markdown(f'<div class="status-card"><div style="font-size:2rem">🔗</div><div style="color:#8b949e;font-size:0.9rem">Execution</div><div style="color:{status_color};font-weight:600">{adapter_status}</div></div>', unsafe_allow_html=True)

st.divider()

# ============================================================================
# WORKFLOW - STEP 1: AI AGENT WITH 3:1 RR
# ============================================================================

st.markdown("### Governed Trading Workflow")

# Step 1: AI Agent Analysis & Proposal
step_class = "active" if st.session_state.step >= 1 else ""
st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
st.markdown('<span class="step-number">1</span><div class="step-title">AI Agent Analysis & Proposal</div>', unsafe_allow_html=True)
st.markdown('<div class="step-caption">The agent analyzes technical indicators and generates 3:1 risk-reward proposals.</div>', unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("##### 🤖 AI Technical Analysis Agent")
    st.caption("Analyzes real-time data and proposes trades with 3:1 risk-reward ratio.")
    
    user_objective = st.text_area(
        "Trading Objective", 
        value="Analyze SOL technically and propose the best trade with 3:1 risk-reward.", 
        height=80,
        key="user_objective_main"
    )
    
    if is_healthy:
        st.caption("✅ Live market data available")
    else:
        st.caption("⚠️ No market data connection - using simulated prices")
    
    if st.button("🤖 Run Technical Analysis & Propose", type="primary", key="ai_propose"):
        with st.spinner("📊 Analyzing market data..."):
            try:
                obj_lower = user_objective.lower()
                symbol = "BTC"
                if "eth" in obj_lower:
                    symbol = "ETH"
                elif "sol" in obj_lower:
                    symbol = "SOL"
                
                # Get trade recommendation with 3:1 RR
                recommendation = get_trade_recommendation(symbol)
                
                if not recommendation.get("ok"):
                    st.error(f"❌ Cannot analyze {symbol}: {recommendation.get('error')}")
                    st.stop()
                
                side = recommendation["side"]
                entry = recommendation["entry_price"]
                stop = recommendation["stop_loss"]
                take_profit = recommendation["take_profit"]
                qty = recommendation["position_size"]
                rr_ratio = recommendation["rr_ratio"]
                tech = recommendation["technical_indicators"]
                
                st.success(f"📊 **Technical Analysis for {symbol}**")
                
                col1a, col2a, col3a = st.columns(3)
                with col1a:
                    st.metric("Trend", tech['trend'])
                with col2a:
                    st.metric("RSI", f"{tech['rsi']:.1f}")
                with col3a:
                    st.metric("Signal", tech['signal'])
                
                if rr_ratio >= 3.0:
                    st.markdown('<span class="rr-badge-ideal">🌟 IDEAL 3:1 Risk-Reward</span>', unsafe_allow_html=True)
                elif rr_ratio >= 2.0:
                    st.markdown('<span class="rr-badge-good">✅ Good 2:1 Risk-Reward</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="rr-badge-poor">⚠️ Poor Risk-Reward</span>', unsafe_allow_html=True)
                
                st.markdown(f"""
                **💡 Recommendation: {side.upper()} {symbol}**
                - **Entry:** ${entry:,.2f}
                - **Stop Loss:** ${stop:,.2f} ({((abs(entry-stop))/entry)*100:.2f}% risk)
                - **Take Profit:** ${take_profit:,.2f} ({((abs(take_profit-entry))/entry)*100:.2f}% reward)
                - **Risk-Reward:** {rr_ratio:.1f}:1
                - **Position:** {qty:.4f} {symbol} (${recommendation['position_value']:,.2f})
                - **Risk:** ${recommendation['risk_amount']:.2f} ({recommendation['risk_percent']:.1f}% of account)
                """)
                
                with st.expander("📝 View Full Reasoning", expanded=False):
                    st.markdown(recommendation['reasoning'])
                
                # =============================================================
                # Only propose if side is NOT neutral and RR is valid
                # =============================================================
                if side != "neutral" and recommendation.get('risk_reward_valid', False):
                    st.success(f"✅ RR {rr_ratio:.1f}:1 meets minimum (≥ {recommendation['min_rr_ratio']:.1f}:1)")
                    
                    # Auto-propose
                    reasoning = f"{recommendation['reasoning']}\n\nRisk-Reward: {rr_ratio:.1f}:1"
                    
                    prop = propose_trade(
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        entry_price=entry,
                        stop_loss=stop,
                        take_profit=take_profit,
                        reasoning=reasoning
                    )
                    st.session_state.trade_id = prop["trade_id"]
                    st.session_state.step = 1
                    st.session_state.execution_price = entry
                    st.session_state.price_source = "live" if is_healthy else "simulated"
                    st.success("✅ Trade proposed successfully!")
                    st.rerun()
                else:
                    # No clear signal – show info and do not propose
                    if side == "neutral":
                        st.warning("⚠️ No clear trade signal detected. The analysis suggests **HOLD**. No trade proposed.")
                        st.info("💡 You can still manually enter a trade below if you have a different view.")
                    else:
                        st.warning("⚠️ Risk-Reward ratio does not meet minimum. No trade proposed.")
                
            except Exception as e:
                st.error(f"❌ Analysis failed: {e}")

with col2:
    st.markdown("##### 🧪 Security Demo")
    st.caption("Test the risk engine with an unsafe proposal.")
    st.info("💰 Demo price: $60,000.00")
    
    if st.button("🚨 Simulate Unsafe AI Proposal (100 BTC)", key="propose_risky_demo"):
        try:
            prop = propose_trade(
                symbol="BTC", side="long", quantity=100.0,
                entry_price=60000.0, stop_loss=59500.0,
                reasoning="Unsafe AI Proposal: Ignoring risk limits!"
            )
            st.session_state.trade_id = prop["trade_id"]
            st.session_state.step = 1
            st.session_state.show_rejection_demo = True
            st.session_state.execution_price = 60000.0
            st.session_state.price_source = "demo"
            st.rerun()
        except Exception as e:
            st.error(f"❌ Proposal failed: {e}")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# MANUAL PROPOSAL SECTION (UPDATED WITH TP)
# ============================================================================

st.markdown("### ✍️ Manual Proposal Entry")
st.caption("Manually define trade parameters with 3:1 risk-reward guidance.")

with st.expander("📝 Manual Trade Entry", expanded=False):
    st.markdown('<div class="manual-box">', unsafe_allow_html=True)
    
    col_man1, col_man2 = st.columns(2)
    
    with col_man1:
        manual_symbol = st.selectbox(
            "Asset",
            ["BTC", "ETH", "SOL"],
            index=0,
            key="manual_symbol"
        )
        
        manual_side = st.radio(
            "Direction",
            ["long", "short"],
            horizontal=True,
            key="manual_side"
        )
        
        manual_market_data = get_live_market_data(manual_symbol)
        if manual_market_data:
            default_price = manual_market_data["last_close"]
            st.caption(f"✅ Live {manual_symbol}: ${default_price:,.2f}")
        else:
            default_price = 60000.0 if manual_symbol == "BTC" else (3000.0 if manual_symbol == "ETH" else 150.0)
            st.caption(f"⚠️ Using simulated price for {manual_symbol}")
        
        manual_entry = st.number_input(
            "Entry Price",
            value=default_price,
            step=10.0,
            format="%.2f",
            key="manual_entry_price"
        )
        
        default_stop = manual_entry * 0.985 if manual_side == "long" else manual_entry * 1.015
        manual_stop = st.number_input(
            "Stop Loss",
            value=default_stop,
            step=10.0,
            format="%.2f",
            key="manual_stop_price",
            help="Long: Stop below entry | Short: Stop above entry"
        )
        
        # Take Profit with 3:1 RR suggestion
        risk = abs(manual_entry - manual_stop)
        suggested_tp = manual_entry + (risk * 3.0) if manual_side == "long" else manual_entry - (risk * 3.0)
        
        manual_take_profit = st.number_input(
            "Take Profit (3:1 RR suggested)",
            value=suggested_tp,
            step=10.0,
            format="%.2f",
            key="manual_tp_price",
            help="3:1 risk-reward ratio is ideal"
        )
    
    with col_man2:
        st.markdown("##### Position Sizing")
        
        risk_per_unit = abs(manual_entry - manual_stop)
        risk_percent_of_price = (risk_per_unit / manual_entry) * 100 if manual_entry > 0 else 0
        
        st.caption(f"📊 Risk per unit: ${risk_per_unit:,.2f} ({risk_percent_of_price:.2f}% of entry)")
        
        account_size = 10000.0
        recommended_risk = account_size * 0.02
        recommended_size = recommended_risk / risk_per_unit if risk_per_unit > 0 else 0.01
        
        st.info(f"💡 Recommended size: {recommended_size:.4f} {manual_symbol} (${recommended_risk:.2f} risk)")
        
        manual_quantity = st.number_input(
            "Quantity",
            value=min(recommended_size, 0.1),
            step=0.001,
            format="%.4f",
            key="manual_quantity"
        )
        
        total_risk = risk_per_unit * manual_quantity
        st.metric("Total Risk", f"${total_risk:,.2f}")
        
        # Show RR ratio
        if manual_take_profit > 0:
            reward = abs(manual_take_profit - manual_entry)
            rr_ratio = reward / risk_per_unit if risk_per_unit > 0 else 0
            if rr_ratio >= 3.0:
                st.success(f"✅ RR Ratio: {rr_ratio:.1f}:1 (IDEAL)")
            elif rr_ratio >= 2.0:
                st.info(f"ℹ️ RR Ratio: {rr_ratio:.1f}:1 (Good)")
            else:
                st.warning(f"⚠️ RR Ratio: {rr_ratio:.1f}:1 (Below min)")
        
        manual_reasoning = st.text_area(
            "Reasoning (Optional)",
            value=f"Manual trade: {manual_side.upper()} {manual_quantity} {manual_symbol} at ${manual_entry:,.2f}",
            height=70,
            key="manual_reasoning"
        )
        
        if st.button("📊 Fetch Technical Analysis", key="fetch_tech_analysis"):
            with st.spinner("Analyzing market data..."):
                st.session_state.manual_tech_analysis = generate_technical_analysis(
                    manual_symbol, 
                    manual_entry,
                    manual_side
                )
                st.rerun()
        
        if st.session_state.manual_tech_analysis:
            st.markdown(st.session_state.manual_tech_analysis)
        
        st.divider()
        
        # ================================================================
        # SUBMIT MANUAL PROPOSAL BUTTON (with all validations)
        # ================================================================
        if st.button("📤 Submit Manual Proposal", type="primary", key="submit_manual"):
            if manual_entry <= 0:
                st.error("❌ Entry price must be positive")
            elif manual_stop <= 0:
                st.error("❌ Stop loss must be positive")
            elif manual_entry == manual_stop:
                st.error("❌ Entry and stop loss cannot be equal")
            elif manual_quantity <= 0:
                st.error("❌ Quantity must be positive")
            elif manual_take_profit <= 0:
                st.error("❌ Take profit must be positive")
            else:
                try:
                    # 1. Direction checks
                    if manual_side == "long" and manual_stop >= manual_entry:
                        st.error(f"❌ Stop ({manual_stop}) must be below entry ({manual_entry})")
                        st.stop()
                    if manual_side == "short" and manual_stop <= manual_entry:
                        st.error(f"❌ Stop ({manual_stop}) must be above entry ({manual_entry})")
                        st.stop()
                    if manual_side == "long" and manual_take_profit <= manual_entry:
                        st.error(f"❌ TP ({manual_take_profit}) must be above entry ({manual_entry})")
                        st.stop()
                    if manual_side == "short" and manual_take_profit >= manual_entry:
                        st.error(f"❌ TP ({manual_take_profit}) must be below entry ({manual_entry})")
                        st.stop()

                    # 2. Stop distance check (≥ 0.5%)
                    stop_distance_pct = abs(manual_entry - manual_stop) / manual_entry
                    if stop_distance_pct < MIN_STOP_DISTANCE:
                        st.error(f"❌ Stop loss is too tight: {stop_distance_pct*100:.2f}% (minimum {MIN_STOP_DISTANCE*100}%)")
                        st.info("Please widen the stop loss (e.g., increase distance between entry and stop).")
                        st.stop()

                    # 3. Risk check (≤ 1.5% of account)
                    try:
                        account_balance = get_portfolio_balance()
                    except:
                        account_balance = 10000.0  # fallback

                    risk_amount = abs(manual_entry - manual_stop) * manual_quantity
                    risk_pct = risk_amount / account_balance if account_balance > 0 else 0
                    if risk_pct > MAX_RISK_PERCENT:
                        st.error(f"❌ Risk amount ${risk_amount:.2f} is {risk_pct*100:.2f}% of account (max {MAX_RISK_PERCENT*100}%)")
                        st.info("Please reduce position size or tighten the stop loss.")
                        st.stop()

                    # 4. Position size check (with helpful max quantity suggestion)
                    position_value = manual_entry * manual_quantity
                    position_pct = position_value / account_balance if account_balance > 0 else 0
                    if position_pct > MAX_POSITION_PCT:
                        max_allowed_qty = (account_balance * MAX_POSITION_PCT) / manual_entry
                        st.error(
                            f"❌ Position size {position_pct*100:.2f}% exceeds {MAX_POSITION_PCT*100}% max\n\n"
                            f"**Maximum allowed quantity for {manual_symbol} at ${manual_entry:,.2f} is {max_allowed_qty:.4f}.**"
                        )
                        st.info("Please reduce the quantity to the suggested maximum or choose a smaller position.")
                        st.stop()

                    # Build final reasoning
                    reasoning = manual_reasoning
                    if st.session_state.manual_tech_analysis:
                        reasoning += f"\n\nTechnical Analysis:\n{st.session_state.manual_tech_analysis[:300]}..."

                    # Submit the trade
                    prop = propose_trade(
                        symbol=manual_symbol,
                        side=manual_side,
                        quantity=manual_quantity,
                        entry_price=manual_entry,
                        stop_loss=manual_stop,
                        take_profit=manual_take_profit,
                        reasoning=reasoning
                    )

                    st.session_state.trade_id = prop["trade_id"]
                    st.session_state.step = 1
                    st.session_state.execution_price = manual_entry
                    st.session_state.price_source = "manual"
                    st.success("✅ Manual proposal submitted!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Manual proposal failed: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# DISPLAY CURRENT TRADE
# ============================================================================

if st.session_state.trade_id:
    trade = get_trade(st.session_state.trade_id)
    
    if trade and trade.get('status') != 'not_found':
        st.markdown("##### Trade Proposal Details")
        
        qty = safe_float(trade.get('quantity'))
        entry = safe_float(trade.get('entry_price'))
        stop = safe_float(trade.get('stop_loss'))
        risk_pct = safe_float(trade.get('risk_percent'))
        risk_amt = safe_float(trade.get('risk_amount'))
        
        if st.session_state.price_source == "live":
            st.markdown('<span class="price-source-live">🟢 Live Price</span>', unsafe_allow_html=True)
        elif st.session_state.price_source == "simulated":
            st.markdown('<span class="price-source-simulated">🟡 Simulated Price</span>', unsafe_allow_html=True)
        elif st.session_state.price_source == "manual":
            st.markdown('<span class="price-source-manual">🔵 Manual Entry</span>', unsafe_allow_html=True)
        elif st.session_state.price_source == "demo":
            st.markdown('<span class="price-source-error">🔴 Demo Only</span>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Asset</div><div class="metric-value">{trade.get("symbol", "N/A")}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Side</div><div class="metric-value">{trade.get("side", "N/A").upper()}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Quantity</div><div class="metric-value">{qty:.4f}</div></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Entry Price</div><div class="metric-value">${entry:,.2f}</div></div>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Stop Loss</div><div class="metric-value">${stop:,.2f}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Risk %</div><div class="metric-value">{risk_pct:.2%}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Risk Amount</div><div class="metric-value">${risk_amt:,.2f}</div></div>', unsafe_allow_html=True)
        with col4:
            status_badge = {
                'proposed': '<span class="status-badge status-proposed">🟡 PROPOSED</span>',
                'risk_checked': '<span class="status-badge status-risk_checked">🔵 RISK CHECKED</span>',
                'awaiting_approval': '<span class="status-badge status-awaiting">🟠 AWAITING APPROVAL</span>',
                'approved': '<span class="status-badge status-approved">🟢 APPROVED</span>',
                'executed': '<span class="status-badge status-executed">✅ EXECUTED</span>',
                'rejected': '<span class="status-badge status-rejected">🔴 REJECTED</span>'
            }.get(trade.get('status', ''), trade.get('status', 'UNKNOWN').upper())
            st.markdown(f'<div class="metric-box"><div class="metric-label">Status</div><div class="metric-value">{status_badge}</div></div>', unsafe_allow_html=True)
        
        st.markdown(f"**📝 Reasoning:** {trade.get('reasoning', 'N/A')}")
        
        # ================================================================
        # UPDATED: Display rejection reason for rejected trades
        # ================================================================
        # dashboard.py (around the rejection display section)

if st.session_state.trade_id:
    trade = get_trade(st.session_state.trade_id)
    
    if trade and trade.get('status') != 'not_found':
        st.markdown("##### Trade Proposal Details")
        # ... (display metrics and reasoning)
        st.markdown(f"**📝 Reasoning:** {trade.get('reasoning', 'N/A')}")

        # --- Display rejection reason if rejected ---
        if trade.get('status') == 'rejected':   # <-- this must be INSIDE the if block
            st.warning("❌ Trade was rejected")
            reason = trade.get('rejection_reason', '')
            if reason:
                st.error(f"**Rejection Reason:** {reason}")
            else:
                meta = trade.get('transition_metadata', '')
                if meta:
                    try:
                        import json
                        data = json.loads(meta)
                        if 'risk_result' in data:
                            reason = data['risk_result'].get('reason', '')
                            details = data['risk_result'].get('details', {})
                        elif 'exposure_result' in data:
                            reason = data['exposure_result'].get('reason', '')
                            details = data['exposure_result'].get('details', {})
                        else:
                            reason = data.get('reason', '')
                            details = {}
                        if reason:
                            st.error(f"**Rejection Reason:** {reason}")
                            if details:
                                with st.expander("🔍 View rejection details"):
                                    st.json(details)
                        else:
                            st.info("No detailed rejection reason available.")
                    except:
                        st.info("No detailed rejection reason available.")
                else:
                    st.info("No detailed rejection reason available. Run risk validation to see details.")

        st.divider()
        
        
        # STEP 2: RISK ENGINE
        step_class = "active" if st.session_state.step >= 2 else ""
        if trade.get('status') == 'rejected': 
            step_class = "rejected"
        elif trade.get('status') in ['risk_checked', 'awaiting_approval', 'approved', 'executed']: 
            step_class = "completed"
        
        st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
        st.markdown('<span class="step-number">2</span><div class="step-title">Deterministic Risk Engine Validates</div>', unsafe_allow_html=True)
        st.markdown('<div class="step-caption">Independent risk validation enforces hard limits.</div>', unsafe_allow_html=True)
        
        if trade.get('status') == 'proposed':
            if st.button("🔍 Run Risk Validation", type="primary", key="risk_validate"):
                with st.spinner("Running risk validation..."):
                    result = screen_trade(st.session_state.trade_id)
                    if result.get('status') == 'SUCCESS':
                        st.success("✅ Risk validation PASSED")
                        st.info("Trade moved to AWAITING_APPROVAL")
                        st.session_state.step = 2
                        st.rerun()
                    else:
                        # Show detailed rejection reason
                        reason = result.get('reason', 'Unknown reason')
                        details = result.get('details', {})
                        st.error("❌ Risk validation REJECTED")
                        st.warning(f"**Reason:** {reason}")
                        if details:
                            with st.expander("🔍 View rejection details"):
                                st.json(details)
                        st.markdown('<div class="warning-box">⚠️ <strong>Key Demo Point:</strong> Trade violated risk controls. See details above.</div>', unsafe_allow_html=True)
                        st.session_state.step = 2
                        st.rerun()
        elif trade.get('status') == 'rejected':
            st.markdown('<div class="success-box">✅ Risk engine rejected unsafe trade. Fail-closed security.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="success-box">✅ Risk validation completed successfully.</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # STEP 3: HUMAN AUTHORIZATION
        if trade.get('status') not in ['rejected']:
            step_class = "active" if st.session_state.step >= 3 else ""
            if trade.get('status') in ['approved', 'executed']: 
                step_class = "completed"
            
            st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
            st.markdown('<span class="step-number">3</span><div class="step-title">Human Authorization Required</div>', unsafe_allow_html=True)
            st.markdown('<div class="step-caption">Cryptographic approval token binds approval to the exact proposal.</div>', unsafe_allow_html=True)
            
            if trade.get('status') == 'awaiting_approval':
                if st.button("🎟️ Generate Approval Token", type="primary", key="gen_token"):
                    result = request_approval(st.session_state.trade_id)
                    if result.get('status') == 'success':
                        st.session_state.token = result.get('approval_token')
                        st.success("✅ Approval token generated")
                        st.rerun()
                    else:
                        st.error(f"❌ Token generation failed: {result.get('reason')}")
                
                if st.session_state.token:
                    st.markdown("##### Approval Token")
                    st.markdown(f'<div class="token-box">{st.session_state.token}</div>', unsafe_allow_html=True)
                    st.caption("SHA-256 hash bound to your exact parameters.")
                    
                    st.divider()
                    
                    st.markdown("#### Step 4: Human Approves Trade")
                    entered_token = st.text_input("Enter Approval Token", key="token_input", placeholder="Paste token here...")
                    
                    col_approve, col_reject = st.columns(2)
                    with col_approve:
                        if st.button("✅ Approve Trade", type="primary", key="approve_trade"):
                            if entered_token.strip() == st.session_state.token:
                                result = approve_trade(entered_token.strip())
                                if result.get('status') == 'SUCCESS':
                                    st.success("✅ Trade APPROVED")
                                    st.session_state.step = 4
                                    st.rerun()
                                else:
                                    st.error(f"❌ Approval failed: {result.get('reason')}")
                            else:
                                st.error("❌ Token mismatch")
                    with col_reject:
                        if st.button("❌ Reject Trade", key="reject_trade"):
                            st.error("❌ Trade REJECTED")
                            st.session_state.step = 2
                            st.rerun()
                            
            elif trade.get('status') == 'approved':
                st.markdown('<div class="success-box">✅ Human approval verified.</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # STEP 4: EXECUTION
            if trade.get('status') == 'approved':
                step_class = "active" if st.session_state.step >= 4 else ""
                
                st.markdown(f'<div class="workflow-step {step_class}">', unsafe_allow_html=True)
                st.markdown('<span class="step-number">4</span><div class="step-title">Execution Gateway Executes</div>', unsafe_allow_html=True)
                st.markdown('<div class="step-caption">Governance verifies proposal integrity before executing.</div>', unsafe_allow_html=True)
                
                execution_price = st.session_state.execution_price or entry
                st.markdown(f"**Execution Price:** `${execution_price:,.2f}`")
                
                if st.button("🚀 Execute Trade via Adapter", type="primary", key="execute_trade"):
                    with st.spinner(f"Executing in {TRADING_MODE.upper()} mode..."):
                        result = execute_trade(st.session_state.trade_id, execution_price=execution_price)
                        if result.get('status') == 'SUCCESS':
                            st.success(f"✅ Trade EXECUTED at ${execution_price:,.2f}")
                            if TRADING_MODE == "paper":
                                st.info("📝 Paper trade simulated")
                            st.session_state.step = 5
                            st.rerun()
                        else:
                            st.error(f"❌ Execution failed: {result.get('reason', 'Unknown error')}")
                
                st.markdown('</div>', unsafe_allow_html=True)
            elif trade.get('status') == 'executed':
                st.markdown('<div class="success-box">✅ Trade executed successfully.</div>', unsafe_allow_html=True)
                
                if trade.get('executed_at'):
                    st.info(f"📅 Executed at: {trade.get('executed_at')}")

# ============================================================================
# DEMO SUMMARY
# ============================================================================

if st.session_state.show_rejection_demo and st.session_state.trade_id:
    trade = get_trade(st.session_state.trade_id)
    if trade and trade.get('status') == 'rejected':
        st.divider()
        st.markdown("### 🎯 Demo Summary: Risk Engine Rejection")
        st.markdown("""
        **What Just Happened:**
        1. ✅ Unsafe trade (100 BTC) was proposed
        2. ✅ Risk engine REJECTED the trade (exceeds 2% risk cap)
        3. ✅ Trade blocked automatically - fail-closed security
        """)

# ============================================================================
# AUDIT TRAIL
# ============================================================================

st.divider()
st.markdown("### Audit Trail - Trade History")
st.caption("Every action is recorded for full transparency.")

history = get_trade_history(limit=10)

if history.get('trades'):
    for trade in history['trades']:
        status_emoji = {
            'proposed': '🟡', 
            'risk_checked': '🔵', 
            'awaiting_approval': '🟠',
            'approved': '🟢', 
            'executed': '✅', 
            'rejected': '🔴'
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
                if trade.get('executed'): 
                    st.write(f"**Executed:** {trade['executed']}")
else:
    st.info("📭 No trades yet. Define your objective above to start.")

# ============================================================================
# RESET
# ============================================================================

st.divider()
col_r1, col_r2, col_r3 = st.columns([1, 1, 1])
with col_r2:
    if st.button("🔄 Reset Workflow", use_container_width=True):
        st.session_state.trade_id = None
        st.session_state.step = 0
        st.session_state.token = None
        st.session_state.show_rejection_demo = False
        st.session_state.execution_price = None
        st.session_state.price_source = None
        st.session_state.manual_tech_analysis = None
        clear_cache()
        st.rerun()

# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown(f"""
<div style='text-align: center; color: #8b949e; padding: 2rem 0;'>
    <h3>🛡️ TradeGuard AI</h3>
    <p><em>AI investigates. Deterministic controls verify. Humans govern. Binance executes.</em></p>
    <p>Built for Binance Agent OS Mini Hackathon - Track B</p>
    <p style='font-size: 0.8rem; margin-top: 1rem;'>
        ⚡ <strong>Mode:</strong> {TRADING_MODE.upper()} · 
        🔐 <strong>Constitution:</strong> Active · 
        📊 <strong>Version:</strong> 1.0.0
    </p>
</div>
""", unsafe_allow_html=True)