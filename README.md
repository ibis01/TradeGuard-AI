# 🛡️ TradeGuard AI

### The Governance Layer for Binance AI Agents

> *"AI investigates. Deterministic controls verify. Humans govern. Binance executes. TradeGuard records."*

[![Built with Binance Agent OS](https://img.shields.io/badge/Built%20with-Binance%20Agent%20OS-blue)](https://www.binance.com/en/agent-os)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## 🎯 The Problem

AI agents are becoming capable of analyzing markets and proposing trades. But **intelligence without governance is a risk**. If an LLM hallucinates a risk metric, ignores a stop-loss, or misinterprets market data, the user loses capital.

Autonomous execution without oversight is a critical vulnerability.

## 💡 The Solution

TradeGuard AI is **not** an autonomous trading bot. It is a **governed AI agent** that demonstrates how AI can participate in trading decisions *without* being trusted with unrestricted control over capital.

We separate concerns:

1. **Agent Investigates & Proposes** – The agent analyzes market data and proposes a structured trade with 3:1 risk‑reward.
2. **Deterministic Rules Validate** – Hardcoded risk engines (2% risk cap, 10% position, 25% exposure) independently evaluate the proposal. The AI *cannot* override this.
3. **Humans Authorize** – Explicit, cryptographically‑bound human approval is required.
4. **Binance Executes** – Only validated, approved intents reach the Binance execution adapter.

---

## 🔗 Built with Binance Agent OS

TradeGuard uses **Binance Agent OS** as its financial execution infrastructure.

| Component | Agent OS Role |
|-----------|---------------|
| **Market Intelligence** | Real‑time price/klines via Agent OS MCP |
| **Risk Engine** | Deterministic policy enforcement (independent of LLM) |
| **Governance** | Cryptographic approval tokens & audit trail |
| **Execution Adapter** | Paper / Testnet / Mainnet isolation through Agent OS |


```text
USER OBJECTIVE
      │
      ▼
🤖 AI AGENT
   │
   ▼
📊 MARKET INTELLIGENCE
   │
   ▼
🔒 DETERMINISTIC RISK ENGINE
   │         │
   ▼         ▼
PASS     REJECT
   │         │
   ▼         ▼
⚖️ GOVERNANCE  AUDIT LOG
   │
   ▼
👤 HUMAN APPROVAL
   │
   ▼
🔐 INTEGRITY CHECK
   │
   ▼
🔗 BINANCE AGENT OS MCP
   │
   ▼
📈 BINANCE EXECUTION



🚀 Quick Start
Prerequisites
Python 3.10+
Binance API keys (optional, for live trading)


Installation
git clone https://github.com/ibis01/TradeGuard-AI.git
cd TradeGuard-AI
pip install -r requirements.txt
streamlit run dashboard.py


Environment Variables
Create a .env file:
e
TRADING_MODE=paper
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
BINANCE_USE_MAINNET=false


📊 Risk Management for $10,000 Account
Rule	Limit
Max Risk Per Trade	2% ($200)
Max Position Size	10% ($1,000)
Max Total Exposure	25% ($2,500)
Max Daily Loss	5% ($500)
Min Risk‑Reward	2:1
Ideal Risk‑Reward	3:1
Min Stop Distance	0.5%
Max Stop Distance	2.5%
Max Trades Per Day	5
Max Consecutive Losses	3

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
        🔗 BINANCE AGENT OS MCP ADAPTER                   │
│  (Paper / Testnet / Mainnet isolation)   
                │
                ▼
              📈 BINANCE EXECUTION 

 [![Tests](https://img.shields.io/badge/tests-111%20passing-brightgreen)]()

---


🛡️ Security Features

Cryptographic Approval Tokens – SHA‑256 hash binding
Deterministic Risk Engine – Cannot be bypassed by LLM
Fail‑Closed Security – Errors reject trades
Audit Trail – Every action recorded
Hash Integrity Check – Proposal tampering detection
Isolated Adapter Layer – Exchange logic separated


📁 Project Structure
text
TradeGuard-AI/
├── dashboard.py              # Main Streamlit UI
├── compatibility.py          # Dashboard↔core bridge
├── config.py                 # Central configuration
├── schemas.py                # Pydantic models
│
├── market_intelligence_mcp.py # Technical analysis
├── risk_management_mcp.py    # Risk calculations
├── governance_engine.py      # Core governance logic
├── state_machine.py          # State transitions
├── trade_memory_mcp.py       # SQLite persistence
├── exchange_adapter.py       # Binance integration
├── guardrails_mcp.py         # Portfolio guardrails
│
├── tests/                    # 110 passing tests
├── data/                     # SQLite database
├── requirements.txt
└── README.md


🧪 Testing
pytest tests/ -q
All 110 tests pass.

🤝 Contributing
Fork the repository
Create a feature branch
Commit your changes
Push to the branch
Open a Pull Request

📝 License
MIT

📧 Contact
GitHub: @ibis01
Hackathon Submission: Binance Agent OS Mini Hackathon

🙏 Acknowledgments

Built for Binance Agent OS Mini Hackathon – Track B
Powered by Binance Agent OS MCP, Streamlit, SQLite, and ccxt
The safest AI trade is the one your AI is not allowed to make. 🛡️



