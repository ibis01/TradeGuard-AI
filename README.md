# 🛡️ TradeGuard AI

**A Risk-Governed AI Trading Agent for Binance Agent OS (Track B)**

> *"AI investigates. Deterministic controls verify. Humans govern. Binance executes. TradeGuard records."*

---

## 🎯 The Problem

Most AI trading agents are dangerous black boxes. If the LLM hallucinates a risk metric or ignores a stop-loss, the user loses capital. Autonomous execution without governance is a critical vulnerability.

## 💡 The Solution

TradeGuard AI is **not** an autonomous trading bot. It is a **governed AI agent** that demonstrates how AI can participate in trading decisions *without* being trusted with unrestricted control over capital.

We separate concerns:

1. **Agent Investigates & Proposes**: The agent analyzes market data and proposes a structured trade with 3:1 risk-reward.
2. **Deterministic Rules Validate**: Hardcoded risk engines (2% risk cap, daily limits) independently evaluate the proposal. The AI *cannot* override this.
3. **Humans Authorize**: Explicit, cryptographically-bound human approval is required.
4. **Binance Executes**: Only validated, approved intents reach the Binance execution adapter.

---

## 🏗️ Architecture

TradeGuard integrates with the Binance ecosystem through a strict, isolated adapter boundary.

```text
                    USER OBJECTIVE
                          │
                          ▼
                🤖 AI TECHNICAL        ANALYSIS
     (RSI, Trend, Support/Resistance)
                          │
                          ▼
                  TRADE PROPOSAL
           (Entry, Stop, TP, 3:1 RR)
                          │
                          ▼
              🔒 DETERMINISTIC RISK ENGINE
                 /                    \
              PASS                    REJECT
                │                       │
                ▼                       ▼
          ⚖️ GOVERNANCE              AUDIT LOG
                │
                ▼
           HUMAN APPROVAL
     (Cryptographic token, hash-bound)
                │
                ▼
       🔐 HASH / INTEGRITY CHECK
                │
                ▼
        🔗 BINANCE EXECUTION ADAPTER
      (Paper / Testnet / Mainnet isolation)
                │
                ▼
              AUDIT LOG

 [![Tests](https://img.shields.io/badge/tests-111%20passing-brightgreen)]()



---

## 📊 Risk Management for $10,000 Account

| Rule | Limit |
|------|-------|
| Max Risk Per Trade | 2% ($200) |
| Max Position Size | 10% ($1,000) |
| Max Total Exposure | 25% ($2,500) |
| Max Daily Loss | 5% ($500) |
| Min Risk-Reward | 1.5:1 |
| Ideal Risk-Reward | 3:1 |
| Min Stop Distance | 0.2% |
| Max Stop Distance | 5% |
| Max Trades Per Day | 5 |
| Max Consecutive Losses | 3 |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Binance API keys (optional, for live trading)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/TradeGuard-AI.git
cd TradeGuard-AI

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run dashboard.py



PROJECT STRUCTURE

TradeGuard-AI/
├── dashboard.py              # Main Streamlit UI
├── compatibility.py          # Compatibility layer
├── config.py                 # Configuration
├── schemas.py                # Data models
│
├── market_intelligence_mcp.py # Market data & technical analysis
├── risk_management_mcp.py    # Risk calculations
├── governance_engine.py      # Core governance logic
├── state_machine.py          # State transitions
├── trade_memory_mcp.py       # Database operations
├── exchange_adapter.py       # Exchange integration
│
├── data/
│   └── trades.db            # SQLite database
├── requirements.txt         # Dependencies
└── README.md               # This file